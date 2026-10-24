"""
UVM Testbench Parser for VeriSight.

Parses UVM testbench SystemVerilog source files and extracts structured
knowledge including component types, transaction flows, TLM connections,
factory overrides, config DB usage, and coverage models.

Primary backend: pyslang (via ``sv_frontend`` + ``pyslang_uvm``), which
discovers classes/interfaces/packages from a real syntax tree. The
macro-driven parts (config_db, factory, TLM) are extracted by the per-class
helpers in this module, because UVM macros cannot be expanded without the UVM
library. When pyslang is unavailable the original regex parser is used and the
result is explicitly flagged ``degraded``.

No LLM calls.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Sequence

from verisight.schemas.tb_schema import (
    TBKnowledge, Transaction, TransactionField, SequenceInfo,
    DriverInfo, MonitorInfo, ScoreboardInfo, CoverageInfo,
    TLMConnection, FactoryOverride, ConfigDBEntry,
    UVMComponentInfo, AssertionInfo, InterfaceInfo,
)
from verisight.schemas.parser_schema import ParserStatus
from verisight.utils.file_utils import read_file, discover_files, TB_EXTENSIONS
from verisight.utils.sv_lexer import strip_comments
from verisight.utils.logger import get_logger
from verisight.parsers import sv_frontend

logger = get_logger("uvm_parser")

# UVM base classes for component identification
UVM_COMPONENT_TYPES = {
    "uvm_driver": "driver",
    "uvm_monitor": "monitor",
    "uvm_scoreboard": "scoreboard",
    "uvm_subscriber": "scoreboard",
    "uvm_agent": "agent",
    "uvm_env": "env",
    "uvm_test": "test",
    "uvm_sequence": "sequence",
    "uvm_sequence_item": "transaction",
    "uvm_sequencer": "sequencer",
    "uvm_object": "object",
    "uvm_component": "component",
}


def parse_uvm(
    path: str,
    include_dirs: Optional[Sequence[str]] = None,
    defines: Optional[Sequence[str]] = None,
    allow_fallback: bool = True,
) -> TBKnowledge:
    """
    Parse UVM testbench source files from a file or directory.

    Uses the pyslang frontend first (syntax-tree based class discovery); falls
    back to the legacy regex parser only when pyslang is unavailable or finds
    no components, flagging the result ``degraded`` in that case.

    Args:
        path: Path to a single .sv file or directory containing TB files.
        include_dirs: Optional `include search directories (defaults to the TB
            directory so package includes resolve).
        defines: Optional macro defines.
        allow_fallback: Whether to fall back to the regex parser.

    Returns:
        TBKnowledge Pydantic model, with ``parser_status`` populated.
    """
    logger.info(f"Parsing UVM testbench: {path}")
    p = Path(path)

    if p.is_file():
        sibling_files = discover_files(p.parent, TB_EXTENSIONS) if p.parent.exists() else []
        if len(sibling_files) > 1:
            files = [p] + [f for f in sibling_files if f != p]
        else:
            files = [p]
    else:
        files = discover_files(p, TB_EXTENSIONS)

    file_strs = [str(f) for f in files]
    # Default include dir: the directory containing the TB files, so `include
    # directives (e.g. package `include "x.sv") resolve.
    inc = list(include_dirs or [])
    if not inc:
        base_dir = str(p if p.is_dir() else p.parent)
        inc = [base_dir]
    defines = list(defines or [])

    # ─── Primary path: pyslang frontend ───────────────────────────────
    if sv_frontend.is_available() and file_strs:
        try:
            from verisight.parsers.pyslang_uvm import build_tb_knowledge
            result = sv_frontend.compile_files(file_strs, inc, defines)
            if result.syntax_trees:
                tb = build_tb_knowledge(result, file_strs)
                has_components = bool(
                    tb.drivers or tb.monitors or tb.scoreboards
                    or tb.sequences or tb.transactions or tb.components
                    or tb.interfaces
                )
                if has_components or not allow_fallback:
                    logger.info(
                        f"UVM parsed (pyslang): {len(tb.drivers)} drivers, "
                        f"{len(tb.monitors)} monitors, {len(tb.scoreboards)} scoreboards, "
                        f"{len(tb.sequences)} sequences, {len(tb.transactions)} transactions, "
                        f"degraded={result.status.degraded}"
                    )
                    return tb
                logger.warning(
                    "pyslang found no UVM components — regex fallback (degraded)."
                )
                tb = _parse_uvm_regex(files)
                _mark_degraded(tb, result.status, "pyslang found no UVM components")
                return tb
            elif not allow_fallback:
                tb = TBKnowledge(file_list=file_strs)
                tb.parser_status = result.status
                return tb
            else:
                logger.warning("pyslang produced no syntax trees — regex fallback (degraded).")
                tb = _parse_uvm_regex(files)
                _mark_degraded(tb, result.status, "pyslang produced no syntax trees")
                return tb
        except Exception as exc:
            logger.warning(f"pyslang UVM parse raised {exc!r} — regex fallback (degraded).")
            if not allow_fallback:
                raise
            tb = _parse_uvm_regex(files)
            _mark_degraded(tb, None, f"pyslang exception: {exc!r}")
            return tb

    # ─── pyslang unavailable ──────────────────────────────────────────
    if not sv_frontend.is_available():
        logger.warning(
            f"pyslang unavailable ({sv_frontend.unavailable_reason()}) — regex fallback (degraded)."
        )
    tb = _parse_uvm_regex(files)
    _mark_degraded(tb, None, f"pyslang unavailable: {sv_frontend.unavailable_reason()}")
    return tb


