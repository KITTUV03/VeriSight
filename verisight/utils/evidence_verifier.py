"""
Evidence / citation verifier.

Anti-hallucination safeguard: checks that the file:line and file citations an
LLM puts into a Classification actually correspond to something in the supplied
inputs (RTL/TB/spec source files or filenames printed in the log). Citations
that cannot be substantiated are reported so the caller can strip/flag them and
lower confidence. This closes the gap where the base agent validated only JSON
*shape*, letting an invented `foo.sv:42` pass through as fact.

It catches the concrete, checkable half of hallucination (invented file paths /
out-of-range line numbers). It does not claim to catch semantic hallucination
(a real line cited for the wrong reason) — that is left to the LLM's own
reasoning plus human review.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

_FILE_TOKEN = re.compile(r"\b([A-Za-z0-9_./\\-]+\.(?:sv|svh|v|vh))\b")
_FILE_LINE = re.compile(r"\b([A-Za-z0-9_./\\-]+\.(?:sv|svh|v|vh))\s*[:(]\s*(\d+)\s*\)?")


def build_known_files(knowledge: Any) -> Dict[str, int]:
    """Collect {basename -> line_count} of every file the pipeline actually saw.

    line_count 0 means "known to exist but not range-checkable" (e.g. a file
    named only inside the log). Sources: parsed RTL/TB file lists, the spec and
    log file names, and any HDL filename printed in the log entries.
    """
    known: Dict[str, int] = {}

    def add(path: str, count: int = 0):
        if not path:
            return
        known.setdefault(Path(path).name.lower(), count)

    rtl = getattr(knowledge, "rtl", None)
    if rtl is not None:
        for m in getattr(rtl, "modules", []) or []:
            add(getattr(m, "file", ""), getattr(m, "line_count", 0) or 0)
        for f in getattr(rtl, "file_list", []) or []:
            add(f)
    tb = getattr(knowledge, "tb", None)
    if tb is not None:
        for f in getattr(tb, "file_list", []) or []:
            add(f)
    spec = getattr(knowledge, "spec", None)
    if spec is not None:
        add(getattr(spec, "source_file", "") or getattr(spec, "file", ""))

    log = getattr(knowledge, "logs", None)
    if log is not None:
        for e in getattr(log, "entries", []) or []:
            add(getattr(e, "file", ""))
            for m in _FILE_TOKEN.finditer(getattr(e, "raw_line", "") or ""):
                add(m.group(1))
        for a in getattr(log, "assertion_failures", []) or []:
            add(getattr(a, "file", ""))
        for te in getattr(log, "tool_errors", []) or []:
            for m in _FILE_TOKEN.finditer(getattr(te, "text", "") or ""):
                add(m.group(1))
    return known


def _classification_text(classification: Any) -> str:
    """Gather the free-text/reference fields of a Classification (model or dict)."""
    def g(obj, name, default=""):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    parts: List[str] = [
        str(g(classification, "reason")),
        str(g(classification, "rtl_reference")),
        str(g(classification, "tb_reference")),
        str(g(classification, "spec_reference")),
        str(g(classification, "recommended_fix")),
    ]
    for ev in g(classification, "evidence", []) or []:
        parts.append(str(g(ev, "reference")))
        parts.append(str(g(ev, "description")))
        parts.append(str(g(ev, "snippet")))
    return "\n".join(parts)


def verify_citations(classification: Any, knowledge: Any) -> List[str]:
    """Return a list of human-readable unsupported-citation problems (empty = clean)."""
    known = build_known_files(knowledge)
    text = _classification_text(classification)
    problems: List[str] = []

    for m in _FILE_LINE.finditer(text):
        fname = Path(m.group(1)).name.lower()
        line = int(m.group(2))
        if fname not in known:
            problems.append(f"cites file not present in inputs: '{m.group(1)}' ({m.group(0)})")
        elif known[fname] and line > known[fname]:
            problems.append(f"cites {m.group(1)}:{line} but that file has only {known[fname]} lines")

    for m in _FILE_TOKEN.finditer(text):
        fname = Path(m.group(1)).name.lower()
        if fname not in known and not any(fname in p for p in problems):
            problems.append(f"cites file not present in inputs: '{m.group(1)}'")

    # de-dup, preserve order
    seen, out = set(), []
    for p in problems:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out
