#!/usr/bin/env python3
"""
VeriSight debugging-workflow evaluation runner.

Runs the FULL VeriSightPipeline (Agents 1-5) on each ground-truth case and
scores the result with eval/metrics.py. Designed for reproducible before/after
comparison: it never modifies verisight/ and isolates ChromaDB per run so RAG
state does not leak between cases or between baseline/after runs.

Usage:
    python -m eval.run_eval --cases eval/cases --out output/eval/baseline \
        --rag isolated --repeats 1 --tag baseline

    # offline (no API spend) — exercises the deterministic fallback path:
    python -m eval.run_eval --no-llm --tag baseline-offline

Outputs:
    <out>/eval_report.json   full machine-readable results
    <out>/eval_report.md     human-readable summary table
    <out>/cases/<id>/...     each case's raw pipeline artifacts
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval import metrics  # noqa: E402


def load_cases(cases_dir: Path, only: Optional[List[str]]) -> List[Dict[str, Any]]:
    cases = []
    for f in sorted(cases_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if only and data["id"] not in only:
            continue
        cases.append(data)
    return cases


def _abs(rel: Optional[str]) -> Optional[str]:
    if not rel:
        return None
    return str((REPO_ROOT / rel).resolve())


def run_one_case(
    case: Dict[str, Any],
    out_dir: Path,
    rag_mode: str,
    no_llm: bool,
    shared_chroma: Optional[str],
    model: Optional[str],
    provider: Optional[str],
) -> Dict[str, Any]:
    """Run the pipeline once for a case and return the parsed artifacts."""
    from verisight.config import VeriSightConfig

    case_out = out_dir / "cases" / case["id"]
    case_out.mkdir(parents=True, exist_ok=True)

    # Isolate ChromaDB so RAG state is reproducible and never pollutes the
    # project knowledge DB during evaluation.
    if rag_mode == "isolated":
        chroma_path = case_out / "_chroma"
    elif rag_mode == "shared":
        chroma_path = Path(shared_chroma) if shared_chroma else (out_dir / "_chroma_shared")
    else:  # off
        chroma_path = case_out / "_chroma_unused"

    if provider:
        os.environ["VERISIGHT_PROVIDER"] = provider
    if model:
        os.environ["VERISIGHT_MODEL"] = model
    if no_llm:
        # Force deterministic fallback: blank keys so every LLM call raises and
        # agents fall back to their heuristic paths.
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["CLAUDE_API_KEY"] = ""

    config = VeriSightConfig()
    config.pipeline.output_dir = str(case_out)
    config.pipeline.enable_rag = (rag_mode != "off")
    config.chroma.persist_path = str(chroma_path)
    if no_llm:
        config.llm.api_key = ""

    inputs = case["inputs"]
    record: Dict[str, Any] = {
        "effective_provider": config.llm.provider,
        "effective_model": config.llm.model_name,
        "rag_mode": rag_mode,
    }

    from verisight.orchestrator import VeriSightPipeline

    try:
        pipeline = VeriSightPipeline(config)
        pipeline.run(
            spec_path=_abs(inputs.get("spec")),
            rtl_path=_abs(inputs.get("rtl")),
            tb_path=_abs(inputs.get("tb")),
            log_path=_abs(inputs.get("log")),
            coverage_path=_abs(inputs.get("coverage")),
            vcd_path=_abs(inputs.get("vcd")),
        )
        record["error"] = None
    except Exception as e:  # noqa: BLE001
        record["error"] = f"{type(e).__name__}: {e}"
        record["traceback"] = traceback.format_exc()

    # Parse artifacts the pipeline wrote.
    summary_path = case_out / "summary.json"
    report_path = case_out / "error.json"
    record["classification"] = (
        json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    )
    record["report"] = (
        json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    )
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description="VeriSight debugging eval runner")
    ap.add_argument("--cases", default="eval/cases", help="dir of case JSON files")
    ap.add_argument("--out", default="output/eval/run", help="output dir")
    ap.add_argument("--rag", choices=["isolated", "off", "shared"], default="isolated")
    ap.add_argument("--repeats", type=int, default=1, help="runs per case (consistency)")
    ap.add_argument("--only", nargs="*", help="only these case ids")
    ap.add_argument("--no-llm", action="store_true", help="force deterministic fallback (no API)")
    ap.add_argument("--model", default=None, help="override VERISIGHT_MODEL")
    ap.add_argument("--provider", default=None, help="override VERISIGHT_PROVIDER")
    ap.add_argument("--tag", default="run", help="label for this run")
    args = ap.parse_args()

    cases_dir = (REPO_ROOT / args.cases).resolve()
    out_dir = (REPO_ROOT / args.out).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = load_cases(cases_dir, args.only)
    if not cases:
        print(f"No cases found in {cases_dir}", file=sys.stderr)
        return 2

    print(f"[eval:{args.tag}] {len(cases)} cases, repeats={args.repeats}, rag={args.rag}, no_llm={args.no_llm}")

    all_case_scores: List[Dict[str, Any]] = []
    per_case_runs: Dict[str, List[Dict[str, Any]]] = {}

    for case in cases:
        source_index = metrics.index_source_files(case["inputs"], REPO_ROOT)
        runs: List[Dict[str, Any]] = []
        for r in range(args.repeats):
            rep_out = out_dir if args.repeats == 1 else (out_dir / f"rep{r}")
            rep_out.mkdir(parents=True, exist_ok=True)
            print(f"  - {case['id']} (rep {r+1}/{args.repeats}) ...", flush=True)
            rec = run_one_case(
                case, rep_out, args.rag, args.no_llm, None, args.model, args.provider
            )
            score = metrics.score_case(case, rec.get("classification", {}), rec.get("report", {}), source_index)
            score["effective_model"] = rec.get("effective_model")
            score["pipeline_error"] = rec.get("error")
            runs.append(score)
            if rec.get("error"):
                print(f"      pipeline error: {rec['error']}")
        per_case_runs[case["id"]] = runs
        # Use first repeat as the representative score; add consistency info.
        rep0 = runs[0]
        if args.repeats > 1:
            labels = [x.get("predicted_classification") for x in runs]
            rep0["label_consistency"] = round(
                max(labels.count(l) for l in set(labels)) / len(labels), 3
            )
            rep0["labels_across_repeats"] = labels
        all_case_scores.append(rep0)

    summary = metrics.aggregate(all_case_scores)
    report = {
        "tag": args.tag,
        "config": {"rag": args.rag, "repeats": args.repeats, "no_llm": args.no_llm,
                   "model": args.model, "provider": args.provider},
        "summary": summary,
        "cases": all_case_scores,
    }
    (out_dir / "eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "eval_report.md").write_text(render_markdown(report), encoding="utf-8")

    print("\n" + render_markdown(report))
    print(f"\n[eval:{args.tag}] wrote {out_dir/'eval_report.json'}")
    return 0


def render_markdown(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"# VeriSight Debugging Eval — `{report['tag']}`",
        "",
        f"- config: {report['config']}",
        "",
        "## Summary metrics",
        "",
        "| metric | value |",
        "|---|---|",
    ]
    for k, v in s.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Per-case", "",
              "| case | expected | predicted | match | cat | rc_recall | file_cited | first_err | conf | bad_cites |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for c in report["cases"]:
        exp = c.get("expected_classification", c.get("expected", "?"))
        lines.append(
            f"| {c['case_id']} | {exp} | {c.get('predicted_classification','')} | "
            f"{_b(c.get('classification_match'))} | {_b(c.get('category_hit'))} | "
            f"{c.get('root_cause_recall','')} | {_b(c.get('responsible_file_cited'))} | "
            f"{_b(c.get('first_causal_error_identified'))} | {c.get('confidence','')} | "
            f"{c.get('unsupported_citation_count',0)} |"
        )
    # Detail on unsupported citations / forbidden claims.
    detail = []
    for c in report["cases"]:
        if c.get("unsupported_citations") or c.get("forbidden_claim_hits"):
            detail.append(f"- **{c['case_id']}**:")
            for u in c.get("unsupported_citations", []):
                detail.append(f"    - unsupported citation: {u}")
            for f in c.get("forbidden_claim_hits", []):
                detail.append(f"    - forbidden/demo-default claim leaked: '{f}'")
    if detail:
        lines += ["", "## Unsupported / fabricated claims", ""] + detail
    return "\n".join(lines)


def _b(v: Optional[bool]) -> str:
    if v is None:
        return "—"
    return "✅" if v else "❌"


if __name__ == "__main__":
    raise SystemExit(main())
