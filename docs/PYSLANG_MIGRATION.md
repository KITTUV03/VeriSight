# PyVerilog → pyslang Migration

Replacing VeriSight's SystemVerilog parsing with a real IEEE-1800 frontend
(pyslang / Slang) and threading structured, categorized diagnostics and
explicit degraded-failure handling through the AST analyzer, X-Tracer, and the
pre-commit validator.

---

## 1. Root cause of the original parsing problems

Two distinct problems, discovered during inspection:

1. **PyVerilog was never actually in the code.** It is not in `pyproject.toml`
   and is not imported by any `.py` file. It appears **only** as a capability
   *claim* in the presentation/journal/Q&A generators (Q16, Slides 8/9/16).
2. **The real parser was regex.** RTL/UVM analysis was done by hand-written
   regular expressions (`verisight/parsers/rtl_parser.py`,
   `uvm_parser.py`, `utils/sv_lexer.py`). This is exactly the "fall back to
   text/regex analysis and lose structural information" failure mode the task
   describes — except it was the *primary and only* path. Regex cannot reliably
   handle types, scopes, packages, generate blocks, parameterized classes, SVA,
   or UVM, so downstream X-propagation and classification worked from
   approximate structure.

The migration therefore means: **build a genuine SystemVerilog frontend and
route all consumers through it**, not swap one library for another.

---

## 2. Parser evaluation (Phase 2)

| Candidate | What it provides | Verdict for VeriSight |
|-----------|------------------|------------------------|
| **pyslang** | Python bindings for the **Slang** C++ frontend: full IEEE-1800 parse, **elaboration**, typed symbols, bit widths, hierarchy, structured diagnostics. Prebuilt `abi3` wheels (no toolchain). MIT. | **Selected.** The only candidate that gives *structurally meaningful* analysis (symbols/types/locations) the platform needs for X-tracing and dependency analysis. |
| slang (C++) | The same frontend as a CLI/library. | Redundant — pyslang already exposes it in-process. Used indirectly: the external `x-tracer` tool is built on it. |
| verible-verilog-syntax | Concrete syntax tree / formatting-oriented. | Syntax tree only; no elaboration/types. Insufficient for semantic structure. |
| tree-sitter-systemverilog | Incremental grammar parse for editors. | Tokenization/CST for highlighting; no semantic model. |

**Verified in-environment** (not assumed): `pip install pyslang` → **12.0.0** on
Python 3.14; parses `examples/rtl/alu.sv` with 0 diagnostics and yields the
`alu` top instance with typed `Port`/`Net`/`Variable`/`ProceduralBlock`
symbols; emits `file:line:col` diagnostics for malformed code; and for a
standalone UVM file reports *missing-dependency* diagnostics (unknown macro /
interface / class) distinctly from syntax errors.

**Capability boundaries (made explicit, not glossed over):**
- *Syntax parse* always works for valid SV.
- *Elaboration* (symbol/type resolution) needs the dependency closure. UVM
  classes do **not** fully elaborate without `uvm_pkg` + `uvm_macros.svh`; they
  still *parse*, so UVM structure is extracted from the **syntax tree** and the
  result is flagged `degraded`.
- Static source analysis ≠ simulation. See §5.

---

## 3. Affected components (Phase 1 inventory)

| Component | File | Role | Change |
|-----------|------|------|--------|
| RTL parser | `parsers/rtl_parser.py` | regex → knowledge | pyslang primary, regex = explicit fallback |
| UVM parser | `parsers/uvm_parser.py` | regex → knowledge | pyslang syntax-tree primary, regex = fallback |
| SV lexer | `utils/sv_lexer.py` | regex tokenizer | retained (used only by fallback) |
| Agent 1 | `agents/agent1_knowledge.py` | calls parsers | unchanged (same API) |
| Agent 3 X-Tracer | `agents/agent3_rtl_analyzer.py` | consumes `RTLKnowledge` | surfaces parser backend/degraded + static-vs-sim limitation |
| Agent 5 fix check | `agents/agent5_fix_generator.py` | "AST syntax pre-check" | pyslang syntax validation added to heuristics |
| Real X-trace | `tools/xtracer_runner.py` | external x-tracer CLI (uses pyslang) | unchanged (already correct) |
| Docs | `generate_*.py`, `presentation.html`, `README.md` | PyVerilog claims | corrected to pyslang |

---

## 4. New / modified files

**New**
- `verisight/parsers/sv_frontend.py` — centralized pyslang frontend:
  `compile_files()` / `compile_text()`, categorized diagnostics, include
  dirs/defines, single/multi compilation unit, explicit availability + degraded
  handling.
- `verisight/parsers/pyslang_rtl.py` — `RTLKnowledge` from the elaborated AST
  (ports+types+widths, params, always blocks with AST-accurate read/write sets
  and blocking/non-blocking lint, assignments, instantiations, FSMs, SVA
  assertions, clock domains).
- `verisight/parsers/pyslang_uvm.py` — `TBKnowledge` from the syntax tree
  (classes/interfaces/packages authoritatively; macro-driven config_db/factory/
  TLM reused from the legacy per-class extractors).
- `verisight/schemas/parser_schema.py` — `ParserDiagnostic` + `ParserStatus`.
- `verisight/tools/sv_validate.py` — pre-commit syntax validator CLI.
- `tests/test_sv_frontend.py` + `tests/fixtures/sv/*` — integration/regression
  tests and minimal SV fixtures (SVA, struct/enum, interface, malformed,
  missing-package, legacy Verilog).

