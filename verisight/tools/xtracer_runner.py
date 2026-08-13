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


def derive_queries(knowledge: UnifiedKnowledge, top_module: str) -> List[XTraceQuery]:
    """
    Auto-derive x-tracer queries from scoreboard mismatches whose actual
    value contains an X, e.g. ScoreboardMismatch(field="result",
    actual="xx", timestamp="20 ns") -> a query for signal "result" @ 20000ps.

    Caps at MAX_DERIVED_QUERIES distinct fields to bound runtime.
    """
    instance = derive_instance_path(knowledge.tb.file_list, top_module)

    queries: List[XTraceQuery] = []
    seen_fields = set()

    for mismatch in knowledge.logs.scoreboard_mismatches:
        if not mismatch.field or "x" not in mismatch.actual.lower():
            continue
        if mismatch.field in seen_fields:
            continue

        time_ps = timestamp_to_ps(mismatch.timestamp)
        if time_ps is None:
            continue

        candidates = []
        if instance:
            candidates.append(f"{instance}.{mismatch.field}")
        if top_module:
            candidates.append(f"{top_module}.{mismatch.field}")
        candidates.append(mismatch.field)
        # Dedup while preserving order.
        candidates = list(dict.fromkeys(candidates))

        queries.append(XTraceQuery(
            field_name=mismatch.field,
            signal_candidates=candidates,
            time_ps=time_ps,
            context=mismatch.message,
        ))
        seen_fields.add(mismatch.field)

        if len(queries) >= MAX_DERIVED_QUERIES:
            break

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
