# Workflow 1 (Verification Debugging) — Reliability Improvements

Date: 2026-10-22. Scope: make VeriSight's debugging workflow identify root causes
from technical evidence, explain its reasoning, and **acknowledge uncertainty
instead of hallucinating**.

---

## 1. Existing architecture (as found)

A fixed 5-stage pipeline (`verisight/orchestrator.py`), not an autonomous loop:

| Stage | File | Nature |
|---|---|---|
| Agent 1 Knowledge Extraction | `agents/agent1_knowledge.py` + `parsers/*` | deterministic (regex/AST); no LLM |
| Agent 2 Root-Cause Classifier | `agents/agent2_classifier.py` | **LLM** + deterministic pre-analysis/fallback |
| Agent 3 RTL Analyzer (7 sub-modules) | `agents/agent3_rtl_analyzer.py` | **deterministic**; its system prompt was dead code |
| Agent 5 Fix Generator | `agents/agent5_fix_generator.py` | LLM + static validation |
| Agent 4 Reporter | `agents/agent4_reporter.py` | pure templater; no LLM |

RAG: ChromaDB, `all-MiniLM-L6-v2`, 11 collections declared / 3 written. Agent 4
writes every run's conclusion back to ChromaDB; Agent 1 retrieves it next run.

## 2. Confirmed causes of inaccurate debugging (evidence-based)

| # | Confirmed defect | Evidence | Impact |
|---|---|---|---|
| A | Classifier saw only `errors[:10]`, `mismatches[:10]`, `reqs[:15]` | `agent2_classifier.py:239,244,251` | real root cause can be truncated out of the prompt |
| B | No first-causal-error selection; "primary" = `errors[0]`; Agent 3 uses a fixed severity ladder | `log_parser` append order; `agent2:375`; `agent3:629-666` | symptom reported as root cause |
| C | UVM-only regexes; compile/elab/native-tool errors dropped → 0 errors → **false PASS** | `log_parser.py:379-382` | whole failure classes mis-handled |
| D | Confidence = raw LLM integer (or hardcoded 85/30/100), not evidence-derived | `agent2`; `classification.py:55` | confidence doesn't track correctness |
| E | LLM citations never verified (only JSON shape validated) | `base_agent._parse_json_response` | fabricated `file:line` passes as fact |
| F | Unverified conclusions written to RAG every run, re-injected as "SIMILAR PAST FAILURES" with no caveat/threshold; `similarity=1-distance` assumes cosine but collections used L2 | `agent4:1882`, `agent2:297`, `retriever.py:65` | self-reinforcing hallucination; irrelevant neighbours used as evidence |
| I | Time unit hardcoded to ` ns`; `[ID]` discarded; multi-line msgs lost | `log_parser.py:160…` | corrupted ordering, lost dedup key |

Cross-cutting: **no evaluation framework, dataset, or ground-truth labels existed**;
"correctness" tests only asserted the ALU deterministic fallback.

## 3. Evaluation dataset & harness (new)

- **Harness:** `eval/run_eval.py` + `eval/metrics.py` — runs the real pipeline,
  isolates ChromaDB per run, scores against ground truth. See `eval/README.md`.
- **Dataset:** `eval/cases/*.json` — 6 cases (ALU, RAM, APB, FIFO + 2 synthetic
  negatives). Ground truth cross-verified from RTL/spec/scoreboard; FIFO is a
  deliberate **TB-bug** trap (spec-correct RTL, out-of-band reset in
  `fifo_tb.sv:57-61`). No logs or diagnoses were fabricated.

## 4. Files changed and why

| File | Change |
|---|---|
| `verisight/analysis/failure_analysis.py` *(new)* | unit-aware time; simulator-native compile/elab detection (Verilator/VCS/Questa/Xcelium/Icarus); `select_primary_event` (earliest causal) + cascade |
| `verisight/schemas/log_schema.py` | `LogEntry.message_id/phase`; `ToolError`, `FailureEvent`; `SimulationSummary.failure_stage`; `LogKnowledge.tool_errors/primary_event/cascade_events` |
| `verisight/parsers/log_parser.py` | wires the above; preserves real time unit; captures `[ID]`; **closes the false-PASS hole** (compile/elab ⇒ FAIL) |
| `verisight/agents/agent2_classifier.py` | evidence-based `_deterministic_classify` across categories (compile/elab, X-prop, protocol/SVA, data-mismatch → honest Unknown); **calibrated confidence** (`_calibrate_confidence`); LLM prompt rewritten (primary-event anchor, failure stage, de-truncation, verbatim-grounding, structured observed/inferred/alternatives/missing); post-hoc citation verification (`_verify_and_calibrate`) |
| `verisight/utils/evidence_verifier.py` *(new)* | verifies cited `file:line` against the inputs; flags invented references |
| `verisight/rag/knowledge_base.py` | cosine metric on collections; `verified` tag on stored sessions |
| `verisight/rag/retriever.py` | relevance threshold (drops low-similarity neighbours); surfaces similarity + verified flag |
| `verisight/agents/agent4_reporter.py` | **gated RAG writeback** — only confident, non-Unknown conclusions, stored as `verified=False` |
| `verisight/config.py` | `rag_min_similarity`, `rag_writeback_min_confidence` |
| `tests/test_failure_analysis.py`, `tests/test_evidence_grounding.py` *(new)* | 17 tests for the new logic |
| `tests/test_llm_adapter.py` | fixed a stale default-model assertion |

