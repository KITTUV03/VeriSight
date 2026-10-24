"""
pyslang-backed RTL knowledge builder.

Walks the elaborated Slang AST (symbols, types, procedural blocks, assignments,
instantiations) and produces the same ``RTLKnowledge`` Pydantic model the rest
of VeriSight already consumes — but populated from a real SystemVerilog
frontend instead of regex. This gives accurate port types/widths, true
read/written signal sets per always block (from assignment expressions, not
identifier diffing), blocking/non-blocking classification from the AST, and
real source locations.

The function here only runs when pyslang successfully parsed the sources; the
explicit regex fallback lives in ``rtl_parser.py``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from verisight.schemas.rtl_schema import (
    RTLKnowledge, RTLModule, Port, Parameter, AlwaysBlock,
    FSM, FSMState, FSMTransition, ClockDomain, RTLAssertion,
)
from verisight.parsers.sv_frontend import CompileResult
from verisight.utils.logger import get_logger

logger = get_logger("pyslang_rtl")

_RESET_RE = re.compile(r"(rst|reset)", re.IGNORECASE)
_RESET_IF_RE = re.compile(
    r"if\s*\(\s*!?\s*~?\s*\w*(?:rst|reset)\w*", re.IGNORECASE
)


def _kind(node: Any) -> str:
    return str(getattr(node, "kind", "")).split(".")[-1]


def _sym_name(expr: Any) -> str:
    """Best-effort symbol name for a NamedValue/HierarchicalValue expression."""
    try:
        sym = expr.symbol
        if sym is not None and getattr(sym, "name", ""):
            return sym.name
    except Exception:
        pass
    try:
        sym = expr.getSymbolReference()
        if sym is not None and getattr(sym, "name", ""):
            return sym.name
    except Exception:
        pass
    return ""


def _names_in(expr: Any) -> Set[str]:
    """Collect all referenced signal names within an expression subtree."""
    names: Set[str] = set()

    def cb(node):
        if _kind(node) in ("NamedValue", "HierarchicalValue"):
            n = _sym_name(node)
            if n:
                names.add(n)

    try:
        expr.visit(cb)
    except Exception:
        pass
    return names


def _line_of(sm: Any, location: Any) -> int:
    try:
        return sm.getLineNumber(location)
    except Exception:
        return 0


def _raw_text(node: Any) -> str:
    try:
        return str(node.syntax)
    except Exception:
        return ""


def _port_direction(direction: Any) -> str:
    name = str(direction).split(".")[-1].lower()
    if name.startswith("in") and name != "inout":
        return "input"
    if name.startswith("out"):
        return "output"
    if name == "inout":
        return "inout"
    if name == "ref":
        return "inout"
    return "input"


def _width_str(typ: Any) -> str:
    try:
        bw = typ.bitWidth
        if bw and bw > 1:
            return f"[{bw - 1}:0]"
    except Exception:
        pass
    return "1"


def _type_str(typ: Any) -> str:
    try:
        s = str(typ)
        # strip packed dims for a clean base type name
        base = s.split("[")[0].strip()
        return base or "logic"
    except Exception:
        return "logic"


# ─── Procedural block analysis ──────────────────────────────────────────
_PROC_KIND_MAP = {
    "AlwaysFF": "sequential",
    "AlwaysComb": "combinational",
    "AlwaysLatch": "latch",
}


def _timing_events(proc: Any) -> List[Tuple[str, str]]:
    """Return [(edge, signal_name)] from an always block's timing control."""
    out: List[Tuple[str, str]] = []
    try:
        body = proc.body
        timing = getattr(body, "timing", None)
        if timing is None:
            return out
        events = getattr(timing, "events", None)
        if events is None:
            return out
        for e in events:
            edge = str(getattr(e, "edge", "")).split(".")[-1]
            name = _sym_name(getattr(e, "expr", None)) if getattr(e, "expr", None) else ""
            out.append((edge, name))
    except Exception:
        pass
    return out


