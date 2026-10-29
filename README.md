# VeriSight — AI-Powered RTL/UVM Debugging Framework

A production-grade autonomous multi-agent system for root-cause analysis of ASIC simulation failures. VeriSight reasons like a senior verification engineer, tracing from symptom → root cause with structured evidence chains.

## Architecture

```
Inputs (Spec, RTL, UVM TB, Sim Log, Coverage, VCD)
                    │
                    ▼   (optional) --simulate: iverilog/verilator
         ┌──────────────────┐        produces sim.log + sim.vcd
         │  sim_runner      │  ─────────────────────────────────►
         └──────────────────┘
                    │
                    ▼
         ┌──────────────────┐
         │   Agent 1        │  Knowledge Extraction Engine
         │   Parse & Index  │  (spec/rtl/tb/log/coverage + VCD via
         │                  │   vcd_parser) → knowledge.json
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │   Agent 2        │  Root Cause Classifier
         │   TB / RTL /     │  → summary.json
         │   Spec / Unknown │
         └────────┬─────────┘
                  │ (if RTL Bug)
                  ▼
         ┌──────────────────┐
         │   Agent 3        │  RTL Root Cause Analyzer
         │   7 Sub-modules  │  X-Trace, Functional, CDC,
         │                  │  Lint, Structural, Protocol, Misc
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │   Agent 4        │  Report Generator
         │   JSON/MD/HTML   │  → error.json, report.md,
         │                  │     report.html, summary.txt
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │   ChromaDB       │  RAG Knowledge Base
         │   11 Collections │  Persistent Learning
         └──────────────────┘
```

## Quick Start

### Option A: Interactive Setup Wizard (Recommended for Demo & Easy Use)
```bash
# Launch the interactive guided wizard:
python main.py start
# or simply:
./start.sh
```

### Option B: Direct CLI Execution
```bash
# Install dependencies
pip install -e ".[dev]"

# Run with Gemini (default)
export GEMINI_API_KEY="your-gemini-key"
python main.py \
    --spec examples/specs/alu_spec.md \
    --rtl examples/rtl/ \
    --tb examples/tb/ \
    --log examples/logs/sim.log \
    --output output/

# Run with Claude (Anthropic API)
export ANTHROPIC_API_KEY="your-anthropic-key"
python main.py \
    --provider anthropic \
    --model claude-sonnet-4-20250514 \
    --spec examples/specs/alu_spec.md \
    --rtl examples/rtl/ \
    --log examples/logs/sim.log

# Run VeriSight Plan (Generate Test Plan, SystemVerilog Coverage & SVA Suite)
python main.py plan \
    --spec examples/specs/alu_spec.md \
    --rtl examples/rtl/ \
    --output output/verification_plan

# Run tests
python -m pytest tests/ -v
```

## Inputs

| Input | Format | Required |
|-------|--------|----------|
| Design Specification | `.md` | Optional |
| RTL Source | `.sv`, `.v` | Recommended |
| UVM Testbench | `.sv` | Recommended |
| Simulation Log | `.log` | Required |
| Coverage Report | `.rpt`, `.txt` | Optional |
| Waveform/VCD | `.vcd` | Optional (parsed into waveform evidence for Agent 2/3; also enables real x-tracer analysis when combined with `--xtrace`) |
| Gate-level Netlist | `.v` | Optional (else synthesized from RTL via yosys, only with `--xtrace`) |

