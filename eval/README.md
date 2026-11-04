# VeriSight Workflow-1 Debugging Evaluation Harness

Reproducible before/after measurement of the **Verification Debugging** workflow's
root-cause accuracy. The harness runs the *real* `VeriSightPipeline` on a set of
ground-truth cases and scores the output with automatically-checkable metrics.
It never modifies `verisight/`, and it isolates ChromaDB per run so RAG state
never leaks between cases or between baseline/after runs.

## Run it

```bash
# From the repo root, using the project venv:

# Deterministic path only (no API spend). This is what runs in an air-gapped
# environment and is the path measured in this repo's baseline/after numbers.
python -m eval.run_eval --no-llm --rag off --tag baseline --out output/eval/baseline

# With the LLM (requires network + a valid key). Isolated RAG per case.
python -m eval.run_eval --rag isolated --tag after-llm --out output/eval/after_llm

# Consistency across repeats (adds label_consistency per case):
python -m eval.run_eval --no-llm --repeats 3 --tag consistency
```

Outputs: `<out>/eval_report.json`, `<out>/eval_report.md`, and each case's raw
pipeline artifacts under `<out>/cases/<id>/`.

## Dataset (`eval/cases/*.json`)

| id | source | ground truth | why it's here |
|---|---|---|---|
| `alu_xprop` | examples/ | RTL Bug · X-prop · `alu.sv` result never reset | the canonical X-propagation case |
| `ram_offbyone` | projects/ram | RTL Bug · `ram_rtl.sv:29` reads `mem[addr+1]` | functional off-by-one |
| `apb_multi_defect` | projects/apb | RTL Bug · `apb_slave.sv:92` truncation + `:83` PSLVERR | protocol + data, two defects |
| `fifo_tb_reset` | projects/fifo | **TB Bug** · out-of-band 2nd reset in `fifo_tb.sv:57-61` | the RTL is spec-correct; tempting wrong answer is "RTL reset bug" |
| `compile_error_falsepass` | synthetic | must DETECT a compile failure | a compile log has no `UVM_ERROR` → old parser reported PASS |
| `insufficient_evidence` | synthetic | must ABSTAIN (Unknown + missing artifacts) | one mismatch, no RTL/TB/spec → cannot decide RTL vs TB |

Ground truth for the real projects was cross-verified from RTL + spec +
scoreboard (not from the tool's own output). Each record documents its
confidence and any ambiguity. **No logs or diagnoses were fabricated.**

## Metrics (`eval/metrics.py`)

All metrics are deterministic given a pipeline output:

- **classification_top1_accuracy** — predicted label == ground-truth label.
- **category_accuracy** — predicted category matches an expected keyword.
- **root_cause_keyword_recall_mean** — fraction of expected root-cause keywords present.
- **responsible_file_citation_accuracy** — the real responsible file is cited.
- **first_causal_error_accuracy** — the earliest causal error (not a downstream symptom) is surfaced.
- **failure_detection_accuracy** — a compile/elab failure is not mis-reported as a clean pass.
- **insufficient_evidence_abstention_accuracy** — correctly returns Unknown + missing artifacts.
- **unsupported_citation_total** — cited `file:line` references that do not exist in the inputs (hallucination proxy). A citation that quotes the log verbatim is *not* counted.
- **mean_confidence_positive** — mean confidence on positive cases.

## Scope / honesty notes

- In an air-gapped environment (no outbound network), every LLM call fails and
  the pipeline falls back to its deterministic path; the numbers here measure
  that path. LLM-path improvements (prompt grounding, citation verification) are
  implemented and unit-tested structurally but their live diagnostic accuracy
  must be measured where the API is reachable.
- The automatable unsupported-citation metric catches invented file paths and
  out-of-range line numbers. It does not catch *semantic* hallucination (a real
  line cited for the wrong reason); that still needs human review.
