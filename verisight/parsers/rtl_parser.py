"""
RTL Parser for VeriSight.

Parses SystemVerilog RTL source files and extracts structured knowledge
including module declarations, ports, parameters, always blocks, FSMs,
clock domains, reset logic, and inline assertions.

This is a deterministic, regex+heuristic parser — no LLM calls.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from verisight.schemas.rtl_schema import (
    RTLKnowledge, RTLModule, Port, Parameter, AlwaysBlock,
    FSM, FSMState, FSMTransition, ClockDomain, RTLAssertion,
)
from verisight.utils.file_utils import read_file, discover_files, RTL_EXTENSIONS
from verisight.utils.sv_lexer import strip_comments
from verisight.utils.logger import get_logger

logger = get_logger("rtl_parser")


def parse_rtl(path: str) -> RTLKnowledge:
    """
    Parse RTL source files from a file or directory.

    Args:
        path: Path to a single .sv/.v file or directory containing RTL files.

    Returns:
        RTLKnowledge Pydantic model.
    """
    logger.info(f"Parsing RTL: {path}")
    p = Path(path)

    if p.is_file():
        files = [p]
    else:
        files = discover_files(p, RTL_EXTENSIONS)

    modules = []
    file_list = []
    total_lines = 0

    for f in files:
        file_list.append(str(f))
        content = read_file(f)
        if not content:
            continue
        total_lines += content.count("\n") + 1
        file_modules = _parse_file(str(f), content)
        modules.extend(file_modules)

    # Detect top module (module that isn't instantiated by others)
    instantiated = set()
    for m in modules:
        for inst in m.instantiations:
            instantiated.add(inst.get("module", ""))
    top_candidates = [m.name for m in modules if m.name not in instantiated]
    top_module = top_candidates[0] if top_candidates else ""

    # Collect global issues
    global_issues = []
    for m in modules:
        for ab in m.always_blocks:
            global_issues.extend(ab.issues)

    knowledge = RTLKnowledge(
        modules=modules,
        top_module=top_module,
        file_list=file_list,
        total_lines=total_lines,
        global_issues=global_issues,
    )

    logger.info(
        f"RTL parsed: {len(modules)} modules, {total_lines} lines, "
        f"top={top_module}, {len(global_issues)} issues"
    )
    return knowledge


def _parse_file(filepath: str, content: str) -> List[RTLModule]:
    """Parse all modules from a single file."""
    modules = []
    clean = strip_comments(content)
    lines = content.splitlines()

    # Find all module declarations
    module_pattern = re.compile(
        r"module\s+(\w+)\s*(?:#\s*\([\s\S]*?\))?\s*\([\s\S]*?\)\s*;",
        re.MULTILINE
    )

    for match in module_pattern.finditer(clean):
        mod_name = match.group(1)
        mod_start = content[:match.start()].count("\n") + 1

        # Find matching endmodule
        endmod = re.search(
            r"\bendmodule\b",
            clean[match.start():]
        )
        if endmod:
            mod_end_offset = match.start() + endmod.end()
            mod_content = clean[match.start():mod_end_offset]
            mod_raw = content[match.start():mod_end_offset]
            mod_end = content[:mod_end_offset].count("\n") + 1
        else:
            mod_content = clean[match.start():]
            mod_raw = content[match.start():]
            mod_end = len(lines)

        module = RTLModule(
            name=mod_name,
            file=filepath,
            ports=_extract_ports(mod_content),
            parameters=_extract_parameters(mod_content),
            always_blocks=_extract_always_blocks(mod_content, mod_raw, mod_start),
            fsms=_extract_fsms(mod_content, mod_name),
            clock_domains=_extract_clock_domains(mod_content),
            assignments=_extract_assignments(mod_content),
            instantiations=_extract_instantiations(mod_content, filepath),
            assertions=_extract_assertions(mod_content, filepath, mod_start),
            raw_source=mod_raw,
            line_count=mod_end - mod_start + 1,
        )
        modules.append(module)

    return modules


def _extract_ports(content: str) -> List[Port]:
    """Extract port declarations from module content."""
    ports = []
    # Match port declarations: input/output/inout [type] [width] name
    port_pattern = re.compile(
        r"(input|output|inout)\s+"
        r"(?:(wire|reg|logic)\s+)?"
        r"(?:(\[[\d:]+\])\s+)?"
        r"(\w+)",
        re.MULTILINE
    )

    for match in port_pattern.finditer(content):
        direction = match.group(1)
        sig_type = match.group(2) or "logic"
        width = match.group(3) or "1"
        name = match.group(4)

        ports.append(Port(
            name=name,
            direction=direction,
            width=width,
            signal_type=sig_type,
        ))

    return ports


def _extract_parameters(content: str) -> List[Parameter]:
    """Extract parameter and localparam declarations."""
    params = []
    param_pattern = re.compile(
        r"(parameter|localparam)\s+"
        r"(?:(\w+)\s+)?"  # optional type
        r"(\w+)\s*=\s*([^;,\)]+)",
        re.MULTILINE
    )

    for match in param_pattern.finditer(content):
        params.append(Parameter(
            name=match.group(3),
            value=match.group(4).strip(),
            param_type=match.group(1),
            data_type=match.group(2) or "",
        ))

    return params


def _extract_always_blocks(
    content: str, raw_content: str, module_start_line: int
) -> List[AlwaysBlock]:
    """Extract and classify always blocks."""
    blocks = []

    # Pattern for always blocks with different sensitivities
    always_pattern = re.compile(
        r"(always_ff|always_comb|always_latch|always)\s*"
        r"(?:@\s*\(([^)]*)\))?\s*"
        r"(begin\b)",
        re.MULTILINE
    )

    for match in always_pattern.finditer(content):
        keyword = match.group(1)
        sensitivity = match.group(2) or ""
        begin_pos = match.start(3)

        # Find matching 'end'
        block_content = _find_matching_block(content, begin_pos)
        block_start_line = module_start_line + content[:match.start()].count("\n")
        block_end_line = module_start_line + content[:begin_pos + len(block_content)].count("\n")

        # Classify block type
        block_type, clock, reset, reset_active = _classify_always(
            keyword, sensitivity, block_content
        )

        # Extract signals written and read
        signals_written = _extract_lhs_signals(block_content)
        signals_read = _extract_rhs_signals(block_content, signals_written)

        # Check for common issues
        issues = _check_always_issues(
            block_type, sensitivity, block_content, signals_written
        )

        has_reset = bool(re.search(
            r"if\s*\(\s*!?\s*\w*(?:rst|reset)\w*\s*\)", block_content, re.IGNORECASE
        ))

        blocks.append(AlwaysBlock(
            block_type=block_type,
            sensitivity_list=sensitivity.strip(),
            clock_signal=clock,
            reset_signal=reset,
            reset_active=reset_active,
            signals_written=signals_written,
            signals_read=signals_read,
            has_reset=has_reset,
            line_start=block_start_line,
            line_end=block_end_line,
            raw_code=block_content[:1000],  # cap to avoid huge strings
            issues=issues,
        ))

    return blocks


def _classify_always(
    keyword: str, sensitivity: str, body: str
) -> Tuple[str, str, str, str]:
    """
    Classify an always block as sequential, combinational, or latch.

    Returns (block_type, clock_signal, reset_signal, reset_active_level).
    """
    clock = ""
    reset = ""
    reset_active = ""

    if keyword == "always_ff":
        block_type = "sequential"
        clk_match = re.search(r"posedge\s+(\w+)", sensitivity)
        if clk_match:
            clock = clk_match.group(1)
        rst_match = re.search(r"(?:posedge|negedge)\s+(\w*(?:rst|reset)\w*)", sensitivity, re.IGNORECASE)
        if rst_match:
            reset = rst_match.group(1)
            reset_active = "low" if "negedge" in sensitivity.split(reset)[0].rsplit("posedge", 1)[-1] if reset in sensitivity else "" else "high"
    elif keyword == "always_comb":
        block_type = "combinational"
    elif keyword == "always_latch":
        block_type = "latch"
    else:
        # Plain 'always' — classify by sensitivity list
        if re.search(r"posedge|negedge", sensitivity):
            block_type = "sequential"
            clk_match = re.search(r"posedge\s+(\w+)", sensitivity)
            if clk_match:
                clock = clk_match.group(1)
            rst_match = re.search(r"(?:posedge|negedge)\s+(\w*(?:rst|reset)\w*)", sensitivity, re.IGNORECASE)
            if rst_match:
                reset = rst_match.group(1)
                reset_active = "high" if f"posedge {reset}" in sensitivity else "low"
        elif sensitivity == "*" or not sensitivity:
            block_type = "combinational"
        else:
            block_type = "combinational"

    return block_type, clock, reset, reset_active


def _extract_lhs_signals(block: str) -> List[str]:
    """Extract signals on the left-hand side of assignments."""
    lhs = re.findall(r"(\w+)\s*<=|(\w+)\s*=(?!=)", block)
    signals = set()
    for groups in lhs:
        for g in groups:
            if g and g not in ("if", "else", "case", "begin", "end", "for"):
                signals.add(g)
    return sorted(signals)


def _extract_rhs_signals(block: str, lhs_signals: List[str]) -> List[str]:
    """Extract signals on the right-hand side (read signals)."""
    identifiers = set(re.findall(r"\b([a-zA-Z_]\w*)\b", block))
    keywords = {
        "if", "else", "case", "begin", "end", "for", "default",
        "posedge", "negedge", "always", "always_ff", "always_comb",
        "endcase", "endmodule", "input", "output", "logic", "reg", "wire",
    }
    rhs = identifiers - set(lhs_signals) - keywords
    return sorted(rhs)


def _check_always_issues(
    block_type: str, sensitivity: str, body: str, written: List[str]
) -> List[str]:
    """Check for common issues in an always block."""
    issues = []

    if block_type == "sequential":
        # Check for blocking assignments in sequential block
        if re.search(r"\w+\s*=[^=]", body) and not re.search(r"<=", body):
            issues.append("blocking_assignment_in_sequential: Uses = instead of <= in sequential block")

    if block_type == "combinational":
        # Check for non-blocking assignments in combinational block
        if re.search(r"<=", body):
            issues.append("nonblocking_in_combinational: Uses <= in combinational block")

        # Check for incomplete sensitivity list (only for plain 'always')
        if sensitivity and sensitivity != "*" and "posedge" not in sensitivity:
            issues.append("incomplete_sensitivity: Sensitivity list may be incomplete, use always @(*) or always_comb")

    # Check for inferred latch (if without else in combinational)
    if block_type == "combinational":
        if_count = len(re.findall(r"\bif\b", body))
        else_count = len(re.findall(r"\belse\b", body))
        if if_count > else_count:
            issues.append("potential_latch: if without else may infer latch")

    # Check for missing default in case
    if re.search(r"\bcase\b", body) and not re.search(r"\bdefault\b", body):
        issues.append("missing_case_default: case statement without default")

    return issues


def _find_matching_block(content: str, begin_pos: int) -> str:
    """Find content between matching begin/end."""
    depth = 0
    i = begin_pos
    while i < len(content):
        if content[i:i+5] == "begin":
            depth += 1
            i += 5
        elif content[i:i+3] == "end" and (i + 3 >= len(content) or not content[i+3].isalnum()):
            depth -= 1
            if depth == 0:
                return content[begin_pos:i + 3]
            i += 3
        else:
            i += 1
    return content[begin_pos:]


def _extract_fsms(content: str, module_name: str) -> List[FSM]:
    """Extract finite state machines from case statements on enum/parameter states."""
    fsms = []

    # Find parameter/localparam state definitions
    state_defs: Dict[str, List[FSMState]] = {}
    # Pattern: parameter IDLE = 2'b00, RUN = 2'b01, ...
    enum_pattern = re.compile(
        r"(?:typedef\s+enum\s+(?:logic\s*\[[\d:]+\]\s*)?\{([^}]+)\}\s*(\w+))|"
        r"(?:(?:parameter|localparam)\s+(\w+)\s*=\s*\d+'[bhd]?\d+)",
        re.MULTILINE
    )

    # Find case statements that look like FSMs
    case_pattern = re.compile(
        r"case\s*\(\s*(\w+)\s*\)([\s\S]*?)endcase",
        re.MULTILINE
    )

    for case_match in case_pattern.finditer(content):
        state_var = case_match.group(1)
        case_body = case_match.group(2)

        # Extract state labels from case items
        case_items = re.findall(
            r"(\w+)\s*:\s*([\s\S]*?)(?=\w+\s*:|default\s*:|$)",
            case_body
        )

        if len(case_items) < 2:
            continue  # Not enough states for an FSM

        states = []
        transitions = []

        for state_name, state_body in case_items:
            if state_name in ("default",):
                continue
            states.append(FSMState(name=state_name))

            # Find next-state assignments
            next_state_matches = re.findall(
                r"(\w+)\s*<=?\s*(\w+)\s*;",
                state_body
            )
            for lhs, rhs in next_state_matches:
                if lhs == state_var or lhs.startswith("next_") or lhs.endswith("_next"):
                    transitions.append(FSMTransition(
                        from_state=state_name,
                        to_state=rhs,
                    ))

        has_default = "default" in case_body

        if states:
            fsms.append(FSM(
                name=f"{module_name}_{state_var}",
                state_variable=state_var,
                states=states,
                transitions=transitions,
                has_default=has_default,
            ))

    return fsms


def _extract_clock_domains(content: str) -> List[ClockDomain]:
    """Extract clock domains from always block sensitivities."""
    domains: Dict[str, List[str]] = {}
    domain_resets: Dict[str, str] = {}

    # Find all posedge clock references
    always_pattern = re.compile(
        r"always(?:_ff)?\s*@\s*\(([^)]+)\)\s*begin([\s\S]*?)end",
        re.MULTILINE
    )

    for match in always_pattern.finditer(content):
        sensitivity = match.group(1)
        body = match.group(2)

        clk_match = re.search(r"posedge\s+(\w+)", sensitivity)
        if clk_match:
            clk = clk_match.group(1)
            if clk not in domains:
                domains[clk] = []

            # Add signals assigned in this block
            written = _extract_lhs_signals(body)
            domains[clk].extend(written)

            # Check for reset
            rst_match = re.search(r"(?:posedge|negedge)\s+(\w*(?:rst|reset)\w*)", sensitivity, re.IGNORECASE)
            if rst_match:
                domain_resets[clk] = rst_match.group(1)

    return [
        ClockDomain(
            clock_signal=clk,
            signals=sorted(set(sigs)),
            reset_signal=domain_resets.get(clk, ""),
        )
        for clk, sigs in domains.items()
    ]


def _extract_assignments(content: str) -> List[str]:
    """Extract continuous assign statements."""
    assigns = re.findall(r"assign\s+(.+?);", content)
    return [a.strip() for a in assigns]


def _extract_instantiations(content: str, filepath: str) -> List[Dict[str, str]]:
    """Extract module instantiations."""
    instances = []
    # Pattern: module_name [#(params)] instance_name (ports);
    inst_pattern = re.compile(
        r"(\w+)\s+(?:#\s*\([^)]*\)\s+)?(\w+)\s*\(",
        re.MULTILINE
    )

    # Keywords that aren't module instantiations
    not_modules = {
        "module", "function", "task", "if", "else", "case", "for",
        "while", "assign", "always", "initial", "begin", "end",
        "input", "output", "inout", "wire", "reg", "logic",
        "parameter", "localparam", "generate", "integer",
        "always_ff", "always_comb", "always_latch",
    }

    for match in inst_pattern.finditer(content):
        mod_name = match.group(1)
        inst_name = match.group(2)
        if mod_name not in not_modules and not mod_name.startswith("$"):
            instances.append({
                "module": mod_name,
                "instance": inst_name,
                "file": filepath,
            })

    return instances


def _extract_assertions(
    content: str, filepath: str, module_start: int
) -> List[RTLAssertion]:
    """Extract inline assertions."""
    assertions = []
    assert_pattern = re.compile(
        r"(?:(\w+)\s*:\s*)?(assert|assume|cover)\s+(?:property\s*)?\(([^;]+)\)\s*;",
        re.MULTILINE
    )

    for match in assert_pattern.finditer(content):
        label = match.group(1) or ""
        atype = match.group(2)
        expr = match.group(3).strip()
        line = module_start + content[:match.start()].count("\n")

        assertions.append(RTLAssertion(
            assertion_type=atype,
            name=label,
            expression=expr,
            line_number=line,
            file=filepath,
        ))

    return assertions
