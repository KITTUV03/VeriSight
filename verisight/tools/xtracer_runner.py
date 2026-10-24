"""
x-tracer integration.

Wraps the x-tracer CLI (https://github.com/kuchlous/x-tracer), which
backward-traces a specific (signal, time) query through a gate-level
netlist against a VCD waveform to explain the root cause of an X value.

x-tracer is not pip-installable — it must be cloned locally with its own
Python dependencies (pyslang, pyvcd/pywellen, click). We only ever detect
an existing install; we never clone or install anything automatically.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.utils.logger import get_logger

logger = get_logger("xtracer_runner")

MAX_DERIVED_QUERIES = 5

XTRACER_INSTALL_HINT = (
    "x-tracer was not found. It is not pip-installable — install it manually:\n"
    "  git clone https://github.com/kuchlous/x-tracer.git\n"
    "  cd x-tracer\n"
    "  pip install pyslang pyvcd click\n"
    "Then point VeriSight at it, either by:\n"
    "  export VERISIGHT_XTRACER_PATH=/path/to/x-tracer/x_tracer.py\n"
    "  or: --xtracer-path /path/to/x-tracer/x_tracer.py\n"
    "  or: place the checkout at <verisight repo root>/third_party/x-tracer/"
)

_TIME_UNIT_TO_PS = {
    "ps": 1,
    "ns": 1_000,
    "us": 1_000_000,
    "ms": 1_000_000_000,
}

_NOT_MODULES = {
    "module", "function", "task", "if", "else", "case", "for",
    "while", "assign", "always", "initial", "begin", "end",
    "input", "output", "inout", "wire", "reg", "logic",
    "parameter", "localparam", "generate", "integer",
    "always_ff", "always_comb", "always_latch",
}


class XTracerNotFoundError(RuntimeError):
    """Raised when x-tracer cannot be located locally."""
    pass


@dataclass
class XTraceQuery:
    """A candidate x-tracer query: a set of plausible hierarchical paths
    for one signal, all referring to the same underlying mismatch."""
    field_name: str
    signal_candidates: List[str]
    time_ps: int
    context: str = ""


def find_xtracer(explicit_path: str = "") -> Path:
    """
    Resolve the path to x_tracer.py.

    Resolution order: explicit_path argument > VERISIGHT_XTRACER_PATH env
    var > <repo_root>/third_party/x-tracer/x_tracer.py > PATH lookup.

    Raises:
        XTracerNotFoundError: if no valid location is found.
    """
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))

    env_path = os.getenv("VERISIGHT_XTRACER_PATH")
    if env_path:
        candidates.append(Path(env_path))

    repo_root = Path(__file__).parent.parent.parent
    candidates.append(repo_root / "third_party" / "x-tracer" / "x_tracer.py")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    which_result = shutil.which("x_tracer.py")
    if which_result:
        return Path(which_result)

    raise XTracerNotFoundError(XTRACER_INSTALL_HINT)


def timestamp_to_ps(timestamp: str) -> Optional[int]:
    """Convert a timestamp string like '20 ns' or '150ps' to picoseconds."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(ps|ns|us|ms)?", timestamp, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "ns").lower()
    return int(value * _TIME_UNIT_TO_PS[unit])


def derive_instance_path(tb_files: List[str], top_module: str) -> Optional[str]:
    """
    Best-effort guess at the DUT instance name by scanning TB sources for
    an instantiation of top_module, e.g. `syn_fifo dut(...)` -> "dut".
    """
    if not top_module:
        return None

    inst_pattern = re.compile(
        rf"\b{re.escape(top_module)}\s+(?:#\s*\([^)]*\)\s+)?(\w+)\s*\(",
    )

    for tb_file in tb_files:
        try:
            content = Path(tb_file).read_text(errors="ignore")
        except OSError:
            continue
        match = inst_pattern.search(content)
        if match:
            instance = match.group(1)
            if instance not in _NOT_MODULES:
                return instance

    return None