def _mark_degraded(tb: TBKnowledge, pyslang_status, reason: str) -> None:
    """Label a regex-fallback TB result as degraded, preserving diagnostics."""
    status = ParserStatus(
        backend="regex-fallback", degraded=True, elaborated=False, syntax_ok=True,
        notes=[
            f"Regex fallback used: {reason}.",
            "UVM analysis is approximate: class discovery via regex, no syntax "
            "validation. Do not treat as a fully elaborated testbench.",
        ],
    )
    if pyslang_status is not None:
        status.diagnostics = list(pyslang_status.diagnostics)
        status.notes = pyslang_status.notes + status.notes
    tb.parser_status = status


def _parse_uvm_regex(files) -> TBKnowledge:
    """Legacy regex UVM parser (fallback only)."""
    tb = TBKnowledge()
    file_list = []

    for f in files:
        file_list.append(str(f))
        content = read_file(f)
        if not content:
            continue
        _parse_tb_file(str(f), content, tb)

    tb.file_list = file_list

    logger.info(
        f"UVM parsed (regex): {len(tb.drivers)} drivers, {len(tb.monitors)} monitors, "
        f"{len(tb.scoreboards)} scoreboards, {len(tb.sequences)} sequences, "
        f"{len(tb.transactions)} transactions"
    )
    return tb