**Modified** — `rtl_parser.py`, `uvm_parser.py` (pyslang primary + labelled
fallback), `rtl_schema.py` / `tb_schema.py` (`parser_status` field),
`rtl_analysis.py` (X-trace `parser_backend`/`parser_degraded`/`limitations`),
`agent3_rtl_analyzer.py`, `agent5_fix_generator.py`, docs/generators,
`pyproject.toml` (pyslang dependency), `README.md`.

---

## 5. Integration changes

**AST analyzer / X-Tracer (Agent 3).** Consumes the same `RTLKnowledge`
schema, now populated from the real AST, so the static X-origin scan is more
reliable (accurate `has_reset`, `signals_written`, `raw_code`). It now records
`parser_backend`, `parser_degraded`, and an explicit `limitations` note stating
that **static source analysis identifies *candidate* X origins but cannot
establish the runtime propagation path** — that requires the simulation-based
x-tracer (VCD + netlist). This separation is deliberate and documented.

**Pre-commit validator (Agent 5 + CLI).** The fix-generator's syntax pre-check
now runs pyslang (wrapping the snippet in a module/always context and failing
only on genuine syntax errors, ignoring the undeclared-signal/macro
missing-dependency noise expected in a fragment) on top of the existing
structural heuristics. The standalone `sv_validate` CLI validates whole files:
non-zero on genuine syntax errors, `UNVERIFIED` (not failed) when syntax is
masked by missing dependencies in syntax-only mode, and non-zero on tool crash.

---

## 6. Test results (actual)

- `tests/test_parsers.py` — **38 passed** (RTL path now via pyslang; UVM via
  pyslang; no regression).
- `tests/test_sv_frontend.py` — **24 passed** (new): diagnostics/categorization,
  RTL structure, packed struct/enum widths, FSM, SVA assertions, multi-module
  hierarchy, legacy Verilog, interfaces/modports, X-tracer integration,
  pre-commit exit codes, fix syntax check.
- Full suite — **169 passed, 2 failed**. Both failures pre-exist on the clean
  tree and are unrelated to parsing:
  - `test_tools.py::...yosys...` — `yosys` binary not installed (environmental).
  - `test_fix_generator.py::...test_html_has_fix_section...` — Agent 4 HTML
    reporter; not touched by this migration.

Pre-commit validator exit codes (verified): clean RTL = 0, legacy Verilog = 0,
malformed = 1, missing-package (syntax-only) = 0, missing-package (`--strict`) =
1, UVM standalone (syntax-only) = 0 (`UNVERIFIED`).

---

## 7. Before / after

| Example | Before (regex) | After (pyslang) |
|---------|----------------|------------------|
| `alu.sv` port `operand_a` | width from a width-regex, type guessed | real type `logic`, width `[7:0]` from the elaborated type |
| `alu.sv` X-origin | depended on identifier-diff heuristics | `has_reset`/`signals_written` from the AST; `alu.result` correctly flagged, `carry`/`zero` correctly spared |
| `types_pkg.sv` `in_bus` (`struct packed{8+8+1}`) | not representable | width `[16:0]` (17 bits) |
| UVM `examples/tb` | regex class discovery, include-expansion could double-count | authoritative class discovery, deduped; `degraded=True` flagged |
| malformed file | silently "parsed" to 0 modules | 3 categorized syntax diagnostics with `file:line:col` |
| `missing_pkg.sv` | indistinguishable | 2 `missing_dependency` diagnostics, 0 syntax errors |

---

## 8. Known limitations / configuration

- **UVM elaboration requires the UVM library.** Without `uvm_pkg` +
  `uvm_macros.svh` on the include path, UVM files parse but don't fully
  elaborate; results are flagged `degraded`, and macro-expanded factory/TLM
  details are extracted heuristically. Supply `-I <uvm>/src` + `-D` for full
  resolution.
- **Static ≠ simulation.** The X-Tracer static layer finds candidate X origins
  only. Runtime propagation needs the external `x-tracer` tool (VCD + netlist).
- **Fallback is degraded, by design.** If pyslang is ever unavailable, the regex
  parser runs and the result is flagged `degraded` — it is not a substitute.
- **Spurious syntax from missing macros.** An unexpanded `` `uvm_* `` macro can
  produce a downstream syntax diagnostic; the validator treats "syntax error in
  the presence of missing dependencies" as `UNVERIFIED`, not a hard failure.

---

## 9. Install / configure / run

```bash
# pyslang is a core dependency (prebuilt wheel, no toolchain needed)
pip install -e ".[dev]"
python -c "import pyslang; print(pyslang.__version__)"   # tested: 12.0.0

# Parse programmatically
python -c "from verisight.parsers.rtl_parser import parse_rtl; \
k=parse_rtl('examples/rtl/alu.sv'); print(k.top_module, k.parser_status.backend)"

# Pre-commit syntax validation
python -m verisight.tools.sv_validate examples/rtl/alu.sv
python -m verisight.tools.sv_validate -I rtl/inc -D SYNTH --strict rtl/*.sv

# Tests
python -m pytest tests/test_sv_frontend.py tests/test_parsers.py -q
```

Suggested `.pre-commit-config.yaml` hook:

```yaml
- repo: local
  hooks:
    - id: verisight-sv-syntax
      name: VeriSight SystemVerilog syntax check
      entry: python -m verisight.tools.sv_validate
      language: system
      files: '\.(sv|svh|v|vh)$'
```
