# VeriSight — AI-Powered RTL/UVM Debugging Framework

A production-grade autonomous multi-agent system for root-cause analysis of ASIC simulation failures. VeriSight reasons like a senior verification engineer, tracing from symptom → root cause with structured evidence chains.

## Architecture

```
Inputs (Spec, RTL, UVM TB, Sim Log, Coverage)
                    │
                    ▼
         ┌──────────────────┐
         │   Agent 1        │  Knowledge Extraction Engine
         │   Parse & Index  │  → knowledge.json
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
| Waveform/VCD | `.vcd` | Optional (enables real x-tracer analysis) |
| Gate-level Netlist | `.v` | Optional (else synthesized from RTL via yosys) |

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
| `analysis/*.json` | RTL analysis sub-module results |

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

## Project Structure

```
VeriSight/
├── verisight/              # Core Python package
│   ├── schemas/            # Pydantic data models
│   ├── parsers/            # Deterministic parsers
│   ├── agents/             # AI Agent implementations
│   ├── rag/                # ChromaDB RAG system
│   ├── orchestrator.py     # Pipeline orchestration
│   └── config.py           # Configuration
├── templates/              # Jinja2 report templates
├── examples/               # ALU example inputs
├── tests/                  # Unit & integration tests
└── main.py                 # CLI entry point
```

## License

MIT