def _collect_assignments(proc: Any) -> Tuple[Set[str], Set[str], List[bool]]:
    """
    Visit a procedural block and return (written, read, nonblocking_flags).

    written: signal names on any assignment LHS
    read:    all referenced names minus written
    nonblocking_flags: isNonBlocking for each assignment (for lint)
    """
    written: Set[str] = set()
    all_named: Set[str] = set()
    nb_flags: List[bool] = []

    def cb(node):
        k = _kind(node)
        if k == "Assignment":
            try:
                for n in _names_in(node.left):
                    written.add(n)
            except Exception:
                pass
            nb_flags.append(bool(getattr(node, "isNonBlocking", False)))
        elif k in ("NamedValue", "HierarchicalValue"):
            n = _sym_name(node)
            if n:
                all_named.add(n)

    try:
        proc.visit(cb)
    except Exception:
        pass

    read = all_named - written
    return written, read, nb_flags


def _build_always_block(proc: Any, sm: Any) -> Optional[AlwaysBlock]:
    kind = _kind(proc)
    if kind != "ProceduralBlock":
        return None
    pk = str(getattr(proc, "procedureKind", "")).split(".")[-1]

    if pk in _PROC_KIND_MAP:
        block_type = _PROC_KIND_MAP[pk]
    elif pk == "Always":
        block_type = None  # decide from timing below
    else:
        return None  # initial/final/etc. are not "always" blocks

    events = _timing_events(proc)
    clock = ""
    reset = ""
    reset_active = ""
    sensitivity = ", ".join(
        f"{edge.lower()} {name}".strip() for edge, name in events
    )

    for edge, name in events:
        if name and _RESET_RE.search(name):
            reset = name
            reset_active = "low" if edge == "NegEdge" else "high"
        elif edge in ("PosEdge", "NegEdge") and not clock:
            clock = name

    if block_type is None:
        block_type = "sequential" if events and any(
            e[0] in ("PosEdge", "NegEdge") for e in events
        ) else "combinational"

    written, read, nb_flags = _collect_assignments(proc)
    raw = _raw_text(proc)

    has_reset = bool(reset) or bool(_RESET_IF_RE.search(raw))

    # Lint issues from AST-accurate blocking/non-blocking classification.
    issues: List[str] = []
    if block_type == "sequential" and nb_flags and not any(nb_flags):
        issues.append(
            "blocking_assignment_in_sequential: sequential block uses blocking (=) assignments"
        )
    if block_type == "combinational" and any(nb_flags):
        issues.append(
            "nonblocking_in_combinational: combinational block uses non-blocking (<=) assignments"
        )
    if block_type == "combinational":
        if re.search(r"\bcase\b", raw) and not re.search(r"\bdefault\b", raw):
            issues.append("missing_case_default: case statement without default")
        if_count = len(re.findall(r"\bif\b", raw))
        else_count = len(re.findall(r"\belse\b", raw))
        if if_count > else_count:
            issues.append("potential_latch: if without else may infer latch")

    try:
        sr = proc.syntax.sourceRange
        line_start = _line_of(sm, sr.start)
        line_end = _line_of(sm, sr.end)
    except Exception:
        line_start = _line_of(sm, getattr(proc, "location", None))
        line_end = line_start

    return AlwaysBlock(
        block_type=block_type,
        sensitivity_list=sensitivity,
        clock_signal=clock,
        reset_signal=reset,
        reset_active=reset_active,
        signals_written=sorted(written),
        signals_read=sorted(read),
        has_reset=has_reset,
        line_start=line_start,
        line_end=line_end,
        raw_code=raw[:4000],
        issues=issues,
    )


