"""
RTL Parser for VeriSight.

Parses SystemVerilog and Verilog (and VHDL entities) RTL source files and extracts
structured knowledge including module declarations, ports, parameters, always blocks,
FSMs, clock domains, reset logic, inline assertions, package definitions, interface
definitions, package imports, include dependencies, and cross-file compilation order.

Treats multiple files as a single logical RTL project while maintaining individual
file boundaries, original paths, and line-accurate references.

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
from typing import List, Dict, Optional, Sequence, Tuple, Union, Set, Any

from verisight.schemas.rtl_schema import (
    RTLKnowledge, RTLModule, Port, Parameter, AlwaysBlock,
    FSM, FSMState, FSMTransition, ClockDomain, RTLAssertion,
)
from verisight.schemas.parser_schema import ParserStatus, ParserDiagnostic, CATEGORY_TOOL
from verisight.utils.file_utils import read_file, discover_files, RTL_EXTENSIONS
from verisight.utils.sv_lexer import strip_comments
from verisight.utils.logger import get_logger
from verisight.parsers import sv_frontend
from verisight.parsers.pyslang_rtl import build_rtl_knowledge

logger = get_logger("rtl_parser")

VERILOG_PRIMITIVES = {
    "and", "nand", "or", "nor", "xor", "xnor", "buf", "not",
    "bufif0", "bufif1", "notif0", "notif1", "pullup", "pulldown",
    "cmos", "rcmos", "nmos", "pmos", "rnmos", "rpmos", "rtran", "rtranif0", "rtranif1", "tran", "tranif0", "tranif1",
}

STANDARD_PACKAGES = {"uvm_pkg"}


def parse_rtl(
    path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
    files: Optional[List[Union[str, Path]]] = None,
    top_module: Optional[str] = None,
    include_dirs: Optional[Sequence[str]] = None,
    defines: Optional[Sequence[str]] = None,
    allow_fallback: bool = True,
    rtl_path: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
    rtl_files: Optional[List[Union[str, Path]]] = None,
    **kwargs,
) -> RTLKnowledge:
    """
    Parse RTL source files from a single file, a directory, or a list of files.

    Uses the pyslang frontend first; falls back to the legacy regex parser
    only when pyslang is unavailable or yields no modules.

    Args:
        path: Path to a single file, a directory, or list of file paths.
        files: Optional explicit list of file paths (takes precedence or combines with path).
        top_module: Optional explicit top-level module name override.
        include_dirs: Optional `include search directories.
        defines: Optional macro defines ("NAME" or "NAME=value").
        allow_fallback: If True, fall back to the regex parser when the
            pyslang frontend is unavailable or finds no modules. The result
            is then flagged degraded. If False, the (possibly empty) pyslang
            result is returned as-is.

    Returns:
        RTLKnowledge Pydantic model with modules, packages, dependencies, and top module.
    """
    path = path or rtl_path or kwargs.get("rtl")
    files = files or rtl_files
    # ── 1. Resolve and deduplicate file list ───────────────────────────
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
            found = discover_files(p, RTL_EXTENSIONS)
            for f in found:
                if f not in resolved_paths:
                    resolved_paths.append(f)
        else:
            logger.warning(f"RTL target path does not exist on disk: {target}")

    if files:
        _add_target(files)
    if path:
        _add_target(path)

    if not resolved_paths:
        logger.warning("parse_rtl: No valid RTL source files found")
        return RTLKnowledge(
            modules=[],
            top_module="",
            file_list=[],
            total_lines=0,
            global_issues=["No RTL source files provided or found"],
        )

    file_strs = [str(f) for f in resolved_paths]
    include_dirs = list(include_dirs or [])
    defines = list(defines or [])

    # ─── Primary path: pyslang frontend ───────────────────────────────
    if sv_frontend.is_available() and file_strs:
        try:
            result = sv_frontend.compile_files(file_strs, include_dirs, defines)
            if result.compilation is not None:
                knowledge = build_rtl_knowledge(result, file_strs)
                knowledge.parser_status = result.status
                if knowledge.modules or not allow_fallback:
                    if top_module:
                        knowledge.top_module = top_module
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
                fallback = _parse_rtl_regex(resolved_paths, top_module=top_module)
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
                fallback = _parse_rtl_regex(resolved_paths, top_module=top_module)
                _mark_degraded(fallback, result.status, reason="pyslang compilation failed")
                return fallback
        except Exception as exc:  # defensive: never let the frontend crash parsing
            logger.warning(f"pyslang RTL parse raised {exc!r} — regex fallback (degraded).")
            if not allow_fallback:
                raise
            fallback = _parse_rtl_regex(resolved_paths, top_module=top_module)
            _mark_degraded(fallback, None, reason=f"pyslang exception: {exc!r}")
            return fallback

    # ─── pyslang unavailable ──────────────────────────────────────────
    if not sv_frontend.is_available():
        logger.warning(
            f"pyslang unavailable ({sv_frontend.unavailable_reason()}) — "
            "using regex fallback (degraded)."
        )
    knowledge = _parse_rtl_regex(resolved_paths, top_module=top_module)
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
        syntax_ok=True,
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


def _parse_rtl_regex(resolved_paths: List[Path], top_module: Optional[str] = None) -> RTLKnowledge:
    """Deterministic regex/heuristic RTL parser (fallback and multi-file project parser)."""
    logger.info(f"Parsing RTL project ({len(resolved_paths)} files)")
    modules: List[RTLModule] = []
    file_list: List[str] = []
    total_lines = 0
    packages_declared: List[str] = []
    interfaces_declared: List[str] = []
    file_basenames: Set[str] = set()
    global_issues: List[str] = []

    for f in resolved_paths:
        f_str = str(f)
        file_list.append(f_str)
        file_basenames.add(f.name)

        # Check for empty file
        try:
            size = f.stat().st_size
            if size == 0:
                global_issues.append(f"Empty source file: {f.name}")
                continue
        except Exception:
            pass

        content = read_file(f)
        if not content:
            continue

        file_lines = content.count("\n") + 1
        total_lines += file_lines

        # Parse packages, interfaces, modules, or VHDL entities
        file_modules = _parse_file(f_str, content)
        for m in file_modules:
            if m.is_package and m.name not in packages_declared:
                packages_declared.append(m.name)
            elif m.is_interface and m.name not in interfaces_declared:
                interfaces_declared.append(m.name)
        modules.extend(file_modules)

    # ── 2. Collect declared entities and track cross-file dependencies ─
    declared_module_names = {m.name for m in modules}
    all_known_entities = declared_module_names | set(packages_declared) | set(interfaces_declared) | VERILOG_PRIMITIVES

    missing_dependencies: List[Dict[str, Any]] = []

    for m in modules:
        # Check module instantiations
        for inst in m.instantiations:
            inst_mod = inst.get("module", "")
            if inst_mod and inst_mod not in all_known_entities and not inst_mod.startswith("$"):
                issue_dict = {
                    "type": "missing_module",
                    "required": inst_mod,
                    "used_by": m.name,
                    "file": inst.get("file", m.file),
                    "description": f"Module '{m.name}' in {Path(m.file).name} instantiates undefined module '{inst_mod}'",
                }
                missing_dependencies.append(issue_dict)
                global_issues.append(issue_dict["description"])

        # Check package imports
        for pkg in m.package_imports:
            clean_pkg = pkg.split("::")[0]
            if clean_pkg not in packages_declared and clean_pkg not in STANDARD_PACKAGES:
                issue_dict = {
                    "type": "missing_package",
                    "required": clean_pkg,
                    "used_by": m.name,
                    "file": m.file,
                    "description": f"Module '{m.name}' imports undeclared package '{clean_pkg}'",
                }
                missing_dependencies.append(issue_dict)
                global_issues.append(issue_dict["description"])

        # Check include files
        for inc in m.includes:
            inc_name = Path(inc).name
            if inc_name not in file_basenames and not Path(inc).exists():
                issue_dict = {
                    "type": "missing_include",
                    "required": inc,
                    "used_by": m.name,
                    "file": m.file,
                    "description": f"File {Path(m.file).name} includes missing header '{inc}'",
                }
                missing_dependencies.append(issue_dict)
                global_issues.append(issue_dict["description"])

    # ── 3. Top-Level Module Detection & Resolution ─────────────────────
    instantiated_modules = set()
    for m in modules:
        for inst in m.instantiations:
            instantiated_modules.add(inst.get("module", ""))

    # Top candidates are real modules (not packages, not interfaces) never instantiated
    top_candidates = [
        m.name for m in modules
        if not m.is_package and not m.is_interface and m.name not in instantiated_modules
    ]

    detected_top = ""
    if top_module:
        # User specified top module
        if top_module in declared_module_names:
            detected_top = top_module
        else:
            global_issues.append(
                f"Specified top module '{top_module}' not found in parsed modules: {sorted(list(declared_module_names))}"
            )
            detected_top = top_candidates[0] if top_candidates else (modules[0].name if modules else "")
    else:
        if len(top_candidates) == 1:
            detected_top = top_candidates[0]
        elif len(top_candidates) > 1:
            # Ranking heuristics:
            # 1. Contains 'top' in name (case-insensitive)
            # 2. Instantiates the most submodules
            # 3. First candidate in file list
            ranked = sorted(
                top_candidates,
                key=lambda name: (
                    1 if "top" in name.lower() or "dut" in name.lower() else 0,
                    len([inst for m in modules if m.name == name for inst in m.instantiations]),
                ),
                reverse=True,
            )
            detected_top = ranked[0]
            global_issues.append(
                f"Multiple top-level candidates detected ({', '.join(top_candidates)}). "
                f"Auto-selected '{detected_top}' based on hierarchy heuristics."
            )
        elif modules:
            # If all are instantiated (cycle) or only 1 module exists
            detected_top = modules[0].name

    # ── 4. Resolve Compilation Order (Topological) ─────────────────────
    compilation_order = _compute_compilation_order(modules, file_list)

    # ── 5. Collect always block issues ─────────────────────────────────
    for m in modules:
        for ab in m.always_blocks:
            global_issues.extend(ab.issues)

    knowledge = RTLKnowledge(
        modules=modules,
        top_module=detected_top,
        file_list=file_list,
        total_lines=total_lines,
        global_issues=global_issues,
        packages=packages_declared,
        interfaces=interfaces_declared,
        compilation_order=compilation_order,
        missing_dependencies=missing_dependencies,
        top_candidates=top_candidates,
    )

    logger.info(
        f"RTL project parsed: {len(modules)} modules ({len(packages_declared)} pkgs, "
        f"{len(interfaces_declared)} ifaces), {total_lines} lines across {len(file_list)} files, "
        f"top={detected_top}, {len(global_issues)} diagnostics"
    )
    return knowledge


def _compute_compilation_order(modules: List[RTLModule], file_list: List[str]) -> List[str]:
    """
    Compute optimal compilation order for RTL source files.
    Packages first, interfaces next, leaf submodules before parents.
    """
    file_ranks: Dict[str, int] = {f: 100 for f in file_list}

    # 1. Packages get lowest rank (compile earliest)
    for m in modules:
        if m.is_package:
            file_ranks[m.file] = min(file_ranks.get(m.file, 100), 10)
        elif m.is_interface:
            file_ranks[m.file] = min(file_ranks.get(m.file, 100), 20)

    # 2. Dependency ordering: if module A instantiates module B, file of B should compile before file of A
    module_to_file = {m.name: m.file for m in modules}
    for m in modules:
        for inst in m.instantiations:
            child_mod = inst.get("module")
            if child_mod in module_to_file:
                child_file = module_to_file[child_mod]
                if child_file != m.file:
                    file_ranks[child_file] = min(file_ranks[child_file], file_ranks[m.file] - 1)

    # Sort files by calculated rank, preserving original relative order for ties
    ordered = sorted(file_list, key=lambda f: (file_ranks.get(f, 100), file_list.index(f)))
    return ordered


def _parse_file(filepath: str, content: str) -> List[RTLModule]:
    """Parse all modules, packages, interfaces, and VHDL entities from a single file."""
    modules: List[RTLModule] = []
    clean = strip_comments(content)
    lines = content.splitlines()
    is_vhdl = filepath.lower().endswith((".vhd", ".vhdl"))

    # Extract file-level package imports and `include directives
    file_imports = re.findall(r"import\s+([\w:*]+)\s*;", clean)
    file_includes = re.findall(r"`include\s+[\"<]([^\"<>]+)[\">]", clean)

    if is_vhdl:
        return _parse_vhdl_file(filepath, content, clean, lines)

    # ── A. Find SystemVerilog Packages ────────────────────────────────
    pkg_pattern = re.compile(
        r"\bpackage\s+(\w+)\s*;([\s\S]*?)\bendpackage\b",
        re.MULTILINE
    )
    for match in pkg_pattern.finditer(clean):
        pkg_name = match.group(1)
        pkg_body = match.group(2)
        pkg_start = content[:match.start()].count("\n") + 1
        pkg_end = content[:match.end()].count("\n") + 1

        pkg_module = RTLModule(
            name=pkg_name,
            file=filepath,
            parameters=_extract_parameters(pkg_body),
            raw_source=content[match.start():match.end()],
            line_count=pkg_end - pkg_start + 1,
            is_package=True,
            package_imports=file_imports,
            includes=file_includes,
        )
        modules.append(pkg_module)

    # ── B. Find SystemVerilog Interfaces ──────────────────────────────
    iface_pattern = re.compile(
        r"\binterface\s+(\w+)\s*(?:#\s*\([\s\S]*?\))?\s*(?:\([\s\S]*?\))?\s*;([\s\S]*?)\bendinterface\b",
        re.MULTILINE
    )
    for match in iface_pattern.finditer(clean):
        iface_name = match.group(1)
        iface_body = match.group(2)
        iface_start = content[:match.start()].count("\n") + 1
        iface_end = content[:match.end()].count("\n") + 1

        iface_module = RTLModule(
            name=iface_name,
            file=filepath,
            ports=_extract_ports(clean[match.start():match.end()]),
            parameters=_extract_parameters(iface_body),
            raw_source=content[match.start():match.end()],
            line_count=iface_end - iface_start + 1,
            is_interface=True,
            package_imports=file_imports,
            includes=file_includes,
        )
        modules.append(iface_module)

    # ── C. Find SystemVerilog / Verilog Modules ────────────────────────
    # Matches module declarations: module name #(...) (...); or module name (...); or module name;
    module_pattern = re.compile(
        r"\bmodule\s+(\w+)\s*(?:#\s*\([\s\S]*?\))?\s*(?:\([\s\S]*?\))?\s*;",
        re.MULTILINE
    )

    for match in module_pattern.finditer(clean):
        mod_name = match.group(1)
        mod_start = content[:match.start()].count("\n") + 1

        # Find matching endmodule
        endmod = re.search(r"\bendmodule\b", clean[match.start():])
        if endmod:
            mod_end_offset = match.start() + endmod.end()
            mod_content = clean[match.start():mod_end_offset]
            mod_raw = content[match.start():mod_end_offset]
            mod_end = content[:mod_end_offset].count("\n") + 1
        else:
            mod_content = clean[match.start():]
            mod_raw = content[match.start():]
            mod_end = len(lines)

        module_imports = re.findall(r"import\s+([\w:*]+)\s*;", mod_content)
        all_imports = sorted(set(file_imports + module_imports))

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
            package_imports=all_imports,
            includes=file_includes,
        )
        modules.append(module)

    return modules