def signal_priority_score(name: str) -> int:
    """
    Score signal importance for root cause tracing:
    Prioritize control/enable/handshake signals before data-bus bits.
    """
    score = 0
    clean = name.lower().rsplit(".", 1)[-1]
    # Control keywords get higher priority
    ctrl_re = re.compile(
        r"(?:^|_)(valid|ready|enable|en|rst|reset|req|ack|wr|rd|write|read|cmd|ctrl|start|done|state|grant|sel|select|load|we|re)(?:$|_|\d+)"
    )
    if ctrl_re.search(clean):
        score += 100
    # Data bus keywords get lower priority
    data_re = re.compile(
        r"(?:^|_)(data|din|dout|wdata|rdata|addr|address|payload|bus|val|value|result)(?:$|_|\d+)"
    )
    if data_re.search(clean):
        score -= 50
    # Bit slice pattern like [0] or [31]
    if "[" in name:
        score -= 10
    return score


def _clean_signal_name(sig: str) -> str:
    """Strip Verilog escaped identifier markers (leading backslash, trailing whitespace)."""
    s = sig.strip()
    if s.startswith("\\"):
        s = s[1:].strip()
    return s.replace("/", ".")


def resolve_and_validate_signals(
    signal_name: str, knowledge: UnifiedKnowledge, top_module: str
) -> List[str]:
    """
    Validate requested signal against available design or waveform data,
    producing prioritized hierarchical candidates (handling prefixes, escaped IDs,
    hierarchy delimiters, and bit slices).
    Preserves explicitly requested signals verbatim while adding validated aliases.
    """
    candidates = [signal_name]
    clean_sig = _clean_signal_name(signal_name)
    if clean_sig != signal_name:
        candidates.append(clean_sig)

    leaf = clean_sig.rsplit(".", 1)[-1]
    # Also base name without bit indexing (e.g. "data[3]" -> "data")
    base_leaf = re.sub(r"\[\d+(?::\d+)?\]$", "", leaf)

    instance = derive_instance_path(knowledge.tb.file_list, top_module) if knowledge.tb else None
    for s in [clean_sig, leaf]:
        if instance and not s.startswith(instance + "."):
            candidates.append(f"{instance}.{s}")
        if top_module and not s.startswith(top_module + "."):
            candidates.append(f"{top_module}.{s}")

    # Check VCD signals if available to validate and add exact matches / aliases
    if knowledge.vcd and knowledge.vcd.signals:
        vcd_keys = list(knowledge.vcd.signals.keys())
        for vpath in vcd_keys:
            clean_vpath = _clean_signal_name(vpath)
            vleaf = clean_vpath.rsplit(".", 1)[-1]
            vbase = re.sub(r"\[\d+(?::\d+)?\]$", "", vleaf)

            if (
                clean_vpath == clean_sig
                or clean_vpath.endswith(f".{leaf}")
                or vleaf == leaf
                or vbase == base_leaf
                or vpath == signal_name
            ):
                candidates.append(vpath)
                if clean_vpath != vpath:
                    candidates.append(clean_vpath)

    # Check RTL module ports/signals
    if knowledge.rtl and knowledge.rtl.modules:
        for mod in knowledge.rtl.modules:
            for port in mod.ports:
                clean_port = _clean_signal_name(port.name)
                if clean_port in (clean_sig, leaf, base_leaf):
                    if instance:
                        candidates.append(f"{instance}.{clean_port}")
                    if top_module:
                        candidates.append(f"{top_module}.{clean_port}")

    # Deduplicate while preserving insertion order
    return list(dict.fromkeys(candidates))