## 5. How the improvements address root causes

- **A** → evidence-prioritized `_select_error_lines` (keeps primary + X/assert lines, reports honest totals).
- **B** → `select_primary_event` anchors on the earliest-in-time failure; cascade is labelled *candidate* (not proven causal). Prompt tells the model to reason from it.
- **C** → `detect_tool_errors` + `failure_stage`; a compile/elab log is now FAIL and classified as a Compilation/Elaboration Error.
- **D** → confidence is a documented additive function of grounded evidence factors, clamped to 0.95; abstentions get a fixed moderate value.
- **E** → verbatim-only prompt rule **plus** automated citation verification that penalizes confidence and records the problem.
- **F** → cosine metric + similarity threshold + "reference only, NOT proof" framing + gated, `verified=False` writeback.
- **I** → real time unit preserved; `[ID]` captured.

## 6. Baseline vs improved (measured here = deterministic path)

> In this environment there is **no outbound network**, so the LLM path is
> unreachable and the pipeline runs on its deterministic path. These numbers
> measure that path on all 6 cases (`--no-llm --rag off`). Commands:
> `python -m eval.run_eval --no-llm --rag off --tag baseline|after`.

| metric | baseline (original) | improved |
|---|---|---|
| classification_top1_accuracy | **0.25** | **0.50** |
| category_accuracy | 0.25 | **0.75** |
| root_cause_keyword_recall_mean | 0.25 | **0.75** |
| responsible_file_citation_accuracy | 0.00 | **1.00** |
| first_causal_error_accuracy | 0.00 | **1.00** |
| failure_detection_accuracy (compile) | 0.00 | **1.00** |
| insufficient_evidence_abstention_accuracy | 1.00 | 1.00 |
| unsupported_citation_total | 0 | 0 |
| mean_confidence (positive) | 43.8 (85/30/100) | 66.2 (calibrated) |

Per-case after: ALU ✅RTL/X-prop, APB ✅RTL/Protocol, compile ✅detected,
insufficient ✅abstain; **RAM and FIFO return honest `Unknown`** with specific
missing artifacts + alternative hypotheses rather than a confident wrong guess —
these two are deterministically undecidable and are where the (currently
unreachable) LLM path is expected to add value.

## 7. Test results

- New: `tests/test_failure_analysis.py` (10) + `tests/test_evidence_grounding.py` (7) — **all pass**.
- Full suite (excluding `test_server.py` [needs fastapi] and `test_sim_runner.py` [needs iverilog]): **135 passed, 2 failed**.
  - The 2 failures are **pre-existing/environmental**: `test_tools.py` yosys test (no `yosys` binary) and `test_fix_generator.py` HTML test (a template CSS-class name mismatch that failed before any change here). Neither relates to debugging accuracy.

## 8. Remaining limitations / known failure scenarios

1. **LLM path not measured here** (no network). Prompt-grounding, citation
   verification, and structured-output changes are implemented and unit-tested
   structurally; live diagnostic accuracy must be measured where the API is reachable.
2. **RAM/FIFO** deterministically resolve to `Unknown` — correct abstention, but
   the definitive label needs the LLM (semantic RTL-vs-reference-model reasoning).
3. **Semantic hallucination** (a real line cited for a wrong reason) is not caught
   by the citation verifier — needs human review.
4. **Agent 3 / Agent 5** were not changed in this pass (Agent 3 remains
   deterministic; Agent 5 fix validation is still static-only).
5. The default model name `gemini-3.8-flash` is fictional; set a real model via
   `VERISIGHT_MODEL`/`--model` for the LLM path.

## 9. How to run the improved workflow

```bash
# Debugging run (LLM path; needs network + key):
python main.py --provider anthropic --model claude-sonnet-4-20250514 \
  --spec projects/apb/specs/apb_spec.md --rtl projects/apb/rtl/ \
  --tb projects/apb/tb/ --log projects/apb/logs/sim.log --output output/apb

# Evaluate (deterministic, no API):
python -m eval.run_eval --no-llm --rag off --tag check --out output/eval/check
```

## 10. Prioritized roadmap to production

1. **Measure the LLM path** where the API is reachable; validate that calibrated
   confidence correlates with correctness; tune factor weights on the eval set.
2. **Grow the dataset** (UVM config_db/factory/phasing, CDC, race, X-init, AXI/AHB,
   reference-model bugs) with ground truth; add top-k and consistency reporting.
3. **Extend Agent 3** to feed Agent 2 concrete static defects (off-by-one, width,
   FSM) so cases like RAM resolve deterministically.
4. **Close Agent 5's validation loop** (compile/sim the proposed fix) and stop
   rendering "Simulation Regression PASS" when validation is `NOT_AVAILABLE`.
5. **Human-in-the-loop RAG**: a review step that promotes `verified=False` →
   `verified=True`; prefer verified entries in retrieval.
6. **Observability**: emit per-run evidence/citation-verification metrics; alert on
   unsupported-citation or low-confidence-but-confident-wording anomalies.
