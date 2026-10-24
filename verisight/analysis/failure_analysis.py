"""
Deterministic failure-stage and primary-event analysis.

This module answers two questions that the original pipeline conflated:

  1. **What stage did the run fail at?**  A compile or elaboration error is a
     different kind of problem from a runtime assertion/scoreboard failure, and
     must never be reported as a passing run just because it carries no
     ``UVM_ERROR`` token.  ``detect_tool_errors`` recognises the native error
     formats of the common simulators (Verilator, VCS, Questa/ModelSim,
     Xcelium, Icarus) so these failures are no longer silently dropped.

  2. **Which failure is causally first?**  The earliest-in-time meaningful
     failure is a far better root-cause anchor than the first line printed or
     the most prominent message.  ``select_primary_event`` orders events by
     stage (compile → elaboration → runtime) and then by simulation time,
     returning the primary event plus the cascade of later symptoms.

All functions are pure and unit-testable without an LLM or a simulator.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ── time handling (unit-aware) ──────────────────────────────────────────────

_UNIT_TO_NS = {
    "fs": 1e-6, "ps": 1e-3, "ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9,
}
_TIME_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(fs|ps|ns|us|ms|s)?", re.IGNORECASE)


def parse_time_to_ns(ts: Optional[str]) -> Optional[float]:
    """Convert a timestamp string like '650000 ns' or '100 ps' to nanoseconds.

    Returns None when no numeric time can be parsed. Unit-aware so that a
    '500 ps' event correctly sorts before a '1 ns' event (the original parser
    hardcoded every unit to 'ns', corrupting cross-unit ordering).
    """
    if not ts:
        return None
    m = _TIME_RE.search(str(ts).strip())
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    unit = (m.group(2) or "ns").lower()
    return value * _UNIT_TO_NS.get(unit, 1.0)


# ── simulator-native compile / elaboration error detection ──────────────────
# Each entry: (compiled regex, stage, tool). Matched against a single line.
# These catch the failures that carry NO UVM_* severity token and would
# otherwise parse to zero errors -> a false PASS.

_TOOL_ERROR_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # Verilator:  %Error: file.sv:line: msg   /  %Error-WIDTH: ...
    (re.compile(r"%(Error|Warning)[-A-Z]*:\s*(.+)", re.IGNORECASE), "compile", "verilator"),
    # Synopsys VCS: "Error-[SE] Syntax error" / "Error-[...] ..."
    (re.compile(r"\bError-\[[A-Z0-9_]+\]\s*(.+)", re.IGNORECASE), "compile", "vcs"),
    # Questa/ModelSim: "** Error: (vlog-NNNN) file(line): msg" / "** Error (vsim-...)"
    (re.compile(r"\*\*\s*Error[:\s].*?(?:\(v(?:log|sim|opt|com)-\d+\))?\s*(.+)", re.IGNORECASE), "compile", "questa"),
    # Cadence Xcelium/NCSim: "xmelab: *E,..." / "xmvlog: *E,..." (elab vs compile)
    (re.compile(r"\bxm(elab|sim):\s*\*[EF],\s*(.+)", re.IGNORECASE), "elaboration", "xcelium"),
    (re.compile(r"\bxm(vlog|sv):\s*\*[EF],\s*(.+)", re.IGNORECASE), "compile", "xcelium"),
    # Icarus Verilog / generic GCC-style: "file.sv:line: error: msg"
    (re.compile(r"[\w./\\-]+\.(?:sv|svh|v|vh):\d+:\s*error:\s*(.+)", re.IGNORECASE), "compile", "iverilog"),
    # Generic syntax / elaboration phrases.
    (re.compile(r"\b(syntax error)\b(.*)", re.IGNORECASE), "compile", "generic"),
    (re.compile(r"\b(unknown module type|module .* not found|cannot find|undefined (?:module|macro|variable)|unresolved reference)\b(.*)", re.IGNORECASE), "elaboration", "generic"),
    (re.compile(r"\b(elaboration (?:error|failed)|error during elaboration)\b(.*)", re.IGNORECASE), "elaboration", "generic"),
]

# Lines that merely summarise a build failure (used to confirm a compile stage
# even if the specific per-error line format was not recognised).
_BUILD_FAIL_RE = re.compile(
    r"(exiting due to \d+ error|compilation (?:failed|aborted)|"
    r"\*\*\* \[.*\] error \d+|make(?:\[\d+\])?:.*error|command failed)",
    re.IGNORECASE,
)

# Negative guard: do not treat a UVM runtime message as a compile error even if
# it contains the word "Error" (e.g. "UVM_ERROR ... PROTOCOL MISMATCH").
_UVM_TOKEN_RE = re.compile(r"\bUVM_(INFO|WARNING|ERROR|FATAL)\b")


def detect_tool_errors(lines: List[str]) -> List[Dict[str, Any]]:
    """Detect simulator-native compile/elaboration errors in raw log lines.

    Returns a list of dicts: {line_no (1-based), text, stage, tool}. Lines that
    carry a UVM severity token are skipped (those are runtime events handled by
    the UVM parser).
    """
    out: List[Dict[str, Any]] = []
    for i, line in enumerate(lines):
        if _UVM_TOKEN_RE.search(line):
            continue
        stripped = line.strip().lstrip("# ").strip()  # tolerate Questa '#' transcript prefix
        if not stripped:
            continue
        for pat, stage, tool in _TOOL_ERROR_PATTERNS:
            m = pat.search(stripped)
            if m:
                out.append({
                    "line_no": i + 1,
                    "text": stripped,
                    "stage": stage,
                    "tool": tool,
                })
                break
    return out


def has_build_failure_marker(content: str) -> bool:
    """True if the log contains an explicit build/compile failure summary line."""
    return bool(_BUILD_FAIL_RE.search(content or ""))


# ── failure stage + primary event selection ─────────────────────────────────

def determine_failure_stage(
    tool_errors: List[Dict[str, Any]],
    runtime_failed: bool,
    build_marker: bool,
) -> str:
    """Return the earliest stage at which the run failed.

    'compile' | 'elaboration' | 'runtime' | 'none'. Compile/elaboration take
    precedence because a design that does not compile never reaches runtime.
    """
    stages = {e["stage"] for e in tool_errors}
    if "compile" in stages:
        return "compile"
    if "elaboration" in stages:
        return "elaboration"
    if build_marker and not runtime_failed:
        # Build summary present but no specific line recognised and nothing ran.
        return "compile"
    if runtime_failed:
        return "runtime"
    return "none"


def _runtime_events(log: Any) -> List[Dict[str, Any]]:
    """Collect timestamped runtime failure events from a LogKnowledge object."""
    events: List[Dict[str, Any]] = []

    for e in getattr(log, "fatals", []) or []:
        events.append(_mk_event("fatal", e.timestamp, e.message, getattr(e, "file", ""),
                                getattr(e, "line", 0), "UVM_FATAL",
                                getattr(e, "line_number_in_log", 0)))
    for e in getattr(log, "errors", []) or []:
        events.append(_mk_event("error", e.timestamp, e.message, getattr(e, "file", ""),
                                getattr(e, "line", 0), "UVM_ERROR",
                                getattr(e, "line_number_in_log", 0)))
    for a in getattr(log, "assertion_failures", []) or []:
        events.append(_mk_event("assertion", a.timestamp, a.message or a.assertion_name,
                                getattr(a, "file", ""), getattr(a, "line", 0),
                                "ASSERTION", 0))
    for m in getattr(log, "scoreboard_mismatches", []) or []:
        events.append(_mk_event("mismatch", m.timestamp, m.message,
                                "", 0, "MISMATCH", 0))
    return events


def _mk_event(kind, timestamp, message, file, line, severity, log_line) -> Dict[str, Any]:
    return {
        "kind": kind,
        "timestamp": timestamp or "",
        "time_ns": parse_time_to_ns(timestamp),
        "message": (message or "").strip(),
        "file": file or "",
        "line": line or 0,
        "severity": severity,
        "log_line": log_line or 0,
    }


# Rank for breaking ties when times are equal/absent. Fatals are terminal, an
# assertion/mismatch is usually closer to the cause than a generic UVM_ERROR
# that may just be the "** TEST FAILED **"-style aggregate.
_KIND_RANK = {"fatal": 0, "assertion": 1, "mismatch": 1, "error": 2}


def select_primary_event(log: Any, tool_errors: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Choose the earliest causally-relevant failure as the root-cause anchor.

    Priority: compile error → elaboration error → earliest-in-time runtime
    event (ties broken by kind rank, then by log position). Returns a dict
    describing the primary event with a human-readable ``rationale`` explaining
    *why* it was chosen, or None if there is no failure at all.
    """
    compile_errs = [e for e in tool_errors if e["stage"] == "compile"]
    elab_errs = [e for e in tool_errors if e["stage"] == "elaboration"]

    if compile_errs:
        first = min(compile_errs, key=lambda e: e["line_no"])
        return {
            "kind": "compile_error", "stage": "compile",
            "timestamp": "", "time_ns": None,
            "message": first["text"], "file": "", "line": 0,
            "severity": "COMPILE", "log_line": first["line_no"],
            "rationale": (
                f"Compilation failed ({first['tool']}); no simulation ran. "
                "A compile error is the root failure regardless of any later output."
            ),
        }
    if elab_errs:
        first = min(elab_errs, key=lambda e: e["line_no"])
        return {
            "kind": "elaboration_error", "stage": "elaboration",
            "timestamp": "", "time_ns": None,
            "message": first["text"], "file": "", "line": 0,
            "severity": "ELABORATION", "log_line": first["line_no"],
            "rationale": (
                f"Elaboration failed ({first['tool']}); the design was not built. "
                "This precedes and causes any runtime symptoms."
            ),
        }

    events = _runtime_events(log)
    if not events:
        return None

    def sort_key(e: Dict[str, Any]):
        # Events with a known time sort first by time; unknown-time events go
        # last (large sentinel) but keep their log order.
        t = e["time_ns"]
        return (
            0 if t is not None else 1,
            t if t is not None else 0.0,
            _KIND_RANK.get(e["kind"], 3),
            e["log_line"] or 10**9,
        )

    events.sort(key=sort_key)
    primary = dict(events[0])
    primary["stage"] = "runtime"
    n_later = len(events) - 1
    primary["rationale"] = (
        f"Earliest runtime failure at t={primary['timestamp'] or 'unknown'} "
        f"({primary['kind']}); {n_later} later event(s) are candidate downstream "
        "symptoms pending causal confirmation."
    )
    return primary


def build_cascade(log: Any, primary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return runtime events after the primary one, as *candidate* symptoms.

    Labelled 'candidate' deliberately: temporal order is evidence of a possible
    cascade, not proof of causation.
    """
    if not primary or primary.get("stage") != "runtime":
        return []
    events = _runtime_events(log)

    def sort_key(e):
        t = e["time_ns"]
        return (0 if t is not None else 1, t if t is not None else 0.0, e["log_line"] or 10**9)

    events.sort(key=sort_key)
    # Drop the first (primary) and return the rest, de-duplicated by (message).
    seen = set()
    cascade = []
    for e in events[1:]:
        key = (e["kind"], e["message"][:120])
        if key in seen:
            continue
        seen.add(key)
        cascade.append(e)
    return cascade