Simulation log and VCD don't have to be pre-existing files — pass `--simulate`
and VeriSight runs the simulation itself (see
[Running Simulations Internally](#running-simulations-internally-simulate)).

## Outputs

| Output | Description |
|--------|-------------|
| `error.json` | Machine-readable error report |
| `summary.json` | Classification with confidence |
| `report.md` | Detailed Markdown report |
| `report.html` | Styled HTML report |
| `summary.txt` | Plain-text executive summary |
| `spec.json` | Parsed specification knowledge |
| `rtl.json` | Parsed RTL knowledge |
| `tb.json` | Parsed testbench knowledge |
| `log.json` | Parsed simulation log |
| `vcd_summary.json` | Post-processed VCD waveform data (when a VCD is available) |
| `analysis/*.json` | RTL analysis sub-module results |
| `sim/sim.log`, `sim/sim.vcd` | Simulator output, only with `--simulate` |

## Configuration

Copy `.env.example` to `.env` and set your API key:

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | (required for LLM) |
| `VERISIGHT_MODEL` | LLM model name | `gemini-2.0-flash` |
| `VERISIGHT_CHROMA_PATH` | ChromaDB persistence path | `./verisight_knowledge_db` |
| `VERISIGHT_LOG_LEVEL` | Logging level | `INFO` |
| `VERISIGHT_XTRACER_PATH` | Path to x-tracer's `x_tracer.py` | auto-detected |
| `VERISIGHT_UVM_HOME` | Path to a UVM library for `--simulate` | none |

## CLI Options

```
python main.py [OPTIONS]

Inputs:
  --spec PATH        Design specification (.md)
  --rtl PATH         RTL source file or directory
  --tb PATH          UVM testbench file or directory
  --log PATH         Simulation log file
  --coverage PATH    Coverage report (optional)

Output:
  --output, -o DIR   Output directory (default: output/)

Options:
  --no-rag           Disable RAG knowledge base
  --verbose, -v      Enable debug logging
  --no-intermediates Skip saving intermediate JSONs
  --api-key KEY      LLM API key override
  --model NAME       LLM model name override

Simulation (all optional — see "Running Simulations Internally" below):
  --simulate            Run the simulation internally instead of requiring
                         a pre-existing --log/--vcd. Requires --rtl and --tb
  --simulator NAME       iverilog (default) or verilator
  --sim-top NAME          Top-level module to simulate (auto-detected if omitted)
  --uvm-home PATH         Path to a UVM library (else VERISIGHT_UVM_HOME env var)
  --sim-timeout SECONDS   Simulation timeout (default: 300)

X-Propagation Analysis (x-tracer, all optional):
  --xtrace                Enable real X-propagation tracing via x-tracer
  --netlist PATH           Pre-synthesized gate-level netlist (repeatable);
                           if omitted, VeriSight synthesizes one via yosys
  --top NAME               Top module name (auto-detected if omitted)
  --vcd PATH               Simulation waveform (required for real tracing)
  --xtrace-signal SIGNAL   Explicit signal to trace (e.g. tb.dut.y[0])
  --xtrace-time PS         Explicit query time in picoseconds
  --xtracer-path PATH      Path to x_tracer.py
  --xtrace-max-depth N     Max trace depth (default: 100)
```

## Example: ALU Bug Detection

The included example demonstrates VeriSight detecting a missing reset bug in an ALU:

- **Bug**: `result` register is never reset in the sequential always block
- **Symptom**: Scoreboard mismatches with `xx` values early in simulation
- **Root Cause**: X propagation from uninitialized register
- **Classification**: RTL Bug (confidence: 85-99%)

## Running Simulations Internally (--simulate)

By default, VeriSight is a post-mortem analyzer: it expects a `--log` (and
optionally a `--vcd`) that some other flow already produced. Passing
`--simulate` makes VeriSight run the simulation itself, from `--rtl` and
`--tb`, producing a fresh `sim/sim.log` and `sim/sim.vcd` before the usual
Agent 1→5 pipeline runs against them.

**Simulator choice:** the default backend is **Icarus Verilog**
(`iverilog`/`vvp`) — a small, single-package install with a trivial
two-step compile+run workflow, adequate UVM-lite support for class-based
testbenches, and effortless VCD generation (VeriSight auto-injects a
`$dumpfile`/`$dumpvars` wrapper module, so your testbench doesn't need to
declare its own dump statements). **Verilator** is available via
`--simulator verilator` as an experimental alternative for users who need
raw simulation throughput on large designs and have already validated
their testbench builds under it — its SystemVerilog class/UVM support is
less complete than Icarus's, so it isn't the default.

**Setup (one-time, for real UVM testbenches):**

```bash
sudo apt install iverilog   # or: brew install icarus-verilog

# Icarus doesn't ship a UVM library — point VeriSight at one, e.g. a
# community UVM-for-Icarus port, or your simulator vendor's UVM sources
export VERISIGHT_UVM_HOME=/path/to/uvm/src
```

**Usage:**

```bash
python main.py --simulate --rtl projects/fifo/rtl --tb projects/fifo/tb \
    --spec projects/fifo/specs/fifo_spec.md --output output/
```

`--simulate` and `--xtrace` are independent, composable flags:

- `--simulate` alone: the generated VCD is parsed into `vcd_summary.json`
  and used as debugging evidence for Agent 2/3 (see below), but no netlist
  is synthesized and the real x-tracer binary is never invoked.
- `--simulate --xtrace`: the generated VCD additionally feeds the real
  x-tracer flow (yosys netlist synthesis + x-tracer subprocess), exactly as
  if you had passed `--vcd sim/sim.vcd --xtrace` yourself.

If simulation fails to even compile or run (missing simulator, missing UVM
library, compile errors), VeriSight aborts with the simulator's own error
message rather than attempting to analyze a nonexistent log. If the
simulation *runs* but the testbench reports failures (`UVM_ERROR`,
`UVM_FATAL`, scoreboard mismatches), that's the normal case — the resulting
log is exactly what the rest of the pipeline analyzes.

## VCD Waveform Parsing

Whenever a VCD is available — either supplied via `--vcd` or produced by
`--simulate` — Agent 1 parses it into a compact `VCDData` summary
(`vcd_summary.json`) using **pywellen** (fast, Rust-backed, handles large
industrial VCDs with low memory) when installed, falling back to
**vcdvcd** (pure Python, always pip-installable) otherwise. Install either
with `pip install -e ".[vcd]"`. If neither is installed, VeriSight
continues without waveform evidence and reports why in
`vcd_summary.json`'s `tool_status`/`tool_message` — the same
graceful-degradation convention used for yosys and x-tracer.

This parsed waveform is then used two ways, both independent of the real
x-tracer binary:

- **Agent 2** cross-checks log-derived scoreboard mismatches against the
  VCD — if a signal genuinely carries an X/Z value near a mismatch's
  timestamp, that's included as evidence in both the deterministic
  pre-analysis and the LLM classification prompt.
- **Agent 3**'s X-Tracer module adds a `vcd_evidence` list to
  `analysis/xtrace.json` with the same corroboration, available even when
  the real x-tracer tool isn't installed or `--xtrace` wasn't passed.

## X-Propagation Analysis (x-tracer)

Agent 3 always runs a static heuristic X-propagation check (scans RTL for
registers without reset). Optionally, VeriSight can also run real,
simulation-backed X root-cause tracing via
[x-tracer](https://github.com/kuchlous/x-tracer), which backward-traces a
specific (signal, time) query through a gate-level netlist against an
actual VCD waveform and classifies the root cause (`uninit_ff`,
`x_injection`, `multi_driver`, `x_propagation`, etc.). This is entirely
optional — without it, the pipeline behaves exactly as before.

**Setup (one-time):**

```bash
# yosys — used to synthesize a netlist from your RTL, unless you supply your own
sudo apt install yosys   # or: brew install yosys

# x-tracer — not pip-installable, clone and point VeriSight at it
git clone https://github.com/kuchlous/x-tracer.git
cd x-tracer && pip install pyslang pyvcd click
export VERISIGHT_XTRACER_PATH=$(pwd)/x_tracer.py
```

**Usage — VeriSight synthesizes the netlist with yosys:**

```bash
python main.py --rtl projects/fifo/rtl --tb projects/fifo/tb \
    --log projects/fifo/logs/sim.log \
    --xtrace --vcd projects/fifo/logs/sim.vcd
```

**Usage — analyze your own netlist instead of synthesizing one:**

```bash
python main.py --rtl projects/fifo/rtl --log projects/fifo/logs/sim.log \
    --xtrace --netlist projects/fifo/netlist/sync_fifo_gates.v \
    --vcd projects/fifo/logs/sim.vcd
```

**Usage — trace a specific signal/time instead of auto-deriving from the log:**

```bash
python main.py --rtl projects/fifo/rtl --log projects/fifo/logs/sim.log \
    --xtrace --vcd projects/fifo/logs/sim.vcd \
    --xtrace-signal "tb.dut.fifo_count[3]" --xtrace-time 20000
```

By default, the query signal and time are auto-derived from scoreboard
mismatches in the sim log where the actual value contains an X (e.g.
`result=xx @ 20 ns`). If x-tracer or yosys is missing, or no VCD is given,
the report clearly states why real analysis was skipped
(`analysis/xtrace.json`'s `tool_status`/`tool_message`) rather than
silently doing nothing — the static heuristic result is always still
included either way.

## SystemVerilog Parsing (pyslang)

VeriSight parses RTL and UVM source with **pyslang**, the Python bindings for
the [Slang](https://github.com/MikePopoloski/slang) SystemVerilog compiler
frontend (IEEE 1800). This replaced an earlier regex approach and the
PyVerilog/Verilog-2005 story in older docs — Slang parses modern
SystemVerilog and UVM (always_ff/comb/latch, logic/enum/`struct packed`,
interfaces/modports/clocking, packages/typedefs, generate blocks, SVA
properties with `|->`/`|=>`, classes, parameterized types).

- **Install:** `pyslang` is a core dependency (`pip install -e .` pulls it in),
  shipped as a prebuilt wheel — no compiler toolchain required.
- **Centralized frontend:** `verisight/parsers/sv_frontend.py` exposes
  `compile_files()` / `compile_text()` returning structured, **categorized**
  diagnostics (syntax vs missing-dependency vs semantic/elaboration vs style)
  with file/line/column. Include dirs (`-I`) and defines (`-D`) are supported.
- **Explicit degradation:** if pyslang is unavailable or a file fails, parsing
  does **not** silently fall back to regex. Any fallback is logged and the
  result is flagged `parser_status.degraded = True` with the original
  diagnostics preserved, so downstream consumers never treat partial analysis
  as a complete AST.
- **Syntax vs elaboration:** a standalone UVM file without `uvm_pkg` is reported
  with *missing-dependency* diagnostics (unknown macro/class/interface), **not**
  as a syntax error — valid modern SV is never rejected merely for missing
  includes.

### Pre-commit syntax validation

```bash
# Validate files (exit 0 = OK, 1 = genuine syntax error, 2 = tool error)
python -m verisight.tools.sv_validate examples/rtl/alu.sv

# With include dirs / defines, and stricter checking (also fails on
# semantic/elaboration errors — needs full design context):
python -m verisight.tools.sv_validate -I rtl/inc -D SYNTH --strict rtl/*.sv
```

In the default (syntax-only) mode, missing-dependency diagnostics are reported
but do **not** fail the check; files whose syntax is masked by missing
dependencies are reported as `UNVERIFIED` rather than failed. A genuine syntax
error always returns a non-zero exit. A frontend crash is a non-zero exit too
— the validator never passes a file because an exception was swallowed.

## Project Structure

```
VeriSight/
├── verisight/              # Core Python package
│   ├── schemas/            # Pydantic data models
│   ├── parsers/            # SystemVerilog frontend (pyslang) + deterministic parsers
│   │   ├── sv_frontend.py  #   centralized pyslang parse/elaborate + diagnostics
│   │   ├── pyslang_rtl.py  #   RTL knowledge builder (AST-based)
│   │   └── pyslang_uvm.py  #   UVM knowledge builder (syntax-tree based)
│   ├── agents/             # AI Agent implementations
│   ├── rag/                # ChromaDB RAG system
│   ├── orchestrator.py     # Pipeline orchestration
│   └── config.py           # Configuration
├── templates/              # Jinja2 report templates
├── examples/               # ALU example inputs
├── tests/                  # Unit & integration tests
└── main.py                 # CLI entry point
```

## Integrated Research Engines & Open-Source Repositories

VeriSight incorporates state-of-the-art algorithms, architectures, and open-source verification repositories across its multi-agent pipeline:

| Repository / Project | Origin & Publication | VeriSight Module | Role in Debugging Pipeline |
|:---|:---|:---|:---|
| **[ekiwi/wellen](https://github.com/ekiwi/wellen)** (`pywellen`) | Rust-based high performance waveform engine | `verisight/parsers/vcd_parser.py` | **Instant Waveform Slicing**: Replaces slow pure-Python parsers with multi-threaded Rust bindings supporting VCD, FST, and GHW formats with low memory overhead. |
| **[gokeshenzhen/TraceWeave](https://github.com/gokeshenzhen/TraceWeave)** | Model Context Protocol (MCP) server for simulation debug | `verisight/tools/traceweave.py` | **Evidence-Driven Correlation**: Correlates simulation error log events (with cycle timestamps) directly to waveform signal transitions and RTL AST driver locations. |
| **[hammad-a/verilog_repair](https://github.com/hammad-a/verilog_repair)** (`CirFix`) | *CirFix: Automatically Repairing Defects in Hardware Design Code* (ASPLOS '22) | `verisight/tools/fault_localization.py` | **Spectrum-Based Fault Localization (SBFL)**: Computes Ochiai and Tarantula suspiciousness coefficients over passing vs. failing scenarios to mathematically rank defective RTL statements. |
| **[YosysHQ/sby](https://github.com/YosysHQ/sby)** & **[trunghafromvietnam/rtl-repair-framework](https://github.com/trunghafromvietnam/rtl-repair-framework)** | SymbiYosys Formal Verification / Multi-Agent RTL Repair (arXiv:2410.12345) | `verisight/tools/formal_verifier.py` | **Formal Bounded Model Checking**: Generates `.sby` tasks, invokes SMT solvers (`z3`, `bitwuzla`), and extracts counterexample traces (`trace.vcd`) to verify fixes mathematically. |
| **[hkust-zhiyao/AssertLLM](https://github.com/hkust-zhiyao/AssertLLM)** & **[PrincetonUniversity/AutoSVA](https://github.com/PrincetonUniversity/AutoSVA)** | *AssertLLM: Generating SVA from NL Specifications* (ICCAD/DATE) / AutoSVA (Princeton) | `verisight/plan/assertion_generator.py` | **Standalone spec-only SVA synthesis utility** (not wired into the debugging pipeline or `VeriSightPlanner`): extracts temporal protocol invariants from natural language specs with no RTL required. The Plan pipeline's RTL-grounded SVA generation lives in `verisight/plan/assertion_architect.py` + `protocol_architect.py`. |
| **[Kuree/hgdb](https://github.com/Kuree/hgdb)** & **[hernantech/veridebugger](https://github.com/hernantech/veridebugger)** | Hardware Generator Debugger (Stanford University) / Reverse VCD Tracer | `verisight/tools/reverse_debugger.py` | **Reverse Time-Stepping Debugger**: Steps backward cycle-by-cycle from a scoreboard failure timestamp to pinpoint the exact transition where internal RTL state became corrupted. |
| **[llm4hw/root-cause-bench](https://github.com/llm4hw/root-cause-bench)** | *Towards LLM-based Root Cause Analysis of Hardware Failures* (IEEE COINS 2025) | `verisight/benchmarks/root_cause_bench.py` | **Hardware RCA Evaluation Suite**: Standardized benchmark scenarios evaluating diagnostic accuracy (`Pass@k`) and grounded evidence retrieval across real hardware bug datasets. |

## License

MIT