# ─── FSM / case extraction (AST-based, best effort) ─────────────────────
def _extract_fsms(inst_body: Any, module_name: str) -> List[FSM]:
    fsms: List[FSM] = []

    def cb(node):
        if _kind(node) != "Case":
            return
        try:
            state_var = _sym_name(node.expr)
        except Exception:
            state_var = ""
        if not state_var:
            return
        states: List[FSMState] = []
        transitions: List[FSMTransition] = []
        has_default = False
        try:
            items = list(node.items)
        except Exception:
            items = []
        for item in items:
            labels = getattr(item, "expressions", None)
            if not labels:
                continue
            for lab in labels:
                label_name = _sym_name(lab) or (str(lab) if lab is not None else "")
                if label_name:
                    states.append(FSMState(name=label_name))
                    # next-state assignments inside this item
                    try:
                        for nm in _collect_assignments(item.stmt)[0]:
                            if nm == state_var or nm.startswith("next_") or nm.endswith("_next"):
                                transitions.append(FSMTransition(
                                    from_state=label_name, to_state="",
                                ))
                    except Exception:
                        pass
        try:
            has_default = node.defaultCase is not None
        except Exception:
            has_default = False
        if len(states) >= 2:
            fsms.append(FSM(
                name=f"{module_name}_{state_var}",
                state_variable=state_var,
                states=states,
                transitions=transitions,
                has_default=has_default,
            ))

    try:
        inst_body.visit(cb)
    except Exception:
        pass
    return fsms


def _extract_assertions(inst_body: Any, sm: Any, file: str) -> List[RTLAssertion]:
    """Collect concurrent/immediate assertions anywhere in a module body."""
    out: List[RTLAssertion] = []
    seen_lines: set = set()

    def cb(node):
        k = _kind(node)
        if k not in ("ConcurrentAssertion", "ImmediateAssertion"):
            return
        try:
            loc = node.sourceRange.start
            line = _line_of(sm, loc)
        except Exception:
            line = _line_of(sm, getattr(node, "location", None))
        if line in seen_lines:
            return
        seen_lines.add(line)
        # assertKind: Assert / Assume / CoverProperty / CoverSequence
        atype = str(getattr(node, "assertionKind", "")).split(".")[-1].lower() or "assert"
        if atype.startswith("cover"):
            atype = "cover"
        elif atype.startswith("assume"):
            atype = "assume"
        else:
            atype = "assert"
        out.append(RTLAssertion(
            assertion_type=atype,
            name="",
            expression=_raw_text(node).strip()[:300],
            line_number=line,
            file=file,
        ))

    try:
        inst_body.visit(cb)
    except Exception:
        pass
    return out


# ─── Module build ───────────────────────────────────────────────────────
def _iter_members(scope: Any):
    """Yield members of a scope, descending into generate blocks."""
    try:
        for m in scope:
            yield m
            k = _kind(m)
            if k in ("GenerateBlock", "GenerateBlockArray", "StatementBlock"):
                yield from _iter_members(m)
    except Exception:
        return