def _parse_vhdl_file(filepath: str, content: str, clean: str, lines: List[str]) -> List[RTLModule]:
    """Parse basic VHDL entity declarations into RTLModule objects."""
    modules: List[RTLModule] = []
    entity_pattern = re.compile(
        r"\bentity\s+(\w+)\s+is\s+port\s*\(([\s\S]*?)\)\s*;\s*end(?:\s+(?:entity\s+)?\1)?\s*;",
        re.IGNORECASE | re.MULTILINE
    )

    for match in entity_pattern.finditer(clean):
        ent_name = match.group(1)
        port_clause = match.group(2)
        start_line = content[:match.start()].count("\n") + 1
        end_line = content[:match.end()].count("\n") + 1

        ports: List[Port] = []
        for port_line in port_clause.split(";"):
            p_match = re.search(r"(\w+)\s*:\s*(in|out|inout)\s+([\w_]+(?:\s*\([^)]+\))?)", port_line, re.IGNORECASE)
            if p_match:
                p_name, p_dir, p_type = p_match.group(1), p_match.group(2).lower(), p_match.group(3)
                ports.append(Port(
                    name=p_name,
                    direction=p_dir,
                    signal_type=p_type,
                    width="1" if "vector" not in p_type.lower() else p_type,
                ))

        modules.append(RTLModule(
            name=ent_name,
            file=filepath,
            ports=ports,
            raw_source=content[match.start():match.end()],
            line_count=end_line - start_line + 1,
        ))

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

        block_content = _find_matching_block(content, begin_pos)
        block_start_line = module_start_line + content[:match.start()].count("\n")
        block_end_line = module_start_line + content[:begin_pos + len(block_content)].count("\n")

        block_type, clock, reset, reset_active = _classify_always(
            keyword, sensitivity, block_content
        )

        signals_written = _extract_lhs_signals(block_content)
        signals_read = _extract_rhs_signals(block_content, signals_written)

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
            raw_code=block_content[:1000],
            issues=issues,
        ))

    return blocks


