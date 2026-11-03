"""
RTL Parser for VeriSight.

Parses SystemVerilog RTL source files and extracts structured knowledge
including module declarations, ports, parameters, always blocks, FSMs,
clock domains, reset logic, and inline assertions.

Primary backend: pyslang (the Slang SystemVerilog frontend) via
``verisight.parsers.sv_frontend`` + ``pyslang_rtl``. This gives real
IEEE-1800 parsing with accurate types, signal dependencies, and source
locations.

Fallback: a deterministic regex+heuristic parser (the original
implementation, preserved below). It is only used when pyslang is
unavailable or produced no usable modules, and when it runs the result is
explicitly labelled ``degraded`` with the pyslang diagnostics preserved —
never a silent switch.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Sequence, Tuple, Union, Set

from verisight.schemas.rtl_schema import (
    RTLKnowledge, RTLModule, Port, Parameter, AlwaysBlock,
    FSM, FSMState, FSMTransition, ClockDomain, RTLAssertion,
)
from verisight.schemas.parser_schema import (
    ParserStatus, ParserDiagnostic, CATEGORY_TOOL,
    CATEGORY_MISSING_DEPENDENCY, SEVERITY_ERROR, SEVERITY_WARNING,
)
from verisight.utils.file_utils import read_file, discover_files, RTL_EXTENSIONS
from verisight.utils.sv_lexer import strip_comments
from verisight.utils.logger import get_logger
from verisight.parsers import sv_frontend
from verisight.parsers.pyslang_rtl import build_rtl_knowledge

logger = get_logger("rtl_parser")


def resolve_rtl_files(path: Union[str, Path, Sequence[Union[str, Path]]]) -> List[Path]:
    """Resolve single path, directory, or sequence of paths into existing file paths."""
    resolved_files: List[Path] = []
    seen = set()

    def _add_p(p_in: Path):
        try:
            r = p_in.resolve()
            if r not in seen and p_in.is_file() and p_in.suffix.lower() in RTL_EXTENSIONS:
                seen.add(r)
                resolved_files.append(p_in)
        except Exception:
            pass

    if isinstance(path, (str, Path)):
        p = Path(path)
        if p.is_file():
            _add_p(p)
        elif p.is_dir():
            for f in discover_files(p, RTL_EXTENSIONS):
                _add_p(f)
        else:
            # Check if multiple paths separated by commas or spaces
            parts = str(path).replace(",", " ").split()
            if len(parts) > 1:
                for part in parts:
                    sub_p = Path(part)
                    if sub_p.is_file():
                        _add_p(sub_p)
                    elif sub_p.is_dir():
                        for f in discover_files(sub_p, RTL_EXTENSIONS):
                            _add_p(f)
    elif isinstance(path, Sequence):
        for item in path:
            p = Path(item)
            if p.is_file():
                _add_p(p)
            elif p.is_dir():
                for f in discover_files(p, RTL_EXTENSIONS):
                    _add_p(f)

    return resolved_files


def order_rtl_sources(files: Sequence[Path]) -> Tuple[List[Path], List[str], List[str], List[str]]:
    """
    Analyzes multiple RTL files and determines compilation order:
    1. Header/include files (.svh, .vh)
    2. Packages (package ...; endpackage)
    3. Interfaces (interface ...; endinterface)
    4. Leaf submodules (modules instantiated by others)
    5. Top-level modules

    Also extracts defined packages, interfaces, and auto-include directories.
    """
    headers: List[Path] = []
    packages_files: List[Path] = []
    interfaces_files: List[Path] = []
    modules_files: List[Path] = []

    defined_packages: List[str] = []
    defined_interfaces: List[str] = []
    auto_incdirs: Set[str] = set()

    pkg_pattern = re.compile(r"\bpackage\s+(\w+)\s*;", re.MULTILINE)
    iface_pattern = re.compile(r"\binterface\s+(\w+)\s*(?:#|\()?", re.MULTILINE)
    mod_pattern = re.compile(r"\bmodule\s+(\w+)\s*(?:#|\()?", re.MULTILINE)
    inst_pattern = re.compile(r"\b(\w+)\s+(?:#\s*\([^)]*\)\s+)?(\w+)\s*\(", re.MULTILINE)

    file_meta: Dict[Path, Dict[str, Any]] = {}

    for f in files:
        auto_incdirs.add(str(f.parent.resolve()))
        suffix = f.suffix.lower()
        content = ""
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

        clean = strip_comments(content) if content else ""
        pkgs = pkg_pattern.findall(clean)
        ifaces = iface_pattern.findall(clean)
        mods = mod_pattern.findall(clean)

        defined_packages.extend(pkgs)
        defined_interfaces.extend(ifaces)

        if suffix in (".svh", ".vh"):
            headers.append(f)
        elif pkgs:
            packages_files.append(f)
        elif ifaces and not mods:
            interfaces_files.append(f)
        else:
            modules_files.append(f)

        file_meta[f] = {
            "pkgs": pkgs,
            "ifaces": ifaces,
            "mods": mods,
            "insts": [inst.get("module") for inst in _extract_instantiations(clean, str(f))],
        }

    # Dependency sort modules: submodules before instantiators
    ordered_mods: List[Path] = []
    visited = set()

    def _visit_mod(p: Path, stack: set):
        if p in visited:
            return
        stack.add(p)
        p_insts = set(file_meta.get(p, {}).get("insts", []))
        for other_p in modules_files:
            if other_p != p and other_p not in visited and other_p not in stack:
                other_mods = set(file_meta.get(other_p, {}).get("mods", []))
                if p_insts.intersection(other_mods):
                    _visit_mod(other_p, stack)
        stack.remove(p)
        visited.add(p)
        ordered_mods.append(p)

    for mf in modules_files:
        if mf not in visited:
            _visit_mod(mf, set())

    # Prioritize leaf modules (modules with 0 instantiations) before parent/top modules
    leaf_mods = [f for f in ordered_mods if not file_meta.get(f, {}).get("insts")]
    parent_mods = [f for f in ordered_mods if f not in leaf_mods]

    ordered_files = headers + packages_files + interfaces_files + leaf_mods + parent_mods
    return ordered_files, defined_packages, defined_interfaces, sorted(auto_incdirs)


def check_missing_dependencies(
    modules: List[RTLModule],
    defined_packages: Sequence[str],
    file_list: Optional[Sequence[Union[str, Path]]] = None,
) -> Tuple[List[str], List[ParserDiagnostic]]:
    """Detect instantiated modules that are missing from uploaded RTL."""
    missing: List[str] = []
    diags: List[ParserDiagnostic] = []
    defined_mods = {m.name for m in modules}
    verilog_primitives = {
        "and", "nand", "or", "nor", "xor", "xnor", "buf", "not",
        "bufif0", "bufif1", "notif0", "notif1", "pulldown", "pullup",
        "nmos", "pmos", "cmos", "rnmos", "rpmos", "rcmos", "tran",
        "rtran", "tranif0", "rtranif0", "tranif1", "rtranif1",
        "interface", "modport", "package", "typedef", "struct", "enum",
        "initial", "always", "assign", "begin", "end", "task", "function",
    }
    for m in modules:
        for inst in m.instantiations:
            inst_mod = inst.get("module", "")
            if (
                inst_mod
                and inst_mod not in defined_mods
                and inst_mod not in verilog_primitives
                and not inst_mod.startswith("$")
                and inst_mod not in missing
            ):
                missing.append(inst_mod)
                diags.append(ParserDiagnostic(
                    severity=SEVERITY_ERROR,
                    category=CATEGORY_MISSING_DEPENDENCY,
                    message=(
                        f"Module '{inst_mod}' instantiated in module '{m.name}' "
                        f"({m.file}) is not defined in any uploaded RTL source file."
                    ),
                    file=m.file,
                    code="MissingModuleDependency",
                ))

    # Also inspect raw source files for instantiations that could not be elaborated by AST
    if file_list:
        for f in file_list:
            content = read_file(f)
            clean = strip_comments(content) if content else ""
            file_insts = _extract_instantiations(clean, str(f))
            for inst in file_insts:
                inst_mod = inst.get("module", "")
                if (
                    inst_mod
                    and inst_mod not in defined_mods
                    and inst_mod not in verilog_primitives
                    and not inst_mod.startswith("$")
                    and inst_mod not in missing
                ):
                    missing.append(inst_mod)
                    diags.append(ParserDiagnostic(
                        severity=SEVERITY_ERROR,
                        category=CATEGORY_MISSING_DEPENDENCY,
                        message=(
                            f"Module '{inst_mod}' instantiated in file '{Path(f).name}' "
                            f"is not defined in any uploaded RTL source file."
                        ),
                        file=str(f),
                        code="MissingModuleDependency",
                    ))

    return sorted(set(missing)), diags


def parse_rtl(
    path: Union[str, Path, Sequence[Union[str, Path]]],
    include_dirs: Optional[Sequence[str]] = None,
    defines: Optional[Sequence[str]] = None,
    allow_fallback: bool = True,
    top_module: Optional[str] = None,
) -> RTLKnowledge:
    """
    Parse RTL source files from a file, directory, or sequence of files.

    Uses the pyslang frontend first; falls back to the legacy regex parser
    only when pyslang is unavailable or yields no modules.

    Args:
        path: Single file, directory, or sequence of .sv/.v/.vhd files.
        include_dirs: Optional `include search directories.
        defines: Optional macro defines ("NAME" or "NAME=value").
        allow_fallback: If True, fall back to the regex parser when pyslang
            is unavailable or finds no modules.
        top_module: Optional explicit top-level module selection.

    Returns:
        RTLKnowledge Pydantic model with dependency ordering and diagnostics.
    """
    logger.info(f"Parsing RTL: {path}")
    files = resolve_rtl_files(path)

    if not files:
        logger.warning(f"No RTL files resolved from path: {path}")
        pstatus = ParserStatus(
            backend="none",
            syntax_ok=False,
            degraded=True,
            diagnostics=[
                ParserDiagnostic(
                    severity=SEVERITY_ERROR,
                    category=CATEGORY_TOOL,
                    message=f"No RTL source files found at: {path}",
                    code="NoFilesFound",
                )
            ]
        )
        return RTLKnowledge(parser_status=pstatus)

    ordered_files, def_pkgs, def_ifaces, auto_incdirs = order_rtl_sources(files)
    file_strs = [str(f) for f in ordered_files]

    all_include_dirs = list(include_dirs or [])
    for d in auto_incdirs:
        if d not in all_include_dirs:
            all_include_dirs.append(d)

    defines = list(defines or [])

    # ─── Primary path: pyslang frontend ───────────────────────────────
    if sv_frontend.is_available() and file_strs:
        try:
            result = sv_frontend.compile_files(file_strs, all_include_dirs, defines)
            if result.compilation is not None:
                knowledge = build_rtl_knowledge(result, file_strs)
                knowledge.parser_status = result.status
                knowledge.packages = def_pkgs
                knowledge.interfaces = def_ifaces

                # Missing dependencies check
                missing_deps, dep_diags = check_missing_dependencies(knowledge.modules, def_pkgs, file_list=ordered_files)
                knowledge.missing_dependencies = missing_deps
                knowledge.parser_status.diagnostics.extend(dep_diags)

                # Top module resolution
                if top_module:
                    knowledge.top_module = top_module
                elif knowledge.top_candidates:
                    knowledge.top_module = knowledge.top_candidates[0]
                    if len(knowledge.top_candidates) > 1:
                        knowledge.parser_status.notes.append(
                            f"Multiple candidate top modules: {', '.join(knowledge.top_candidates)}. "
                            f"Selected '{knowledge.top_module}' as top."
                        )

                if knowledge.modules or not allow_fallback:
                    logger.info(
                        f"RTL parsed (pyslang): {len(knowledge.modules)} modules, "
                        f"top={knowledge.top_module}, "
                        f"syntax_ok={result.status.syntax_ok}, "
                        f"degraded={result.status.degraded}"
                    )
                    return knowledge

                logger.warning(
                    "pyslang parsed no modules — falling back to regex parser (degraded)."
                )
                fallback = _parse_rtl_regex(ordered_files, top_module=top_module, def_pkgs=def_pkgs, def_ifaces=def_ifaces)
                _mark_degraded(fallback, result.status, reason="pyslang found no modules")
                return fallback
            elif not allow_fallback:
                knowledge = RTLKnowledge(file_list=file_strs)
                knowledge.parser_status = result.status
                return knowledge
            else:
                logger.warning(
                    "pyslang frontend failed to compile — falling back to regex parser (degraded)."
                )
                fallback = _parse_rtl_regex(ordered_files, top_module=top_module, def_pkgs=def_pkgs, def_ifaces=def_ifaces)
                _mark_degraded(fallback, result.status, reason="pyslang compilation failed")
                return fallback
        except Exception as exc:  # defensive: never let the frontend crash parsing
            logger.warning(f"pyslang RTL parse raised {exc!r} — regex fallback (degraded).")
            if not allow_fallback:
                raise
            fallback = _parse_rtl_regex(ordered_files, top_module=top_module, def_pkgs=def_pkgs, def_ifaces=def_ifaces)
            _mark_degraded(fallback, None, reason=f"pyslang exception: {exc!r}")
            return fallback

    # ─── pyslang unavailable ──────────────────────────────────────────
    if not sv_frontend.is_available():
        logger.warning(
            f"pyslang unavailable ({sv_frontend.unavailable_reason()}) — "
            "using regex fallback (degraded)."
        )
    knowledge = _parse_rtl_regex(ordered_files, top_module=top_module, def_pkgs=def_pkgs, def_ifaces=def_ifaces)
    _mark_degraded(
        knowledge, None,
        reason=f"pyslang unavailable: {sv_frontend.unavailable_reason()}",
    )
    return knowledge


def _mark_degraded(
    knowledge: RTLKnowledge,
    pyslang_status: Optional[ParserStatus],
    reason: str,
) -> None:
    """Label a regex-fallback result as degraded, preserving pyslang diagnostics."""
    status = ParserStatus(
        backend="regex-fallback",
        degraded=True,
        elaborated=False,
        syntax_ok=True,  # regex parser does not validate syntax
        notes=[
            f"Regex fallback used: {reason}.",
            "Results are approximate: no type/scope resolution, SVA/UVM/"
            "generate constructs may be mis-parsed. Do not treat as a full AST.",
        ],
    )
    if pyslang_status is not None:
        status.diagnostics = list(pyslang_status.diagnostics)
        status.notes = pyslang_status.notes + status.notes
    knowledge.parser_status = status


def _parse_rtl_regex(
    files: Sequence[Path],
    top_module: Optional[str] = None,
    def_pkgs: Optional[Sequence[str]] = None,
    def_ifaces: Optional[Sequence[str]] = None,
) -> RTLKnowledge:
    """Legacy regex/heuristic RTL parser (fallback only)."""
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

    resolved_top = top_module if top_module else (top_candidates[0] if top_candidates else "")

    # Collect global issues
    global_issues = []
    for m in modules:
        for ab in m.always_blocks:
            global_issues.extend(ab.issues)

    missing_deps, dep_diags = check_missing_dependencies(modules, def_pkgs or [], file_list=files)

    knowledge = RTLKnowledge(
        modules=modules,
        top_module=resolved_top,
        file_list=file_list,
        total_lines=total_lines,
        global_issues=global_issues,
        packages=list(def_pkgs or []),
        interfaces=list(def_ifaces or []),
        missing_dependencies=missing_deps,
        top_candidates=top_candidates,
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
        r"(?:(\[[^\]]+\])\s+)?"
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
            if reset in sensitivity:
                pre_reset = sensitivity.split(reset)[0]
                reset_active = "low" if "negedge" in pre_reset else "high"
            else:
                reset_active = ""
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
        "interface", "modport", "package", "endmodule", "endinterface",
        "endpackage", "import", "export", "typedef", "struct", "enum",
        "assert", "assume", "cover", "property", "sequence", "return",
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