def _build_module(inst: Any, sm: Any) -> RTLModule:
    body = inst.body
    name = inst.name
    try:
        file = sm.getFileName(body.location)
    except Exception:
        file = ""

    ports: List[Port] = []
    parameters: List[Parameter] = []
    always_blocks: List[AlwaysBlock] = []
    assignments: List[str] = []
    instantiations: List[Dict[str, str]] = []
    assertions: List[RTLAssertion] = []

    for m in _iter_members(body):
        k = _kind(m)
        if k == "Port":
            typ = getattr(m, "type", None)
            ports.append(Port(
                name=m.name,
                direction=_port_direction(getattr(m, "direction", "")),
                width=_width_str(typ) if typ is not None else "1",
                signal_type="wire" if getattr(m, "isNetPort", False) else _type_str(typ),
            ))
        elif k == "Parameter":
            val = ""
            try:
                val = str(m.value)
            except Exception:
                pass
            parameters.append(Parameter(
                name=m.name, value=val, param_type="parameter",
                data_type=_type_str(getattr(m, "type", None)),
            ))
        elif k == "ProceduralBlock":
            ab = _build_always_block(m, sm)
            if ab is not None:
                always_blocks.append(ab)
        elif k == "ContinuousAssign":
            assignments.append(_raw_text(m).strip()[:300])
        elif k == "Instance":
            try:
                mod = m.body.definitionName if hasattr(m.body, "definitionName") else m.definition.name
            except Exception:
                mod = _type_str(getattr(m, "definition", None))
            instantiations.append({
                "module": mod or "", "instance": getattr(m, "name", ""), "file": file,
            })
    # Concurrent/immediate assertions are nested inside procedural blocks, so
    # collect them with a body-wide visit rather than from top-level members.
    assertions.extend(_extract_assertions(body, sm, file))

    fsms = _extract_fsms(body, name)

    # Clock domains from sequential always blocks.
    domains: Dict[str, Dict[str, Any]] = {}
    for ab in always_blocks:
        if ab.block_type == "sequential" and ab.clock_signal:
            dom = domains.setdefault(
                ab.clock_signal, {"signals": set(), "reset": ""}
            )
            dom["signals"].update(ab.signals_written)
            if ab.reset_signal:
                dom["reset"] = ab.reset_signal
    clock_domains = [
        ClockDomain(
            clock_signal=clk,
            signals=sorted(info["signals"]),
            reset_signal=info["reset"],
        )
        for clk, info in domains.items()
    ]

    try:
        line_count = _line_of(sm, body.syntax.sourceRange.end) - _line_of(sm, body.location) + 1
    except Exception:
        line_count = 0

    return RTLModule(
        name=name,
        file=file,
        ports=ports,
        parameters=parameters,
        always_blocks=always_blocks,
        fsms=fsms,
        clock_domains=clock_domains,
        assignments=assignments,
        instantiations=instantiations,
        assertions=assertions,
        raw_source=_raw_text(body)[:20000],
        line_count=max(line_count, 0),
    )


def build_rtl_knowledge(result: CompileResult, file_list: List[str]) -> RTLKnowledge:
    """Build RTLKnowledge from a pyslang CompileResult."""
    compilation = result.compilation
    sm = result.source_manager

    modules: List[RTLModule] = []
    seen: Set[str] = set()

    def walk(inst):
        try:
            file = sm.getFileName(inst.body.location)
        except Exception:
            file = ""
        key = f"{inst.name}@{file}"
        if key in seen:
            return
        seen.add(key)
        modules.append(_build_module(inst, sm))
        # recurse into child instances
        for m in _iter_members(inst.body):
            if _kind(m) == "Instance":
                try:
                    walk(m)
                except Exception:
                    continue

    try:
        for top in compilation.getRoot().topInstances:
            walk(top)
    except Exception as exc:
        logger.warning(f"pyslang RTL walk failed: {exc!r}")

    # Ensure no module definition silently disappears.
    discovered_names = {m.name for m in modules}
    try:
        for d in compilation.getDefinitions():
            if _kind(d) != "Definition" and str(getattr(d, "definitionKind", "")).split(".")[-1] not in ("Module",):
                continue
            if d.name not in discovered_names:
                try:
                    file = sm.getFileName(d.location)
                except Exception:
                    file = ""
                modules.append(RTLModule(
                    name=d.name, file=file,
                    raw_source="",
                    line_count=0,
                ))
                discovered_names.add(d.name)
    except Exception:
        pass

    # Top module: not instantiated by others.
    instantiated = set()
    for m in modules:
        for inst in m.instantiations:
            instantiated.add(inst.get("module", ""))
    top_candidates = [m.name for m in modules if m.name not in instantiated]
    top_module = top_candidates[0] if top_candidates else (modules[0].name if modules else "")

    global_issues: List[str] = []
    for m in modules:
        for ab in m.always_blocks:
            global_issues.extend(ab.issues)

    total_lines = 0
    for f in file_list:
        try:
            from pathlib import Path
            total_lines += Path(f).read_text(errors="ignore").count("\n") + 1
        except Exception:
            pass

    knowledge = RTLKnowledge(
        modules=modules,
        top_module=top_module,
        file_list=file_list,
        total_lines=total_lines,
        global_issues=global_issues,
    )
    return knowledge