def _classify_always(
    keyword: str, sensitivity: str, body: str
) -> Tuple[str, str, str, str]:
    """Classify an always block as sequential, combinational, or latch."""
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
        if re.search(r"\w+\s*=[^=]", body) and not re.search(r"<=", body):
            issues.append("blocking_assignment_in_sequential: Uses = instead of <= in sequential block")

    if block_type == "combinational":
        if re.search(r"<=", body):
            issues.append("nonblocking_in_combinational: Uses <= in combinational block")

        if sensitivity and sensitivity != "*" and "posedge" not in sensitivity:
            issues.append("incomplete_sensitivity: Sensitivity list may be incomplete, use always @(*) or always_comb")

        if_count = len(re.findall(r"\bif\b", body))
        else_count = len(re.findall(r"\belse\b", body))
        if if_count > else_count:
            issues.append("potential_latch: if without else may infer latch")

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

    case_pattern = re.compile(
        r"case\s*\(\s*(\w+)\s*\)([\s\S]*?)endcase",
        re.MULTILINE
    )

    for case_match in case_pattern.finditer(content):
        state_var = case_match.group(1)
        case_body = case_match.group(2)

        case_items = re.findall(
            r"(\w+)\s*:\s*([\s\S]*?)(?=\w+\s*:|default\s*:|$)",
            case_body
        )

        if len(case_items) < 2:
            continue

        states = []
        transitions = []

        for state_name, state_body in case_items:
            if state_name in ("default",):
                continue
            states.append(FSMState(name=state_name))

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

            written = _extract_lhs_signals(body)
            domains[clk].extend(written)

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
    inst_pattern = re.compile(
        r"(\w+)\s+(?:#\s*\([^)]*\)\s+)?(\w+)\s*\(",
        re.MULTILINE
    )

    not_modules = {
        "module", "function", "task", "if", "else", "case", "for",
        "while", "assign", "always", "initial", "begin", "end",
        "input", "output", "inout", "wire", "reg", "logic",
        "parameter", "localparam", "generate", "integer",
        "always_ff", "always_comb", "always_latch", "package", "interface",
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