def _parse_tb_file(filepath: str, content: str, tb: TBKnowledge) -> None:
    """Parse a single TB file and populate TBKnowledge."""
    clean = strip_comments(content)

    # Check for package declaration
    pkg_match = re.search(r"package\s+(\w+)\s*;", clean)
    if pkg_match:
        tb.packages.append(pkg_match.group(1))

    # Check for interface declaration
    intf_match = re.search(r"interface\s+(\w+)", clean)
    if intf_match:
        tb.interfaces.append(_parse_interface(filepath, clean))
        return  # Interfaces are separate from UVM components

    # Find class declarations and classify by parent
    class_pattern = re.compile(
        r"class\s+(\w+)\s+extends\s+([\w#\(\)\s,]+?)\s*;([\s\S]*?)endclass",
        re.MULTILINE
    )

    for match in class_pattern.finditer(clean):
        class_name = match.group(1)
        parent_raw = match.group(2).strip()
        class_body = match.group(3)

        # Determine parent base class
        parent_base = _get_base_class(parent_raw)
        comp_type = UVM_COMPONENT_TYPES.get(parent_base, "")

        if not comp_type:
            # Try to infer from class name
            comp_type = _infer_component_type(class_name)

        if comp_type == "transaction":
            tb.transactions.append(
                _parse_transaction(class_name, filepath, parent_raw, class_body)
            )
        elif comp_type == "sequence":
            tb.sequences.append(
                _parse_sequence(class_name, filepath, parent_raw, class_body)
            )
        elif comp_type == "driver":
            tb.drivers.append(
                _parse_driver(class_name, filepath, parent_raw, class_body)
            )
        elif comp_type == "monitor":
            tb.monitors.append(
                _parse_monitor(class_name, filepath, parent_raw, class_body)
            )
        elif comp_type == "scoreboard":
            tb.scoreboards.append(
                _parse_scoreboard(class_name, filepath, parent_raw, class_body)
            )
        else:
            # Generic component
            tb.components.append(UVMComponentInfo(
                name=class_name,
                component_type=comp_type or "component",
                file=filepath,
                parent_class=parent_raw,
                phase_methods=_extract_phase_methods(class_body),
            ))

        # Extract factory overrides from class body
        tb.factory_overrides.extend(_extract_factory_overrides(class_body))
        # Extract config_db usage
        tb.config_db_entries.extend(
            _extract_config_db(class_body, class_name)
        )
        # Extract TLM connections
        tb.tlm_connections.extend(
            _extract_tlm_connections(class_body, class_name)
        )

    # Extract coverage groups (outside of class or inside)
    tb.coverage.extend(_extract_coverage(filepath, clean))

    # Extract assertions
    tb.assertions.extend(_extract_assertions(filepath, clean))


def _get_base_class(parent_raw: str) -> str:
    """Extract the base UVM class from a parameterized extends clause."""
    # Handle: uvm_driver #(my_seq_item) → uvm_driver
    base = re.match(r"(\w+)", parent_raw)
    return base.group(1) if base else parent_raw


def _infer_component_type(class_name: str) -> str:
    """Infer component type from naming conventions."""
    name_lower = class_name.lower()
    if "driver" in name_lower or name_lower.endswith("_drv"):
        return "driver"
    if "monitor" in name_lower or name_lower.endswith("_mon"):
        return "monitor"
    if "scoreboard" in name_lower or name_lower.endswith("_sb"):
        return "scoreboard"
    if "sequencer" in name_lower or name_lower.endswith("_sqr"):
        return "sequencer"
    if "sequence" in name_lower or name_lower.endswith("_seq"):
        return "sequence"
    if "agent" in name_lower or name_lower.endswith("_agt"):
        return "agent"
    if "env" in name_lower:
        return "env"
    if "test" in name_lower:
        return "test"
    if "config" in name_lower or name_lower.endswith("_cfg"):
        return "config"
    if "item" in name_lower or "txn" in name_lower or "transaction" in name_lower:
        return "transaction"
    return ""


def _parse_transaction(
    name: str, filepath: str, parent: str, body: str
) -> Transaction:
    """Parse a UVM transaction/sequence_item."""
    fields = []
    constraints = []

    # Extract rand/randc fields
    field_pattern = re.compile(
        r"(rand|randc)?\s*(\w+(?:\s*\[[\d:]+\])?)\s+(\w+)\s*;",
        re.MULTILINE
    )
    for match in field_pattern.finditer(body):
        rand_type = match.group(1) or ""
        field_type = match.group(2)
        field_name = match.group(3)
        if field_type not in ("function", "task", "virtual", "static", "local", "protected"):
            fields.append(TransactionField(
                name=field_name,
                field_type=field_type,
                is_rand=bool(rand_type),
            ))

    # Extract constraints
    constraint_pattern = re.compile(
        r"constraint\s+(\w+)\s*\{([^}]*)\}",
        re.MULTILINE
    )
    for match in constraint_pattern.finditer(body):
        constraints.append(f"{match.group(1)}: {match.group(2).strip()}")

    return Transaction(
        name=name,
        file=filepath,
        fields=fields,
        constraints=constraints,
        parent_class=parent,
    )


