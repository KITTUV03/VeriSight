"""
UPF (Unified Power Format - IEEE 1801) Parser for VeriSight.

Parses UPF power-intent files and extracts:
- Power domains (create_power_domain)
- Supply ports and nets (create_supply_port, create_supply_net, connect_supply_net)
- Supply sets (create_supply_set)
- Power switches (create_power_switch)
- Isolation strategies (set_isolation, set_isolation_control)
- Level shifter strategies (set_level_shifter)
- Retention strategies (set_retention, set_retention_control)
- Power states and Power State Tables (add_power_state, create_pst, add_pst_state)

Resolves UPF power-intent against the actual RTL design hierarchy:
- Binds power domains to RTL instances and modules
- Discovers signals crossing power domain boundaries
- Validates isolation, level shifting, and state retention
- Emits actionable diagnostics with filename and line numbers
Deterministic parser — no external EDA tool or LLM required.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union, Set, Any

from verisight.schemas.upf_schema import (
    UPFKnowledge, PowerDomain, SupplyPort, SupplyNet, SupplySet,
    PowerSwitch, IsolationStrategy, LevelShifterStrategy,
    RetentionStrategy, PowerState, PowerStateTable, DomainCrossing,
    UPFValidationIssue,
)
from verisight.schemas.rtl_schema import RTLKnowledge
from verisight.utils.file_utils import read_file, discover_files, UPF_EXTENSIONS
from verisight.utils.logger import get_logger

logger = get_logger("upf_parser")


def parse_upf(
    path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
    files: Optional[List[Union[str, Path]]] = None,
    rtl_knowledge: Optional[RTLKnowledge] = None,
    upf_path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
    upf_files: Optional[List[Union[str, Path]]] = None,
    **kwargs,
) -> UPFKnowledge:
    """
    Parse one or more UPF power-intent files and correlate with RTL hierarchy.

    Args:
        path: Path to a .upf file, directory containing UPF, or list of paths.
        files: Optional explicit list of UPF file paths.
        rtl_knowledge: Optional parsed RTLKnowledge to resolve hierarchy against.

    Returns:
        UPFKnowledge Pydantic model with power domains, strategies, crossings, and diagnostics.
    """
    path = path or upf_path or kwargs.get("upf")
    files = files or upf_files
    resolved_paths: List[Path] = []

    def _add_target(target: Union[str, Path]):
        if isinstance(target, (list, tuple)):
            for item in target:
                _add_target(item)
            return

        p = Path(target)
        if p.is_file():
            if p not in resolved_paths:
                resolved_paths.append(p)
        elif p.is_dir():
            found = discover_files(p, UPF_EXTENSIONS)
            for f in found:
                if f not in resolved_paths:
                    resolved_paths.append(f)
        else:
            logger.warning(f"UPF target path does not exist on disk: {target}")

    if files:
        _add_target(files)
    if path:
        _add_target(path)

    if not resolved_paths:
        logger.info("parse_upf: No UPF files provided")
        return UPFKnowledge(
            file_list=[],
            summary="No UPF power-intent specification provided.",
            is_valid=True,
        )

    logger.info(f"Parsing UPF power intent ({len(resolved_paths)} file(s))")

    file_list: List[str] = []
    power_domains: List[PowerDomain] = []
    supply_ports: List[SupplyPort] = []
    supply_nets: List[SupplyNet] = []
    supply_sets: List[SupplySet] = []
    power_switches: List[PowerSwitch] = []
    isolation_strategies: List[IsolationStrategy] = []
    level_shifter_strategies: List[LevelShifterStrategy] = []
    retention_strategies: List[RetentionStrategy] = []
    power_states: List[PowerState] = []
    power_state_tables: List[PowerStateTable] = []
    validation_issues: List[UPFValidationIssue] = []

    for upf_file in resolved_paths:
        file_list.append(str(upf_file))
        raw_text = read_file(upf_file)
        if not raw_text:
            validation_issues.append(UPFValidationIssue(
                severity="warning",
                issue_type="syntax_error",
                description=f"Empty UPF file: {upf_file.name}",
                file=str(upf_file),
            ))
            continue

        commands = _tokenize_upf_commands(raw_text, str(upf_file), validation_issues)

        for cmd, line_num, raw_line in commands:
            _parse_command(
                cmd=cmd,
                line_num=line_num,
                raw_line=raw_line,
                filepath=str(upf_file),
                power_domains=power_domains,
                supply_ports=supply_ports,
                supply_nets=supply_nets,
                supply_sets=supply_sets,
                power_switches=power_switches,
                isolation_strategies=isolation_strategies,
                level_shifter_strategies=level_shifter_strategies,
                retention_strategies=retention_strategies,
                power_states=power_states,
                power_state_tables=power_state_tables,
                validation_issues=validation_issues,
            )

    # ── Resolve against RTL Hierarchy (if RTL knowledge is present) ───
    resolved_hierarchy: Dict[str, str] = {}
    domain_crossings: List[DomainCrossing] = []

    if rtl_knowledge and rtl_knowledge.modules:
        resolved_hierarchy, domain_crossings = _resolve_upf_with_rtl(
            rtl_knowledge=rtl_knowledge,
            power_domains=power_domains,
            isolation_strategies=isolation_strategies,
            level_shifter_strategies=level_shifter_strategies,
            retention_strategies=retention_strategies,
            power_switches=power_switches,
            power_state_tables=power_state_tables,
            validation_issues=validation_issues,
            file_list=file_list,
        )

    # Check validity
    has_errors = any(issue.severity == "error" for issue in validation_issues)
    is_valid = not has_errors

    # Generate summary
    summary_parts = [
        f"Parsed {len(power_domains)} power domain(s)",
        f"{len(supply_nets)} supply net(s)",
        f"{len(power_switches)} power switch(es)",
        f"{len(isolation_strategies)} isolation strategy(ies)",
        f"{len(level_shifter_strategies)} level shifter(s)",
        f"{len(retention_strategies)} retention strategy(ies)",
    ]
    if domain_crossings:
        summary_parts.append(f"{len(domain_crossings)} cross-domain signal(s)")
    if validation_issues:
        summary_parts.append(f"{len(validation_issues)} validation diagnostic(s)")

    summary_str = f"UPF Power Intent: {', '.join(summary_parts)}."

    knowledge = UPFKnowledge(
        file_list=file_list,
        power_domains=power_domains,
        supply_ports=supply_ports,
        supply_nets=supply_nets,
        supply_sets=supply_sets,
        power_switches=power_switches,
        isolation_strategies=isolation_strategies,
        level_shifter_strategies=level_shifter_strategies,
        retention_strategies=retention_strategies,
        power_states=power_states,
        power_state_tables=power_state_tables,
        resolved_hierarchy=resolved_hierarchy,
        domain_crossings=domain_crossings,
        validation_issues=validation_issues,
        summary=summary_str,
        is_valid=is_valid,
    )

    logger.info(summary_str)
    return knowledge


def _tokenize_upf_commands(
    content: str, filepath: str, validation_issues: List[UPFValidationIssue]
) -> List[Tuple[List[str], int, str]]:
    """
    Tokenize UPF source lines, handling comments (#), line continuations (\\),
    and grouping curly braces/quotes.
    """
    commands: List[Tuple[List[str], int, str]] = []
    lines = content.splitlines()

    current_tokens: List[str] = []
    current_start_line: int = 1
    current_raw: List[str] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        line_num = i + 1

        # Skip empty lines or pure comments if not continuing
        if not current_tokens and (not line or line.startswith("#")):
            i += 1
            continue

        if not current_tokens:
            current_start_line = line_num

        # Check line continuation
        is_continued = line.endswith("\\")
        if is_continued:
            line_part = line[:-1].strip()
        else:
            line_part = line

        # Strip inline comments (outside quotes or braces)
        line_part = _strip_upf_comment(line_part)

        current_raw.append(line_part)

        # Tokenize line part
        tokens = _tokenize_line(line_part)
        current_tokens.extend(tokens)

        if not is_continued:
            if current_tokens:
                # Merge tokens that belong to braces e.g. { ... }
                normalized_tokens = _normalize_braced_tokens(current_tokens)
                commands.append((normalized_tokens, current_start_line, " ".join(current_raw)))
            current_tokens = []
            current_raw = []

        i += 1

    if current_tokens:
        normalized_tokens = _normalize_braced_tokens(current_tokens)
        commands.append((normalized_tokens, current_start_line, " ".join(current_raw)))

    return commands


def _strip_upf_comment(line: str) -> str:
    """Strip '#' comments that are not inside curly braces or double quotes."""
    res = []
    in_quote = False
    in_brace = 0
    for char in line:
        if char == '"':
            in_quote = not in_quote
        elif char == '{':
            in_brace += 1
        elif char == '}':
            in_brace = max(0, in_brace - 1)
        elif char == '#' and not in_quote and in_brace == 0:
            break
        res.append(char)
    return "".join(res).strip()


def _tokenize_line(line: str) -> List[str]:
    """Tokenize a line respecting double quotes and curly braces."""
    tokens = []
    buf = []
    in_quote = False
    brace_depth = 0

    for char in line:
        if char == '"':
            in_quote = not in_quote
            buf.append(char)
        elif char == '{' and not in_quote:
            brace_depth += 1
            buf.append(char)
        elif char == '}' and not in_quote:
            brace_depth = max(0, brace_depth - 1)
            buf.append(char)
        elif char.isspace() and not in_quote and brace_depth == 0:
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(char)

    if buf:
        tokens.append("".join(buf))

    return tokens


def _normalize_braced_tokens(tokens: List[str]) -> List[str]:
    """Clean enclosing braces and quotes from arguments."""
    normalized = []
    for tok in tokens:
        if tok.startswith("{") and tok.endswith("}"):
            normalized.append(tok[1:-1].strip())
        elif tok.startswith('"') and tok.endswith('"'):
            normalized.append(tok[1:-1].strip())
        else:
            normalized.append(tok)
    return normalized


def _get_flag_value(tokens: List[str], flag: str, default: str = "") -> str:
    """Extract argument for a specific flag (e.g. -domain <name>)."""
    for i, tok in enumerate(tokens):
        if tok == flag and i + 1 < len(tokens):
            return tokens[i + 1]
    return default


def _get_flag_list(tokens: List[str], flag: str) -> List[str]:
    """Extract list argument for a specific flag (e.g. -elements { a b c })."""
    for i, tok in enumerate(tokens):
        if tok == flag and i + 1 < len(tokens):
            val = tokens[i + 1].strip()
            # Split by whitespace or commas
            items = [item.strip() for item in re.split(r"[\s,]+", val) if item.strip()]
            return items
    return []


def _parse_command(
    cmd: List[str],
    line_num: int,
    raw_line: str,
    filepath: str,
    power_domains: List[PowerDomain],
    supply_ports: List[SupplyPort],
    supply_nets: List[SupplyNet],
    supply_sets: List[SupplySet],
    power_switches: List[PowerSwitch],
    isolation_strategies: List[IsolationStrategy],
    level_shifter_strategies: List[LevelShifterStrategy],
    retention_strategies: List[RetentionStrategy],
    power_states: List[PowerState],
    power_state_tables: List[PowerStateTable],
    validation_issues: List[UPFValidationIssue],
):
    """Parse a single tokenized UPF command."""
    if not cmd:
        return

    name_cmd = cmd[0].lower()

    # 1. create_power_domain
    if name_cmd == "create_power_domain":
        if len(cmd) < 2:
            validation_issues.append(UPFValidationIssue(
                severity="error",
                issue_type="syntax_error",
                description="create_power_domain requires a domain name argument",
                file=filepath,
                line_number=line_num,
            ))
            return

        dom_name = cmd[1]
        scope = _get_flag_value(cmd, "-scope", "")
        include_scope = "-include_scope" in cmd
        elements = _get_flag_list(cmd, "-elements")

        # Check for duplicate domain name
        if any(d.name == dom_name for d in power_domains):
            validation_issues.append(UPFValidationIssue(
                severity="warning",
                issue_type="syntax_error",
                description=f"Duplicate power domain '{dom_name}' redefined at line {line_num}",
                file=filepath,
                line_number=line_num,
                element=dom_name,
            ))

        power_domains.append(PowerDomain(
            name=dom_name,
            scope=scope,
            elements=elements,
            is_default=include_scope or (not elements and (dom_name.upper() in ("PD_TOP", "TOP_PD", "DEFAULT"))),
        ))

    # 2. create_supply_port
    elif name_cmd == "create_supply_port":
        if len(cmd) < 2:
            return
        port_name = cmd[1]
        direction = _get_flag_value(cmd, "-direction", "in")
        domain = _get_flag_value(cmd, "-domain", "")
        supply_ports.append(SupplyPort(
            name=port_name,
            direction=direction,
            domain=domain,
        ))

    # 3. create_supply_net
    elif name_cmd == "create_supply_net":
        if len(cmd) < 2:
            return
        net_name = cmd[1]
        domain = _get_flag_value(cmd, "-domain", "")
        resolve = _get_flag_value(cmd, "-resolve", "unresolved")
        is_gnd = any(g in net_name.upper() for g in ("VSS", "GND", "GROUND"))
        is_pwr = any(p in net_name.upper() for p in ("VDD", "VCC", "POWER"))
        supply_nets.append(SupplyNet(
            name=net_name,
            domain=domain,
            is_ground=is_gnd,
            is_power=is_pwr,
            resolved_type=resolve,
        ))

    # 4. set_domain_supply_net
    elif name_cmd == "set_domain_supply_net":
        dom_name = cmd[1] if len(cmd) > 1 and not cmd[1].startswith("-") else _get_flag_value(cmd, "-domain")
        pwr_net = _get_flag_value(cmd, "-primary_power_net")
        gnd_net = _get_flag_value(cmd, "-primary_ground_net")
        for d in power_domains:
            if d.name == dom_name:
                if pwr_net:
                    d.primary_power_net = pwr_net
                if gnd_net:
                    d.primary_ground_net = gnd_net

    # 5. create_supply_set
    elif name_cmd == "create_supply_set":
        if len(cmd) < 2:
            return
        set_name = cmd[1]
        # Match -function {power VDD} -function {ground VSS}
        pwr_match = re.search(r"-function\s*\{?\s*power\s+([\w.]+)\s*\}?", raw_line)
        gnd_match = re.search(r"-function\s*\{?\s*ground\s+([\w.]+)\s*\}?", raw_line)
        pwr_net = pwr_match.group(1) if pwr_match else ""
        gnd_net = gnd_match.group(1) if gnd_match else ""

        supply_sets.append(SupplySet(
            name=set_name,
            power_net=pwr_net,
            ground_net=gnd_net,
        ))

    # 6. create_power_switch
    elif name_cmd == "create_power_switch":
        if len(cmd) < 2:
            return
        sw_name = cmd[1]
        dom_name = _get_flag_value(cmd, "-domain")
        in_port = _get_flag_value(cmd, "-input_supply_port")
        out_port = _get_flag_value(cmd, "-output_supply_port")
        ctl_match = re.search(r"-control_port\s*\{?\s*([\w.]+)(?:\s+([\w.]+))?\s*\}?", raw_line)
        ctl_port = (ctl_match.group(2) or ctl_match.group(1)) if ctl_match else _get_flag_value(cmd, "-control_port")
        on_state = _get_flag_value(cmd, "-on_state")
        if not on_state:
            on_match = re.search(r"-on_state\s*\{([^}]+)\}", raw_line)
            on_state = on_match.group(1).strip() if on_match else ""

        power_switches.append(PowerSwitch(
            name=sw_name,
            domain=dom_name,
            in_port=in_port,
            out_port=out_port,
            control_port=ctl_port,
            on_state=on_state,
        ))

    # 7. set_isolation
    elif name_cmd == "set_isolation":
        if len(cmd) < 2:
            return
        iso_name = cmd[1]
        dom_name = _get_flag_value(cmd, "-domain")
        clamp_val = _get_flag_value(cmd, "-clamp_value", "0")
        applies_to = _get_flag_value(cmd, "-applies_to", "outputs")
        location = _get_flag_value(cmd, "-location", "from")
        elements = _get_flag_list(cmd, "-elements")
        iso_sig = _get_flag_value(cmd, "-isolation_signal", "")
        iso_sense = _get_flag_value(cmd, "-isolation_sense", "high")

        isolation_strategies.append(IsolationStrategy(
            name=iso_name,
            domain=dom_name,
            isolation_signal=iso_sig,
            isolation_sense=iso_sense,
            clamp_value=clamp_val,
            elements=elements,
            applies_to=applies_to,
            location=location,
        ))

    # 8. set_isolation_control
    elif name_cmd == "set_isolation_control":
        if len(cmd) < 2:
            return
        iso_name = cmd[1]
        iso_sig = _get_flag_value(cmd, "-isolation_signal")
        iso_sense = _get_flag_value(cmd, "-isolation_sense", "high")
        location = _get_flag_value(cmd, "-location", "")

        for strat in isolation_strategies:
            if strat.name == iso_name:
                if iso_sig:
                    strat.isolation_signal = iso_sig
                if iso_sense:
                    strat.isolation_sense = iso_sense
                if location:
                    strat.location = location

    # 9. set_level_shifter
    elif name_cmd == "set_level_shifter":
        if len(cmd) < 2:
            return
        ls_name = cmd[1]
        dom_name = _get_flag_value(cmd, "-domain")
        rule = _get_flag_value(cmd, "-rule", "both")
        applies_to = _get_flag_value(cmd, "-applies_to", "both")
        elements = _get_flag_list(cmd, "-elements")
        threshold = _get_flag_value(cmd, "-threshold", "")

        level_shifter_strategies.append(LevelShifterStrategy(
            name=ls_name,
            domain=dom_name,
            rule=rule,
            applies_to=applies_to,
            elements=elements,
            threshold=threshold,
        ))

    # 10. set_retention
    elif name_cmd == "set_retention":
        if len(cmd) < 2:
            return
        ret_name = cmd[1]
        dom_name = _get_flag_value(cmd, "-domain")
        pwr_net = _get_flag_value(cmd, "-retention_power_net")
        gnd_net = _get_flag_value(cmd, "-retention_ground_net")
        elements = _get_flag_list(cmd, "-elements")

        retention_strategies.append(RetentionStrategy(
            name=ret_name,
            domain=dom_name,
            retention_power_net=pwr_net,
            retention_ground_net=gnd_net,
            elements=elements,
        ))

    # 11. set_retention_control
    elif name_cmd == "set_retention_control":
        if len(cmd) < 2:
            return
        ret_name = cmd[1]
        save_match = re.search(r"-save_signal\s*\{?\s*([\w.]+)\s*\}?", raw_line)
        restore_match = re.search(r"-restore_signal\s*\{?\s*([\w.]+)\s*\}?", raw_line)
        save_sig = save_match.group(1) if save_match else ""
        restore_sig = restore_match.group(1) if restore_match else ""

        for ret in retention_strategies:
            if ret.name == ret_name:
                if save_sig:
                    ret.save_signal = save_sig
                if restore_sig:
                    ret.restore_signal = restore_sig

    # 12. add_power_state
    elif name_cmd == "add_power_state":
        if len(cmd) < 2:
            return
        obj_ref = cmd[1]
        # Match -state { STATE_NAME LOGIC_EXPR ... }
        state_match = re.search(r"-state\s*\{?\s*(\w+)\s+([^}]+)\}?", raw_line)
        if state_match:
            s_name = state_match.group(1)
            s_expr = state_match.group(2).strip()
            simstate = "NORMAL"
            if "OFF" in s_name.upper() or "OFF" in s_expr.upper():
                simstate = "OFF"
            elif "CORRUPT" in s_expr.upper() or "SLEEP" in s_name.upper():
                simstate = "CORRUPT"

            power_states.append(PowerState(
                name=s_name,
                object_ref=obj_ref,
                logic_expression=s_expr,
                simstate=simstate,
            ))

    # 13. create_pst
    elif name_cmd == "create_pst":
        if len(cmd) < 2:
            return
        pst_name = cmd[1]
        supplies = _get_flag_list(cmd, "-supplies")
        power_state_tables.append(PowerStateTable(
            name=pst_name,
            supplies=supplies,
            states=[],
        ))

    # 14. add_pst_state
    elif name_cmd == "add_pst_state":
        if len(cmd) < 2:
            return
        state_name = cmd[1]
        pst_name = _get_flag_value(cmd, "-pst")
        state_vals = _get_flag_list(cmd, "-state")

        for pst in power_state_tables:
            if pst.name == pst_name:
                row_dict: Dict[str, str] = {"state": state_name}
                for idx, sup in enumerate(pst.supplies):
                    if idx < len(state_vals):
                        row_dict[sup] = state_vals[idx]
                    else:
                        row_dict[sup] = "UNKNOWN"
                pst.states.append(row_dict)


def _resolve_upf_with_rtl(
    rtl_knowledge: RTLKnowledge,
    power_domains: List[PowerDomain],
    isolation_strategies: List[IsolationStrategy],
    level_shifter_strategies: List[LevelShifterStrategy],
    retention_strategies: List[RetentionStrategy],
    power_switches: List[PowerSwitch],
    power_state_tables: List[PowerStateTable],
    validation_issues: List[UPFValidationIssue],
    file_list: List[str],
) -> Tuple[Dict[str, str], List[DomainCrossing]]:
    """
    Resolve UPF elements against the actual RTL design hierarchy and identify
    domain boundary crossings and potential power-aware hazards.
    """
    resolved_hierarchy: Dict[str, str] = {}
    domain_crossings: List[DomainCrossing] = []
    primary_upf_file = file_list[0] if file_list else "design.upf"

    # Map of module name -> module
    module_map = {m.name: m for m in rtl_knowledge.modules}
    top_mod_name = rtl_knowledge.top_module

    # Identify default / top power domain
    top_domain = None
    for dom in power_domains:
        if dom.is_default or dom.name.upper() in ("PD_TOP", "TOP_PD"):
            top_domain = dom
            break
    if not top_domain and power_domains:
        top_domain = power_domains[0]

    # ── 1. Map RTL Modules / Instances to Power Domains ───────────────
    # Collect all instantiated paths in RTL
    all_instances: Dict[str, str] = {}  # instance_name -> module_name
    for m in rtl_knowledge.modules:
        for inst in m.instantiations:
            inst_name = inst.get("instance", "")
            mod_name = inst.get("module", "")
            if inst_name and mod_name:
                all_instances[inst_name] = mod_name

    for dom in power_domains:
        for elem in dom.elements:
            elem_clean = elem.strip().lstrip("/")
            elem_leaf = elem_clean.split("/")[-1]

            # Verify element exists in RTL
            matched_module = None
            if elem_clean in module_map:
                matched_module = elem_clean
            elif elem_leaf in module_map:
                matched_module = elem_leaf
            elif elem_clean in all_instances:
                matched_module = all_instances[elem_clean]
            elif elem_leaf in all_instances:
                matched_module = all_instances[elem_leaf]

            if matched_module:
                resolved_hierarchy[elem_clean] = dom.name
                resolved_hierarchy[matched_module] = dom.name
            else:
                # Element in UPF does not exist in RTL hierarchy!
                validation_issues.append(UPFValidationIssue(
                    severity="error",
                    issue_type="missing_element",
                    description=(
                        f"UPF domain '{dom.name}' references element '{elem}', but no matching "
                        f"module or instance was found in RTL hierarchy."
                    ),
                    file=primary_upf_file,
                    element=elem,
                ))

    # Map remaining modules (including top) to default domain
    for m in rtl_knowledge.modules:
        if m.name not in resolved_hierarchy and top_domain:
            resolved_hierarchy[m.name] = top_domain.name

    # ── 2. Discover Domain Crossings from RTL Port Interconnections ───
    # Check top-level and parent instantiations where two modules talk to each other
    for parent_mod in rtl_knowledge.modules:
        parent_domain = resolved_hierarchy.get(parent_mod.name, top_domain.name if top_domain else "DEFAULT")

        for inst in parent_mod.instantiations:
            child_mod_name = inst.get("module", "")
            child_inst_name = inst.get("instance", "")
            child_mod = module_map.get(child_mod_name)
            if not child_mod:
                continue

            child_domain = (
                resolved_hierarchy.get(child_inst_name)
                or resolved_hierarchy.get(child_mod_name)
                or parent_domain
            )

            # Check if crossing occurs between parent domain and child domain
            if child_domain != parent_domain:
                for port in child_mod.ports:
                    is_output = port.direction == "output"
                    src_dom = child_domain if is_output else parent_domain
                    dst_dom = parent_domain if is_output else child_domain

                    # Look for isolation strategy covering this domain & port
                    has_iso = False
                    iso_strat_name = ""
                    for iso in isolation_strategies:
                        if iso.domain == src_dom:
                            if not iso.elements or port.name in iso.elements:
                                has_iso = True
                                iso_strat_name = iso.name
                                break

                    # Look for level shifter covering this domain & port
                    has_ls = False
                    ls_strat_name = ""
                    for ls in level_shifter_strategies:
                        if ls.domain == src_dom or ls.domain == dst_dom:
                            if not ls.elements or port.name in ls.elements:
                                has_ls = True
                                ls_strat_name = ls.name
                                break

                    crossing_issues = []
                    # Check if switch exists (can power down) without isolation
                    src_is_switchable = any(sw.domain == src_dom for sw in power_switches)
                    if src_is_switchable and not has_iso:
                        issue_msg = (
                            f"Signal '{port.name}' from switchable domain '{src_dom}' to '{dst_dom}' "
                            f"lacks an isolation strategy (missing clamp when '{src_dom}' is OFF)."
                        )
                        crossing_issues.append(issue_msg)
                        validation_issues.append(UPFValidationIssue(
                            severity="error",
                            issue_type="missing_isolation",
                            description=issue_msg,
                            file=child_mod.file,
                            element=port.name,
                        ))

                    domain_crossings.append(DomainCrossing(
                        signal=port.name,
                        width=port.width,
                        source_domain=src_dom,
                        dest_domain=dst_dom,
                        source_module=child_mod.name if is_output else parent_mod.name,
                        dest_module=parent_mod.name if is_output else child_mod.name,
                        has_isolation=has_iso,
                        isolation_strategy=iso_strat_name,
                        has_level_shifter=has_ls,
                        level_shifter_strategy=ls_strat_name,
                        issues=crossing_issues,
                    ))

    # ── 3. Retention Verification ─────────────────────────────────────
    for sw in power_switches:
        # Domain has power gating. Check if it has a retention strategy
        has_ret = any(ret.domain == sw.domain for ret in retention_strategies)
        if not has_ret:
            validation_issues.append(UPFValidationIssue(
                severity="warning",
                issue_type="retention_hazard",
                description=(
                    f"Power domain '{sw.domain}' is switchable (power switch '{sw.name}'), "
                    f"but no retention strategy is specified. Sequential state will be lost on power-down."
                ),
                file=primary_upf_file,
                element=sw.domain,
            ))
        else:
            # Check save/restore control signals
            for ret in retention_strategies:
                if ret.domain == sw.domain:
                    if not ret.save_signal or not ret.restore_signal:
                        validation_issues.append(UPFValidationIssue(
                            severity="error",
                            issue_type="retention_hazard",
                            description=(
                                f"Retention strategy '{ret.name}' for domain '{ret.domain}' "
                                f"must define both save_signal and restore_signal."
                            ),
                            file=primary_upf_file,
                            element=ret.name,
                        ))

    # ── 4. Power State Table (PST) Consistency Checks ─────────────────
    for pst in power_state_tables:
        if not pst.states:
            validation_issues.append(UPFValidationIssue(
                severity="warning",
                issue_type="pst_violation",
                description=f"Power state table '{pst.name}' contains no declared states.",
                file=primary_upf_file,
                element=pst.name,
            ))

    return resolved_hierarchy, domain_crossings
