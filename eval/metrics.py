"""
Scoring metrics for the VeriSight debugging-workflow evaluation.

Every metric is automatically checkable against a ground-truth record so that
baseline vs improved runs are comparable. Metrics are intentionally
conservative: substring / keyword / citation-existence checks that do not
require an LLM judge, so scores are deterministic given a pipeline output.

Where ground truth cannot be established by automation (e.g. subtle wording of
a root cause), we fall back to keyword recall and flag the case for human
review rather than inventing a pass/fail.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── citation extraction / verification ──────────────────────────────────────

_FILE_TOKEN = re.compile(r"\b([A-Za-z0-9_./\\-]+\.(?:sv|svh|v|vh))\b")
_FILE_LINE = re.compile(
    r"\b([A-Za-z0-9_./\\-]+\.(?:sv|svh|v|vh))\s*[:(]\s*(\d+)\s*\)?"
)
_LINE_PHRASE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)


def _collect_text_and_refs(classification: Dict[str, Any]) -> str:
    """Concatenate all free-text + reference fields that may carry citations."""
    parts: List[str] = [
        str(classification.get("reason", "")),
        str(classification.get("component", "")),
        str(classification.get("category", "")),
        str(classification.get("rtl_reference", "")),
        str(classification.get("tb_reference", "")),
        str(classification.get("spec_reference", "")),
        str(classification.get("log_reference", "")),
        str(classification.get("recommended_fix", "")),
    ]
    for ev in classification.get("evidence", []) or []:
        parts.append(str(ev.get("reference", "")))
        parts.append(str(ev.get("description", "")))
        parts.append(str(ev.get("snippet", "")))
    for step in classification.get("reasoning_chain", []) or []:
        parts.append(str(step.get("observation", "")))
        parts.append(str(step.get("inference", "")))
    return "\n".join(parts)


def index_source_files(input_paths: Dict[str, str], repo_root: Path) -> Dict[str, int]:
    """
    Build {basename.sv -> line_count} for every HDL file reachable from the
    case inputs. Used to verify that cited file:line references actually exist.

    Files that are not provided as HDL sources but ARE named verbatim inside a
    provided text input (e.g. a filename printed in the simulation log) are
    added with a line count of 0, meaning "known to exist, but line numbers
    cannot be range-checked". This prevents flagging a citation that faithfully
    quotes the log (the opposite of a hallucination) as unsupported.
    """
    index: Dict[str, int] = {}
    exts = {".sv", ".svh", ".v", ".vh"}
    text_blobs: List[str] = []
    for key, rel in input_paths.items():
        if not rel:
            continue
        p = (repo_root / rel).resolve()
        candidates: List[Path] = []
        if p.is_dir():
            candidates = [q for q in p.rglob("*") if q.suffix.lower() in exts]
        elif p.is_file() and p.suffix.lower() in exts:
            candidates = [p]
        elif p.is_file():
            # Non-HDL input (log, spec, coverage): keep its text for mention scan.
            try:
                text_blobs.append(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        for q in candidates:
            try:
                n = sum(1 for _ in q.open("r", encoding="utf-8", errors="replace"))
            except OSError:
                n = 0
            index[q.name.lower()] = n

    # Filenames mentioned verbatim in provided text inputs count as grounded.
    for blob in text_blobs:
        for m in _FILE_TOKEN.finditer(blob):
            fname = Path(m.group(1)).name.lower()
            index.setdefault(fname, 0)
    return index


def unsupported_citations(
    classification: Dict[str, Any], source_index: Dict[str, int]
) -> List[str]:
    """
    Return a list of file:line citations that cannot be substantiated:
      - a cited HDL filename that is not among the case input files, or
      - a cited line number beyond that file's length.

    This is the automatable proxy for the Phase-5 "unsupported claim" metric:
    it catches the concrete, checkable half of hallucination (invented file
    paths / out-of-range line numbers). It does NOT claim to catch semantic
    hallucination (a real line cited for a wrong reason).
    """
    text = _collect_text_and_refs(classification)
    problems: List[str] = []

    for m in _FILE_LINE.finditer(text):
        fname = Path(m.group(1)).name.lower()
        line = int(m.group(2))
        if fname not in source_index:
            problems.append(f"cites non-existent file '{m.group(1)}' (as {m.group(0)})")
        elif source_index[fname] and line > source_index[fname]:
            problems.append(
                f"cites {m.group(1)}:{line} but file has only "
                f"{source_index[fname]} lines"
            )

    # Bare filenames with no line that still don't exist in the input set.
    for m in _FILE_TOKEN.finditer(text):
        fname = Path(m.group(1)).name.lower()
        if fname not in source_index:
            msg = f"cites unknown file '{m.group(1)}'"
            if msg not in problems and not any(fname in p for p in problems):
                problems.append(msg)

    # De-duplicate while preserving order.
    seen = set()
    out = []
    for p in problems:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ── per-case scoring ────────────────────────────────────────────────────────

def _contains_any(haystack: str, needles: List[str]) -> bool:
    h = haystack.lower()
    return any(n.lower() in h for n in needles)


def score_case(
    case: Dict[str, Any],
    classification: Dict[str, Any],
    report: Optional[Dict[str, Any]],
    source_index: Dict[str, int],
) -> Dict[str, Any]:
    """Score one pipeline output against one ground-truth case record."""
    gt = case["ground_truth"]
    text = _collect_text_and_refs(classification)
    report_text = ""
    if report:
        report_text = "\n".join(
            str(report.get(k, "")) for k in ("root_cause", "classification", "category")
        )
    full_text = text + "\n" + report_text

    result: Dict[str, Any] = {"case_id": case["id"], "title": case.get("title", "")}

    pred = str(classification.get("classification", "")).strip()
    result["predicted_classification"] = pred
    result["confidence"] = classification.get("confidence")

    reason_l = str(classification.get("reason", "")).lower()

    # Robustness case: a failure that the parser must not silently classify as
    # "passed / no failure" (e.g. a compile or elaboration error with no UVM
    # error lines). Correct behaviour: detect that something failed.
    if gt.get("must_detect_failure"):
        looks_like_false_pass = (
            pred == "Unknown"
            and ("no failure" in reason_l or "passed" in reason_l or "pass" == reason_l.strip())
        )
        result["expected"] = "DETECT_FAILURE (not a clean pass)"
        result["failure_detected"] = not looks_like_false_pass
        result["classification_match"] = not looks_like_false_pass
        cat_keys = gt.get("category_keywords", [])
        result["category_hit"] = _contains_any(full_text, cat_keys) if cat_keys else None
        result["unsupported_citations"] = unsupported_citations(classification, source_index)
        result["unsupported_citation_count"] = len(result["unsupported_citations"])
        return result

    # Negative / insufficient-evidence cases: correct behaviour is to abstain.
    if gt.get("expect_insufficient_evidence"):
        abstained = (
            pred == "Unknown"
            or bool(classification.get("missing_artifacts"))
            or (isinstance(classification.get("confidence"), (int, float))
                and classification["confidence"] < gt.get("max_confidence_if_abstain", 50))
        )
        result["expected"] = "INSUFFICIENT_EVIDENCE / abstain"
        result["correct_abstention"] = abstained
        result["classification_match"] = abstained
        result["unsupported_citations"] = unsupported_citations(classification, source_index)
        result["unsupported_citation_count"] = len(result["unsupported_citations"])
        return result

    # Positive cases.
    result["expected_classification"] = gt["classification"]
    result["classification_match"] = (pred == gt["classification"])

    cat_keys = gt.get("category_keywords", [])
    result["category_hit"] = (
        _contains_any(str(classification.get("category", "")), cat_keys)
        or _contains_any(full_text, cat_keys)
        if cat_keys else None
    )

    rc_all = gt.get("root_cause_keywords_all", [])
    rc_any = gt.get("root_cause_keywords_any", [])
    if rc_all:
        # Every keyword must appear (used when the root cause is unambiguous).
        hits = [k for k in rc_all if k.lower() in full_text.lower()]
        result["root_cause_recall"] = round(len(hits) / len(rc_all), 3)
        result["root_cause_missing"] = [k for k in rc_all if k.lower() not in full_text.lower()]
    elif rc_any:
        # At least one acceptable focus must appear (used for multi-defect
        # cases where several distinct correct diagnoses exist).
        present = [k for k in rc_any if k.lower() in full_text.lower()]
        result["root_cause_recall"] = 1.0 if present else 0.0
        result["root_cause_any_present"] = present
    else:
        result["root_cause_recall"] = None

    files = gt.get("responsible_files", [])
    result["responsible_file_cited"] = _contains_any(full_text, files) if files else None

    fce = gt.get("first_causal_error_substring")
    if fce:
        result["first_causal_error_identified"] = fce.lower() in full_text.lower()
    else:
        result["first_causal_error_identified"] = None

    result["unsupported_citations"] = unsupported_citations(classification, source_index)
    result["unsupported_citation_count"] = len(result["unsupported_citations"])

    # Forbidden-claim traps (demo-default leakage, e.g. "apb_slave" on a non-APB case).
    forbidden = (case.get("fabrication_guard") or {}).get("forbidden_claims", [])
    hits = [f for f in forbidden if f.lower() in full_text.lower()]
    result["forbidden_claim_hits"] = hits

    return result


def _rate(values: List[Optional[bool]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(1 for v in vals if v) / len(vals), 3)


def aggregate(case_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-case scores into summary metrics."""
    positives = [s for s in case_scores if "expected_classification" in s]
    negatives = [s for s in case_scores if s.get("expected", "").startswith("INSUFFICIENT")]
    robustness = [s for s in case_scores if s.get("expected", "").startswith("DETECT_FAILURE")]

    def recall_mean():
        vals = [s["root_cause_recall"] for s in positives if s.get("root_cause_recall") is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    total_unsupported = sum(s.get("unsupported_citation_count", 0) for s in case_scores)
    total_forbidden = sum(len(s.get("forbidden_claim_hits", [])) for s in case_scores)

    return {
        "n_cases": len(case_scores),
        "n_positive": len(positives),
        "n_negative": len(negatives),
        "classification_top1_accuracy": _rate([s.get("classification_match") for s in positives]),
        "category_accuracy": _rate([s.get("category_hit") for s in positives]),
        "root_cause_keyword_recall_mean": recall_mean(),
        "responsible_file_citation_accuracy": _rate([s.get("responsible_file_cited") for s in positives]),
        "first_causal_error_accuracy": _rate([s.get("first_causal_error_identified") for s in positives]),
        "insufficient_evidence_abstention_accuracy": _rate([s.get("correct_abstention") for s in negatives]),
        "failure_detection_accuracy": _rate([s.get("failure_detected") for s in robustness]),
        "unsupported_citation_total": total_unsupported,
        "unsupported_citation_cases": sum(1 for s in case_scores if s.get("unsupported_citation_count", 0) > 0),
        "forbidden_claim_total": total_forbidden,
        "mean_confidence_positive": (
            round(sum(s["confidence"] for s in positives if isinstance(s.get("confidence"), (int, float)))
                  / max(1, sum(1 for s in positives if isinstance(s.get("confidence"), (int, float)))), 1)
            if positives else None
        ),
    }