def _parse_sequence(
    name: str, filepath: str, parent: str, body: str
) -> SequenceInfo:
    """Parse a UVM sequence."""
    # Extract transaction type from parameterization
    txn_match = re.search(r"extends\s+\w+\s*#\s*\(\s*(\w+)\s*\)", parent + body)
    txn_type = txn_match.group(1) if txn_match else ""

    # Extract body task summary
    body_match = re.search(
        r"(?:virtual\s+)?task\s+body\s*\(\s*\)\s*;([\s\S]*?)endtask",
        body
    )
    body_summary = ""
    if body_match:
        body_text = body_match.group(1).strip()
        body_summary = body_text[:500]

    return SequenceInfo(
        name=name,
        file=filepath,
        body_summary=body_summary,
        transaction_type=txn_type,
        parent_class=parent,
        has_pre_body="pre_body" in body,
        has_post_body="post_body" in body,
    )


def _parse_driver(
    name: str, filepath: str, parent: str, body: str
) -> DriverInfo:
    """Parse a UVM driver."""
    txn_match = re.search(r"#\s*\(\s*(\w+)\s*\)", parent)
    txn_type = txn_match.group(1) if txn_match else ""

    # Extract interface signal references (vif.signal)
    intf_signals = list(set(re.findall(r"vif\.(\w+)", body)))

    # Extract run_phase
    run_phase_match = re.search(
        r"(?:virtual\s+)?task\s+run_phase\s*\([^)]*\)\s*;([\s\S]*?)endtask",
        body
    )
    raw_run = run_phase_match.group(1).strip() if run_phase_match else ""

    return DriverInfo(
        name=name,
        file=filepath,
        transaction_type=txn_type,
        interface_signals=sorted(intf_signals),
        drive_logic_summary=raw_run[:300],
        raw_run_phase=raw_run[:2000],
    )


def _parse_monitor(
    name: str, filepath: str, parent: str, body: str
) -> MonitorInfo:
    """Parse a UVM monitor."""
    txn_match = re.search(r"#\s*\(\s*(\w+)\s*\)", parent)
    txn_type = txn_match.group(1) if txn_match else ""

    intf_signals = list(set(re.findall(r"vif\.(\w+)", body)))

    # Find analysis port
    ap_match = re.search(r"uvm_analysis_port\s*#\s*\(\s*\w+\s*\)\s+(\w+)", body)
    ap_name = ap_match.group(1) if ap_match else ""

    run_phase_match = re.search(
        r"(?:virtual\s+)?task\s+run_phase\s*\([^)]*\)\s*;([\s\S]*?)endtask",
        body
    )
    raw_run = run_phase_match.group(1).strip() if run_phase_match else ""

    return MonitorInfo(
        name=name,
        file=filepath,
        transaction_type=txn_type,
        interface_signals=sorted(intf_signals),
        analysis_port=ap_name,
        raw_run_phase=raw_run[:2000],
    )


def _parse_scoreboard(
    name: str, filepath: str, parent: str, body: str
) -> ScoreboardInfo:
    """Parse a UVM scoreboard."""
    # Find analysis exports/imps
    exports = re.findall(
        r"uvm_analysis_(?:imp|export)\w*\s*(?:#\s*\([^)]*\))?\s+(\w+)",
        body
    )

    # Extract comparison/prediction logic (write function)
    write_match = re.search(
        r"(?:virtual\s+)?function\s+void\s+write\s*\([^)]*\)\s*;([\s\S]*?)endfunction",
        body
    )
    comparison = write_match.group(1).strip() if write_match else ""

    return ScoreboardInfo(
        name=name,
        file=filepath,
        prediction_logic=comparison[:500],
        comparison_logic=comparison[:500],
        analysis_exports=exports,
        raw_code=body[:3000],
    )


