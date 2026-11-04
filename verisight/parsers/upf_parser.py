"""
UPF (Unified Power Format — IEEE 1801) Parser for VeriSight.

Parses power intent specifications (.upf files) and extracts:
- Power domains (with hierarchical scoping and element binding)
- Supply ports, nets, and supply sets
- Power switches (gating logic and control/ack signals)
- Isolation strategies (clamp values, applies_to, control signals)
- Level shifter strategies (voltage domain rules, boundaries)
- Retention strategies (save/restore controls, retention supply nets)
- Power State Tables (PST) and power states

Resolves UPF power domains against the actual RTL design hierarchy,
providing rich structured diagnostics for invalid syntax or hierarchy mismatches.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Optional, Sequence, Union, Tuple, Any

from verisight.schemas.upf_schema import (
    UPFKnowledge,
    PowerDomain,
    SupplyPort,
    SupplyNet,
    SupplySet,
    PowerSwitch,
    IsolationStrategy,
    LevelShifterStrategy,
    RetentionStrategy,
    PowerStateTable,
    PowerState,
    UPFDiagnostic,
)
from verisight.schemas.rtl_schema import RTLKnowledge
from verisight.utils.file_utils import read_file, discover_files, UPF_EXTENSIONS
from verisight.utils.logger import get_logger

logger = get_logger("upf_parser")


def _tokenize_upf_line(text: str) -> List[str]:
    """
    Tokenize a UPF/Tcl command line respecting {braced} and "quoted" groups.
    """
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        # Skip whitespace
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break

        char = text[i]
        if char == "{":
            # Match balanced braces
            depth = 1
            start = i + 1
            i += 1
            while i < n and depth > 0:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
            token_content = text[start:i-1 if depth == 0 else i].strip()
            tokens.append(token_content)
        elif char == '"':
            # Match quoted string
            start = i + 1
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            token_content = text[start:i].strip()
            if i < n and text[i] == '"':
                i += 1
            tokens.append(token_content)
        else:
            # Regular token until next whitespace
            start = i
            while i < n and not text[i].isspace() and text[i] not in "{}\"":
                i += 1
            token_content = text[start:i].strip()
            if token_content:
                tokens.append(token_content)
    return tokens


def _join_upf_lines(raw_content: str) -> List[Tuple[int, str]]:
    """
    Strips line-end comments (#) and joins lines ending in backslash (\\).
    Returns list of (start_line_no, command_str).
    """
    commands: List[Tuple[int, str]] = []
    current_cmd: List[str] = []
    current_start_line = 0

    lines = raw_content.splitlines()
    for idx, line in enumerate(lines, start=1):
        # Strip comments unless inside quotes/braces
        clean_line = line
        if "#" in line:
            # Simple comment strip outside braces/quotes
            in_quote = False
            brace_count = 0
            cut_idx = len(line)
            for c_i, c in enumerate(line):
                if c == '"':
                    in_quote = not in_quote
                elif c == '{' and not in_quote:
                    brace_count += 1
                elif c == '}' and not in_quote:
                    brace_count = max(0, brace_count - 1)
                elif c == '#' and not in_quote and brace_count == 0:
                    cut_idx = c_i
                    break
            clean_line = line[:cut_idx]

        clean_line = clean_line.strip()
        if not clean_line:
            continue

        if not current_cmd:
            current_start_line = idx

        if clean_line.endswith("\\"):
            current_cmd.append(clean_line[:-1].strip())
        else:
            current_cmd.append(clean_line)
            full_statement = " ".join(current_cmd).strip()
            # Split semicolon-delimited commands
            for part in full_statement.split(";"):
                part_clean = part.strip()
                if part_clean:
                    commands.append((current_start_line, part_clean))
            current_cmd = []

    if current_cmd:
        full_statement = " ".join(current_cmd).strip()
        for part in full_statement.split(";"):
            part_clean = part.strip()
            if part_clean:
                commands.append((current_start_line, part_clean))

    return commands


def _parse_named_args(tokens: List[str]) -> Tuple[List[str], Dict[str, Any]]:
    """
    Parse a list of command tokens into positional arguments and a dict of flag -> value.
    Flags without value are treated as boolean True.
    """
    positional = []
    kwargs = {}
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.startswith("-"):
            flag = tok.lstrip("-")
            # Check if next token exists and is not a flag
            if i + 1 < n and not tokens[i + 1].startswith("-"):
                val = tokens[i + 1]
                # If val has multiple items or is braced, split into list
                kwargs[flag] = val
                i += 2
            else:
                kwargs[flag] = True
                i += 1
        else:
            positional.append(tok)
            i += 1
    return positional, kwargs


def parse_upf(
    paths: Union[str, Path, Sequence[Union[str, Path]]],
    rtl_knowledge: Optional[RTLKnowledge] = None,
) -> UPFKnowledge:
    """
    Parse UPF power intent specification file(s) and correlate against RTL hierarchy.

    Args:
        paths: Single path, directory, or sequence of UPF file paths.
        rtl_knowledge: Optional parsed RTL knowledge to resolve hierarchy & cross-check.

    Returns:
        UPFKnowledge populated with domains, strategies, and diagnostics.
    """
    # 1. Resolve all input files
    target_files: List[Path] = []
    if isinstance(paths, (str, Path)):
        p = Path(paths)
        if p.is_dir():
            target_files.extend(discover_files(p, UPF_EXTENSIONS))
        elif p.exists():
            target_files.append(p)
        else:
            logger.warning(f"UPF file not found: {paths}")
    elif isinstance(paths, Sequence):
        for item in paths:
            p = Path(item)
            if p.is_dir():
                target_files.extend(discover_files(p, UPF_EXTENSIONS))
            elif p.exists():
                target_files.append(p)
            else:
                logger.warning(f"UPF file not found: {item}")

    file_paths_str = [str(f) for f in target_files]
    knowledge = UPFKnowledge(file_paths=file_paths_str)

    if not target_files:
        if paths:
            knowledge.diagnostics.append(UPFDiagnostic(
                severity="error",
                message=f"Provided UPF file path does not exist: {paths}",
                file=str(paths),
                code="UPF_FILE_NOT_FOUND",
            ))
            knowledge.is_valid = False
        return knowledge

    current_scope = ""

    # 2. Parse UPF files
    for upf_file in target_files:
        raw = read_file(upf_file)
        if not raw or not raw.strip():
            knowledge.diagnostics.append(UPFDiagnostic(
                severity="warning",
                message=f"UPF file '{upf_file.name}' is empty.",
                file=str(upf_file),
                line_number=1,
                code="UPF_EMPTY_FILE",
            ))
            continue

        commands = _join_upf_lines(raw)
        for line_no, cmd_str in commands:
            tokens = _tokenize_upf_line(cmd_str)
            if not tokens:
                continue

            cmd = tokens[0].lower()
            pos_args, kwargs = _parse_named_args(tokens[1:])

            try:
                if cmd == "set_scope":
                    current_scope = pos_args[0] if pos_args else kwargs.get("scope", "")

                elif cmd == "create_power_domain":
                    domain_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    if not domain_name:
                        knowledge.diagnostics.append(UPFDiagnostic(
                            severity="error",
                            message="Missing power domain name in 'create_power_domain'",
                            file=str(upf_file),
                            line_number=line_no,
                            code="UPF_SYNTAX_DOMAIN",
                        ))
                        knowledge.is_valid = False
                        continue

                    raw_elements = kwargs.get("elements", "")
                    elements = []
                    if raw_elements:
                        if isinstance(raw_elements, str):
                            elements = raw_elements.replace("{", "").replace("}", "").split()
                        elif isinstance(raw_elements, list):
                            elements = [str(x) for x in raw_elements]

                    is_top = (
                        "include_scope" in kwargs
                        or domain_name.upper() in ("TOP", "DEFAULT", "PD_TOP")
                        or not elements
                    )

                    domain = PowerDomain(
                        name=domain_name,
                        scope=kwargs.get("scope", current_scope),
                        elements=elements,
                        is_top=is_top,
                        include_scope="include_scope" in kwargs,
                        file=str(upf_file),
                        line_number=line_no,
                    )
                    knowledge.power_domains.append(domain)

                elif cmd == "create_supply_port":
                    port_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    direction = kwargs.get("direction", "in")
                    domain = kwargs.get("domain", None)
                    knowledge.supply_ports.append(SupplyPort(
                        name=port_name,
                        direction=direction,
                        domain=domain,
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "create_supply_net":
                    net_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    domain = kwargs.get("domain", None)
                    is_reuse = "reuse" in kwargs
                    knowledge.supply_nets.append(SupplyNet(
                        name=net_name,
                        domain=domain,
                        is_reuse=is_reuse,
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "connect_supply_net":
                    net_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    raw_ports = kwargs.get("ports", "")
                    ports = []
                    if raw_ports:
                        if isinstance(raw_ports, str):
                            ports = raw_ports.replace("{", "").replace("}", "").split()
                        elif isinstance(raw_ports, list):
                            ports = [str(p) for p in raw_ports]
                    for sn in knowledge.supply_nets:
                        if sn.name == net_name:
                            sn.connected_ports.extend(ports)

                elif cmd == "create_supply_set":
                    set_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    p_net = ""
                    g_net = ""
                    func_spec = kwargs.get("function", "")
                    if isinstance(func_spec, str):
                        parts = func_spec.split()
                        if "power" in parts and len(parts) > parts.index("power") + 1:
                            p_net = parts[parts.index("power") + 1]
                        if "ground" in parts and len(parts) > parts.index("ground") + 1:
                            g_net = parts[parts.index("ground") + 1]
                    knowledge.supply_sets.append(SupplySet(
                        name=set_name,
                        power_net=p_net,
                        ground_net=g_net,
                        domain=kwargs.get("domain", None),
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "set_domain_supply_net":
                    dom_name = pos_args[0] if pos_args else kwargs.get("domain", "")
                    p_net = kwargs.get("primary_power_net", "")
                    g_net = kwargs.get("primary_ground_net", "")
                    found = False
                    for pd in knowledge.power_domains:
                        if pd.name == dom_name:
                            pd.primary_power_net = p_net
                            pd.primary_ground_net = g_net
                            found = True
                    if not found and dom_name:
                        knowledge.diagnostics.append(UPFDiagnostic(
                            severity="warning",
                            message=f"set_domain_supply_net references undeclared power domain '{dom_name}'",
                            file=str(upf_file),
                            line_number=line_no,
                            code="UPF_UNRESOLVED_DOMAIN",
                        ))

                elif cmd == "create_power_switch":
                    sw_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    dom = kwargs.get("domain", "")
                    in_port = str(kwargs.get("input_supply_port", "")).replace("{", "").replace("}", "").strip()
                    out_port = str(kwargs.get("output_supply_port", "")).replace("{", "").replace("}", "").strip()
                    ctrl = str(kwargs.get("control_port", "")).replace("{", "").replace("}", "").strip()
                    ack = str(kwargs.get("ack_port", "")).replace("{", "").replace("}", "").strip()
                    on_st = str(kwargs.get("on_state", "")).replace("{", "").replace("}", "").strip()

                    knowledge.power_switches.append(PowerSwitch(
                        name=sw_name,
                        domain=dom,
                        input_supply_port=in_port,
                        output_supply_port=out_port,
                        control_port=ctrl,
                        ack_port=ack,
                        on_state=on_st,
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "set_isolation":
                    iso_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    dom = kwargs.get("domain", "")
                    clamp = str(kwargs.get("clamp_value", "0")).lower()
                    applies = str(kwargs.get("applies_to", "outputs")).lower()
                    loc = str(kwargs.get("location", "self")).lower()
                    raw_elem = kwargs.get("elements", "")
                    elems = []
                    if raw_elem:
                        elems = str(raw_elem).replace("{", "").replace("}", "").split()

                    sig = kwargs.get("isolation_signal", "")
                    sense = kwargs.get("isolation_sense", "high")

                    knowledge.isolation_strategies.append(IsolationStrategy(
                        name=iso_name,
                        domain=dom,
                        clamp_value=clamp,
                        applies_to=applies,
                        location=loc,
                        elements=elems,
                        isolation_signal=sig,
                        isolation_sense=sense,
                        isolation_power_net=kwargs.get("isolation_power_net", ""),
                        isolation_ground_net=kwargs.get("isolation_ground_net", ""),
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "set_isolation_control":
                    iso_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    sig = str(kwargs.get("isolation_signal", ""))
                    sense = str(kwargs.get("isolation_sense", "high"))
                    found = False
                    for iso in knowledge.isolation_strategies:
                        if iso.name == iso_name:
                            iso.isolation_signal = sig
                            iso.isolation_sense = sense
                            found = True
                    if not found and iso_name:
                        knowledge.diagnostics.append(UPFDiagnostic(
                            severity="warning",
                            message=f"set_isolation_control references undeclared isolation strategy '{iso_name}'",
                            file=str(upf_file),
                            line_number=line_no,
                            code="UPF_UNRESOLVED_STRATEGY",
                        ))

                elif cmd == "set_level_shifter":
                    ls_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    dom = kwargs.get("domain", "")
                    applies = str(kwargs.get("applies_to", "inputs")).lower()
                    rule = str(kwargs.get("rule", "both")).lower()
                    loc = str(kwargs.get("location", "self")).lower()
                    raw_elem = kwargs.get("elements", "")
                    elems = []
                    if raw_elem:
                        elems = str(raw_elem).replace("{", "").replace("}", "").split()

                    knowledge.level_shifters.append(LevelShifterStrategy(
                        name=ls_name,
                        domain=dom,
                        applies_to=applies,
                        rule=rule,
                        location=loc,
                        elements=elems,
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "set_retention":
                    ret_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    dom = kwargs.get("domain", "")
                    p_net = kwargs.get("retention_power_net", "")
                    g_net = kwargs.get("retention_ground_net", "")
                    save = str(kwargs.get("save_signal", "")).replace("{", "").replace("}", "")
                    restore = str(kwargs.get("restore_signal", "")).replace("{", "").replace("}", "")
                    raw_elem = kwargs.get("elements", "")
                    elems = []
                    if raw_elem:
                        elems = str(raw_elem).replace("{", "").replace("}", "").split()

                    knowledge.retention_strategies.append(RetentionStrategy(
                        name=ret_name,
                        domain=dom,
                        retention_power_net=p_net,
                        retention_ground_net=g_net,
                        save_signal=save,
                        restore_signal=restore,
                        elements=elems,
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "set_retention_control":
                    ret_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    save = str(kwargs.get("save_signal", "")).replace("{", "").replace("}", "")
                    restore = str(kwargs.get("restore_signal", "")).replace("{", "").replace("}", "")
                    for ret in knowledge.retention_strategies:
                        if ret.name == ret_name:
                            ret.save_signal = save
                            ret.restore_signal = restore

                elif cmd == "create_pst":
                    pst_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    raw_supplies = kwargs.get("supplies", "")
                    supplies = []
                    if raw_supplies:
                        supplies = str(raw_supplies).replace("{", "").replace("}", "").split()
                    knowledge.power_state_tables.append(PowerStateTable(
                        name=pst_name,
                        supplies=supplies,
                        states={},
                        file=str(upf_file),
                        line_number=line_no,
                    ))

                elif cmd == "add_pst_state":
                    st_name = pos_args[0] if pos_args else kwargs.get("name", "")
                    pst_target = kwargs.get("pst", "")
                    raw_st = kwargs.get("state", "")
                    supply_states = []
                    if raw_st:
                        supply_states = str(raw_st).replace("{", "").replace("}", "").split()
                    for pst in knowledge.power_state_tables:
                        if pst.name == pst_target:
                            pst.states[st_name] = supply_states

                elif cmd == "add_power_state":
                    target_obj = pos_args[0] if pos_args else kwargs.get("name", "")
                    state_name = kwargs.get("state", "")
                    is_off = "off" in cmd_str.lower()
                    knowledge.power_states.append(PowerState(
                        name=state_name or target_obj,
                        domain_or_pst=target_obj,
                        is_off=is_off,
                        file=str(upf_file),
                        line_number=line_no,
                    ))

            except Exception as e:
                knowledge.diagnostics.append(UPFDiagnostic(
                    severity="error",
                    message=f"Failed to parse UPF command '{cmd}': {e}",
                    file=str(upf_file),
                    line_number=line_no,
                    code="UPF_CMD_PARSE_ERROR",
                ))
                knowledge.is_valid = False

    # 3. Hierarchy Cross-Validation & RTL Mapping
    if rtl_knowledge is not None:
        validate_upf_against_rtl(knowledge, rtl_knowledge)

    logger.info(
        f"UPF Parsed: {len(knowledge.power_domains)} domains, "
        f"{len(knowledge.power_switches)} switches, "
        f"{len(knowledge.isolation_strategies)} isolation, "
        f"{len(knowledge.level_shifters)} level shifters, "
        f"{len(knowledge.retention_strategies)} retention, "
        f"{len(knowledge.diagnostics)} diagnostics"
    )

    return knowledge


def validate_upf_against_rtl(
    upf_knowledge: UPFKnowledge,
    rtl_knowledge: RTLKnowledge,
) -> List[UPFDiagnostic]:
    """
    Resolve and validate UPF power-domain hierarchy, elements, and control
    signals against the actual RTL design hierarchy.
    """
    diagnostics = upf_knowledge.diagnostics

    # 1. Collect all RTL module names, instance names, and signals
    rtl_modules_by_name = {m.name: m for m in rtl_knowledge.modules}
    top_module_name = rtl_knowledge.top_module or (rtl_knowledge.modules[0].name if rtl_knowledge.modules else "")

    # Instances mapped {instance_name: module_type}
    rtl_instances: Dict[str, str] = {}
    for m in rtl_knowledge.modules:
        for inst in m.instantiations:
            inst_name = inst.get("instance", "")
            mod_type = inst.get("module", "")
            if inst_name:
                rtl_instances[inst_name] = mod_type
                # Also include hierarchical dot paths
                rtl_instances[f"{m.name}.{inst_name}"] = mod_type

    # 2. Resolve power domain elements to RTL instances
    for pd in upf_knowledge.power_domains:
        if pd.is_top:
            if top_module_name:
                pd.associated_modules.append(top_module_name)
                upf_knowledge.resolved_hierarchy[top_module_name] = pd.name
                upf_knowledge.resolved_hierarchy["top"] = pd.name

        for elem in pd.elements:
            # Check if elem exists in RTL instances or modules
            clean_elem = elem.strip("{}")
            matched_mod = ""

            if clean_elem in rtl_instances:
                matched_mod = rtl_instances[clean_elem]
            elif any(clean_elem == inst_k.split(".")[-1] for inst_k in rtl_instances):
                for inst_k, mod_t in rtl_instances.items():
                    if inst_k.split(".")[-1] == clean_elem:
                        matched_mod = mod_t
                        break
            elif clean_elem in rtl_modules_by_name:
                matched_mod = clean_elem

            if matched_mod:
                pd.associated_modules.append(matched_mod)
                upf_knowledge.resolved_hierarchy[clean_elem] = pd.name
            else:
                diagnostics.append(UPFDiagnostic(
                    severity="warning",
                    message=(
                        f"Power domain '{pd.name}' references element '{clean_elem}' "
                        f"which was not found in RTL module hierarchy."
                    ),
                    file=pd.file,
                    line_number=pd.line_number,
                    code="UPF_ELEMENT_NOT_IN_RTL",
                ))

    # 3. Check power switch controls against RTL signals
    for ps in upf_knowledge.power_switches:
        ctrl = ps.control_port
        # Extract signal name if format is 'port signal'
        ctrl_sig = ctrl.split()[-1] if ctrl else ""
        if ctrl_sig and rtl_knowledge.modules:
            # Check if signal exists in any module port or assignment
            sig_basename = ctrl_sig.split(".")[-1].replace("!", "").replace("~", "")
            found = False
            for m in rtl_knowledge.modules:
                all_sigs = {p.name for p in m.ports}
                for ab in m.always_blocks:
                    all_sigs.update(ab.signals_written)
                    all_sigs.update(ab.signals_read)
                if sig_basename in all_sigs:
                    found = True
                    break
            if not found:
                diagnostics.append(UPFDiagnostic(
                    severity="warning",
                    message=(
                        f"Power switch '{ps.name}' control port '{ctrl_sig}' "
                        f"is not declared in RTL signals."
                    ),
                    file=ps.file,
                    line_number=ps.line_number,
                    code="UPF_SWITCH_CTRL_UNRESOLVED",
                ))

    # 4. Check isolation control signals
    for iso in upf_knowledge.isolation_strategies:
        sig = iso.isolation_signal
        if sig and rtl_knowledge.modules:
            sig_basename = sig.split(".")[-1].replace("!", "").replace("~", "")
            found = False
            for m in rtl_knowledge.modules:
                all_sigs = {p.name for p in m.ports}
                for ab in m.always_blocks:
                    all_sigs.update(ab.signals_written)
                    all_sigs.update(ab.signals_read)
                if sig_basename in all_sigs:
                    found = True
                    break
            if not found:
                diagnostics.append(UPFDiagnostic(
                    severity="warning",
                    message=(
                        f"Isolation strategy '{iso.name}' control signal '{sig}' "
                        f"is not declared in RTL signals."
                    ),
                    file=iso.file,
                    line_number=iso.line_number,
                    code="UPF_ISO_SIGNAL_UNRESOLVED",
                ))

    return diagnostics