def derive_queries(
    knowledge: UnifiedKnowledge,
    top_module: str,
    explicit_signals: Optional[List[str]] = None,
    explicit_time_ps: Optional[int] = None,
) -> List[XTraceQuery]:
    """
    Derive x-tracer queries:
    - If explicit_signals provided, validates and preserves them.
    - Otherwise auto-selects signals, prioritizing control/enable signals before data-bus bits.
    """
    queries: List[XTraceQuery] = []

    # 1. Handle explicit signals
    if explicit_signals:
        default_time = explicit_time_ps
        if default_time is None:
            if knowledge.logs.errors:
                default_time = timestamp_to_ps(knowledge.logs.errors[0].timestamp)
            elif knowledge.logs.scoreboard_mismatches:
                default_time = timestamp_to_ps(knowledge.logs.scoreboard_mismatches[0].timestamp)
            if default_time is None:
                default_time = 0

        for sig in explicit_signals:
            candidates = resolve_and_validate_signals(sig, knowledge, top_module)
            queries.append(XTraceQuery(
                field_name=sig,
                signal_candidates=candidates,
                time_ps=default_time,
                context=f"Explicitly requested signal: {sig}",
            ))
        return queries

    # 2. Automatic signal selection
    candidate_items: List[Dict[str, Any]] = []
    seen_fields = set()

    for mismatch in knowledge.logs.scoreboard_mismatches:
        if not mismatch.field or "x" not in mismatch.actual.lower():
            continue
        if mismatch.field in seen_fields:
            continue
        time_ps = timestamp_to_ps(mismatch.timestamp)
        if time_ps is None:
            continue
        candidate_items.append({
            "field": mismatch.field,
            "time_ps": time_ps,
            "context": mismatch.message,
            "priority": signal_priority_score(mismatch.field),
        })
        seen_fields.add(mismatch.field)

    if knowledge.vcd and knowledge.vcd.signals:
        for full_path, sig_wave in knowledge.vcd.signals.items():
            if sig_wave.has_x and sig_wave.name not in seen_fields:
                first_x_time = 0
                for tr in sig_wave.transitions:
                    if "x" in tr.value.lower():
                        first_x_time = tr.time_ps
                        break
                candidate_items.append({
                    "field": full_path,
                    "time_ps": first_x_time,
                    "context": f"VCD waveform X detected on {full_path}",
                    "priority": signal_priority_score(full_path),
                })
                seen_fields.add(sig_wave.name)

    # Sort by priority: control/enable signals before data-bus bits!
    candidate_items.sort(key=lambda item: item["priority"], reverse=True)

    for item in candidate_items[:MAX_DERIVED_QUERIES]:
        candidates = resolve_and_validate_signals(item["field"], knowledge, top_module)
        queries.append(XTraceQuery(
            field_name=item["field"],
            signal_candidates=candidates,
            time_ps=item["time_ps"],
            context=item["context"],
        ))

    return queries


def run_xtracer(
    xtracer_path: Path,
    netlists: List[Path],
    vcd: Path,
    signal: str,
    time_ps: int,
    max_depth: int = 100,
) -> Dict[str, Any]:
    """
    Invoke x-tracer for a single (signal, time) query and return the
    parsed JSON cause tree.

    Raises:
        RuntimeError: if x-tracer exits non-zero or emits invalid JSON.
    """
    cmd = ["python3", str(xtracer_path)]
    for netlist in netlists:
        cmd += ["-n", str(netlist)]
    cmd += [
        "-v", str(vcd),
        "-s", signal,
        "-t", str(time_ps),
        "-f", "json",
        "--max-depth", str(max_depth),
    ]

    logger.info(f"Running x-tracer: signal={signal} time={time_ps}ps")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"x-tracer failed for signal '{signal}' @ {time_ps}ps "
            f"(exit {result.returncode}):\n{result.stderr or result.stdout}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"x-tracer produced invalid JSON for signal '{signal}' @ {time_ps}ps: {e}"
        )


def run_xtracer_with_candidates(
    xtracer_path: Path,
    netlists: List[Path],
    vcd: Path,
    candidates: List[str],
    time_ps: int,
    max_depth: int = 100,
) -> Dict[str, Any]:
    """
    Try each candidate hierarchical signal path in order (since the exact
    VCD scope naming can't be known statically) and return the first
    successful trace.

    Raises:
        RuntimeError: the last candidate's error, if all candidates fail.
    """
    last_error: Optional[Exception] = None

    for candidate in candidates:
        try:
            return run_xtracer(xtracer_path, netlists, vcd, candidate, time_ps, max_depth)
        except RuntimeError as e:
            logger.warning(f"x-tracer candidate signal '{candidate}' failed: {e}")
            last_error = e

    raise last_error or RuntimeError("No signal candidates provided")