def _extract_phase_methods(body: str) -> List[str]:
    """Extract implemented UVM phase method names."""
    phases = re.findall(
        r"(?:virtual\s+)?(?:function|task)\s+\w+\s+(\w+_phase)\s*\(",
        body
    )
    return phases


def _extract_factory_overrides(body: str) -> List[FactoryOverride]:
    """Extract factory override calls."""
    overrides = []
    pattern = re.compile(
        r"(?:set_type_override_by_type|set_inst_override_by_type)\s*\(\s*"
        r"(\w+)::get_type\(\)\s*,\s*(\w+)::get_type\(\)",
        re.MULTILINE
    )
    for match in pattern.finditer(body):
        overrides.append(FactoryOverride(
            original_type=match.group(1),
            override_type=match.group(2),
        ))
    return overrides


def _extract_config_db(body: str, component: str) -> List[ConfigDBEntry]:
    """Extract uvm_config_db set/get calls."""
    entries = []
    pattern = re.compile(
        r"uvm_config_db\s*#\s*\(\s*([^)]+)\s*\)\s*::\s*(set|get)\s*\("
        r"[^,]*,\s*[^,]*,\s*\"(\w+)\"",
        re.MULTILINE
    )
    for match in pattern.finditer(body):
        entries.append(ConfigDBEntry(
            operation=match.group(2),
            field_name=match.group(3),
            value_type=match.group(1).strip(),
            component=component,
        ))
    return entries


def _extract_tlm_connections(body: str, component: str) -> List[TLMConnection]:
    """Extract TLM port.connect() calls."""
    connections = []
    pattern = re.compile(
        r"(\w+)\.(\w+)\.connect\s*\(\s*(\w+)\.(\w+)\s*\)",
        re.MULTILINE
    )
    for match in pattern.finditer(body):
        connections.append(TLMConnection(
            source_component=match.group(1),
            source_port=match.group(2),
            target_component=match.group(3),
            target_port=match.group(4),
        ))
    return connections


def _extract_coverage(filepath: str, content: str) -> List[CoverageInfo]:
    """Extract covergroup definitions."""
    coverages = []
    cg_pattern = re.compile(
        r"covergroup\s+(\w+)[\s\S]*?endgroup",
        re.MULTILINE
    )
    for match in cg_pattern.finditer(content):
        cg_name = match.group(1)
        cg_body = match.group(0)

        coverpoints = re.findall(r"(\w+)\s*:\s*coverpoint", cg_body)
        crosses = re.findall(r"(\w+)\s*:\s*cross", cg_body)

        coverages.append(CoverageInfo(
            name=cg_name,
            file=filepath,
            covergroups=[cg_name],
            coverpoints=coverpoints,
            crosses=crosses,
        ))

    return coverages


def _extract_assertions(filepath: str, content: str) -> List[AssertionInfo]:
    """Extract assertions from TB files."""
    assertions = []
    assert_pattern = re.compile(
        r"(?:(\w+)\s*:\s*)?(assert|assume|cover)\s+(?:property\s*)?\(([^;]+)\)\s*;",
        re.MULTILINE
    )
    for match in assert_pattern.finditer(content):
        assertions.append(AssertionInfo(
            name=match.group(1) or "",
            assertion_type=match.group(2),
            expression=match.group(3).strip(),
            file=filepath,
        ))
    return assertions


def _parse_interface(filepath: str, content: str) -> InterfaceInfo:
    """Parse a SystemVerilog interface."""
    name_match = re.search(r"interface\s+(\w+)", content)
    name = name_match.group(1) if name_match else "unknown"

    # Extract signal declarations
    signals = re.findall(r"(?:logic|wire|reg)\s+(?:\[[\d:]+\]\s+)?(\w+)\s*;", content)

    # Extract clocking blocks
    clocking = re.findall(r"clocking\s+(\w+)", content)

    # Extract modports
    modports = re.findall(r"modport\s+(\w+)", content)

    return InterfaceInfo(
        name=name,
        file=filepath,
        signals=signals,
        clocking_blocks=clocking,
        modports=modports,
    )
