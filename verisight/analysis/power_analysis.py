"""
Power Intent & Low-Power Verification Engine for VeriSight.

Performs static and simulation-correlated power-aware verification:
1. Power Domain Boundary Crossing Analysis (identifies signals crossing domains)
2. Isolation Strategy Verification (missing clamps on power-down boundaries)
3. Level Shifter Verification (cross-voltage domain shifting)
4. Retention Register Verification (save/restore controls & always-on supplies)
5. Power Switch & Power State Sequencing Hazards (PST consistency & illegal states)
6. Simulation Log Cross-Correlation (correlating logged X-values/errors with power domains)
"""

from typing import List, Dict, Set, Optional, Any, Tuple
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.schemas.rtl_analysis import PowerAnalysisResult, PowerIssue
from verisight.schemas.upf_schema import UPFKnowledge
from verisight.utils.logger import get_logger

logger = get_logger("power_analysis")


def analyze_power_intent(knowledge: UnifiedKnowledge) -> Optional[PowerAnalysisResult]:
    """
    Run comprehensive low-power and UPF intent analysis against the RTL design.

    Returns:
        PowerAnalysisResult if UPF is present, or None if no UPF was supplied.
    """
    if not knowledge.upf or not knowledge.upf.power_domains:
        logger.debug("No UPF power intent provided; skipping power analysis.")
        return None

    upf = knowledge.upf
    rtl = knowledge.rtl

    result = PowerAnalysisResult()
    result.domains_analyzed = [pd.name for pd in upf.power_domains]

    # 1. Map RTL modules & instances to Power Domains
    instance_to_domain: Dict[str, str] = {}
    module_to_domain: Dict[str, str] = {}
    domain_by_name = {pd.name: pd for pd in upf.power_domains}

    # Identify top power domain
    top_domain_name = ""
    for pd in upf.power_domains:
        if pd.is_top:
            top_domain_name = pd.name
            break
    if not top_domain_name and upf.power_domains:
        top_domain_name = upf.power_domains[0].name

    for pd in upf.power_domains:
        for elem in pd.elements:
            clean_elem = elem.strip("{}")
            instance_to_domain[clean_elem] = pd.name
        for mod in pd.associated_modules:
            module_to_domain[mod] = pd.name

    # Identify domains that can be powered down (have power switches or OFF states in PST)
    gated_domains: Set[str] = set()
    for ps in upf.power_switches:
        if ps.domain:
            gated_domains.add(ps.domain)
    for pst in upf.power_state_tables:
        for st_name, supply_vals in pst.states.items():
            for s_val in supply_vals:
                if s_val.upper() in ("OFF", "0", "GND", "POWER_DOWN"):
                    for pd in upf.power_domains:
                        if pd.name != top_domain_name:
                            gated_domains.add(pd.name)

    # 2. Check RTL-UPF Hierarchy Mismatches
    for diag in upf.diagnostics:
        issue = PowerIssue(
            severity="warning" if diag.severity == "warning" else "high",
            category="hierarchy_mismatch",
            description=diag.message,
            file=diag.file,
            line_number=diag.line_number,
            recommendation="Verify UPF scope/elements match RTL module declarations and instantiations.",
        )
        result.hierarchy_mismatches.append(issue)

    # 3. Domain Boundary Crossing & Isolation Analysis
    # Inspect top-level module instantiations and port connections
    top_mod = None
    if rtl and rtl.modules:
        for m in rtl.modules:
            if m.name == rtl.top_module:
                top_mod = m
                break
        if not top_mod and rtl.modules:
            top_mod = rtl.modules[0]

    # Find signals crossing between instances
    if top_mod and rtl:
        for inst in top_mod.instantiations:
            inst_name = inst.get("instance", "")
            mod_type = inst.get("module", "")
            src_domain = instance_to_domain.get(inst_name, module_to_domain.get(mod_type, top_domain_name))

            # If src_domain can be powered down, check its output signals
            if src_domain in gated_domains and src_domain != top_domain_name:
                # Find isolation strategies for this domain
                has_output_isolation = False
                isolated_signals: Set[str] = set()
                clamp_val = "0"
                iso_ctrl = ""

                for iso in upf.isolation_strategies:
                    if iso.domain == src_domain and iso.applies_to in ("outputs", "both"):
                        has_output_isolation = True
                        clamp_val = iso.clamp_value
                        iso_ctrl = iso.isolation_signal
                        if iso.elements:
                            isolated_signals.update(iso.elements)

                # Look up child module ports
                child_mod = next((m for m in rtl.modules if m.name == mod_type), None)
                if child_mod:
                    output_ports = [p.name for p in child_mod.ports if p.direction in ("output", "inout")]
                    unisolated = []
                    for out_p in output_ports:
                        if isolated_signals and out_p not in isolated_signals:
                            unisolated.append(out_p)

                    if not has_output_isolation:
                        result.isolation_issues.append(PowerIssue(
                            severity="critical",
                            category="isolation",
                            domain=src_domain,
                            module=mod_type,
                            instance=inst_name,
                            signals=output_ports[:5],
                            description=(
                                f"Power domain '{src_domain}' contains switchable instance '{inst_name}' ({mod_type}), "
                                f"but no output isolation strategy is defined. When '{src_domain}' is powered off, "
                                f"{len(output_ports)} output signal(s) ({', '.join(output_ports[:3])}) will float, "
                                f"propagating metastable X-values to active logic."
                            ),
                            recommendation=(
                                f"Add an isolation strategy in UPF: "
                                f"'set_isolation iso_{src_domain} -domain {src_domain} -applies_to outputs "
                                f"-clamp_value 0 -isolation_signal <pwr_ctrl.iso_en>'"
                            ),
                        ))
                    elif unisolated:
                        result.isolation_issues.append(PowerIssue(
                            severity="high",
                            category="isolation",
                            domain=src_domain,
                            module=mod_type,
                            instance=inst_name,
                            signals=unisolated[:5],
                            description=(
                                f"Isolation strategy for '{src_domain}' only covers partial elements; "
                                f"{len(unisolated)} output signal(s) ({', '.join(unisolated[:3])}) remain unisolated."
                            ),
                            recommendation=f"Update UPF -elements list or remove -elements to isolate all domain outputs.",
                        ))

                    if has_output_isolation and not iso_ctrl:
                        result.isolation_issues.append(PowerIssue(
                            severity="high",
                            category="isolation",
                            domain=src_domain,
                            module=mod_type,
                            instance=inst_name,
                            description=(
                                f"Isolation strategy in domain '{src_domain}' is missing an isolation control signal "
                                f"(-isolation_signal). Clamps cannot be dynamically activated."
                            ),
                            recommendation="Specify '-isolation_signal <signal_name>' in set_isolation or set_isolation_control.",
                        ))

    # 4. Level Shifter Strategy Verification
    # Check if multiple domains exist and if level shifters are present across different supplies
    domains_with_diff_supplies = set()
    for pd in upf.power_domains:
        if pd.primary_power_net and pd.primary_power_net.upper() not in ("VDD", "VCC"):
            domains_with_diff_supplies.add(pd.name)

    if domains_with_diff_supplies:
        for d_name in domains_with_diff_supplies:
            has_ls = any(ls.domain == d_name for ls in upf.level_shifters)
            if not has_ls:
                result.level_shift_issues.append(PowerIssue(
                    severity="high",
                    category="level_shift",
                    domain=d_name,
                    description=(
                        f"Power domain '{d_name}' operates on a distinct voltage supply net "
                        f"('{domain_by_name[d_name].primary_power_net}'), but no level shifter strategy "
                        f"is defined for boundary crossings."
                    ),
                    recommendation=(
                        f"Define level shifter strategy: "
                        f"'set_level_shifter ls_{d_name} -domain {d_name} -applies_to both -rule both'"
                    ),
                ))

    # 5. Retention Strategy Verification
    for ret in upf.retention_strategies:
        dom = domain_by_name.get(ret.domain)
        # Check if retention power net is identical to switched domain supply
        if dom and ret.retention_power_net and dom.primary_power_net:
            if ret.retention_power_net == dom.primary_power_net and ret.domain in gated_domains:
                result.retention_issues.append(PowerIssue(
                    severity="critical",
                    category="retention",
                    domain=ret.domain,
                    description=(
                        f"Retention strategy '{ret.name}' retention_power_net ('{ret.retention_power_net}') "
                        f"is connected to the gated primary supply of '{ret.domain}'. During power-down, "
                        f"retention registers will lose state due to loss of backup supply."
                    ),
                    recommendation="Connect retention_power_net to an always-on backup supply net (e.g. VDD_AON).",
                ))

        if not ret.save_signal or not ret.restore_signal:
            result.retention_issues.append(PowerIssue(
                severity="high",
                category="retention",
                domain=ret.domain,
                description=(
                    f"Retention strategy '{ret.name}' in domain '{ret.domain}' is missing save/restore "
                    f"control handshake signals."
                ),
                recommendation="Provide -save_signal and -restore_signal in set_retention or set_retention_control.",
            ))

    # 6. Power Sequencing & Power State Table (PST) Hazards
    for pst in upf.power_state_tables:
        supplies = pst.supplies
        for state_name, states in pst.states.items():
            if len(states) != len(supplies):
                result.sequencing_issues.append(PowerIssue(
                    severity="error",
                    category="sequencing",
                    description=(
                        f"PST '{pst.name}' state '{state_name}' has {len(states)} values, "
                        f"expected {len(supplies)} matching supplies list ({', '.join(supplies)})."
                    ),
                    recommendation="Ensure state vector length exactly matches the number of supplies in create_pst.",
                ))

            # Check if switched supply is ON while primary parent supply is OFF
            for ps in upf.power_switches:
                in_net = ps.input_supply_port.split()[-1] if ps.input_supply_port else ""
                out_net = ps.output_supply_port.split()[-1] if ps.output_supply_port else ""
                if in_net in supplies and out_net in supplies:
                    in_idx = supplies.index(in_net)
                    out_idx = supplies.index(out_net)
                    if in_idx < len(states) and out_idx < len(states):
                        in_val = states[in_idx].upper()
                        out_val = states[out_idx].upper()
                        if in_val in ("OFF", "0", "GND") and out_val in ("ON", "1", "FULL_ON"):
                            result.sequencing_issues.append(PowerIssue(
                                severity="critical",
                                category="sequencing",
                                domain=ps.domain,
                                description=(
                                    f"Illegal Power State in PST '{pst.name}', state '{state_name}': "
                                    f"Switched output supply '{out_net}' is ON while input supply '{in_net}' is OFF."
                                ),
                                recommendation="Correct the state entry in add_pst_state so switched nets cannot be ON without source power.",
                            ))

    # 7. Simulation Log Cross-Correlation
    if knowledge.logs and knowledge.logs.errors:
        for err in knowledge.logs.errors:
            msg = err.message or ""
            # Check if error mentions a signal or domain in our power intent
            for pd in upf.power_domains:
                for elem in pd.elements:
                    clean = elem.strip("{}")
                    if clean.lower() in msg.lower() or pd.name.lower() in msg.lower():
                        result.power_aware_sim_checks.append({
                            "domain": pd.name,
                            "element": clean,
                            "error": msg[:200],
                            "time": err.timestamp,
                        })

    # Combine all issues
    result.all_issues = (
        result.isolation_issues
        + result.level_shift_issues
        + result.retention_issues
        + result.sequencing_issues
        + result.hierarchy_mismatches
    )

    # Compose summary
    crit_count = sum(1 for i in result.all_issues if i.severity in ("critical", "error"))
    high_count = sum(1 for i in result.all_issues if i.severity == "high")
    result.summary = (
        f"Analyzed {len(result.domains_analyzed)} power domain(s) across UPF power intent: "
        f"{len(result.all_issues)} issue(s) identified ({crit_count} critical/error, {high_count} high). "
        f"Gated domains: {', '.join(sorted(gated_domains)) or 'None'}. "
        f"Isolation checks: {len(result.isolation_issues)} issue(s), "
        f"Level shift checks: {len(result.level_shift_issues)} issue(s)."
    )

    logger.info(f"Power Analysis completed: {result.summary}")
    return result

