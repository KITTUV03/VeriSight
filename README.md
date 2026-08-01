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

# Run on the included ALU example
python main.py \
    --spec examples/specs/alu_spec.md \
    --rtl examples/rtl/ \
    --tb examples/tb/ \
    --log examples/logs/sim.log \
    --output output/ \
    --no-rag

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
| Waveform/VCD | `.vcd` | Future |

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
```

## Example: ALU Bug Detection

The included example demonstrates VeriSight detecting a missing reset bug in an ALU:

- **Bug**: `result` register is never reset in the sequential always block
- **Symptom**: Scoreboard mismatches with `xx` values early in simulation
- **Root Cause**: X propagation from uninitialized register
- **Classification**: RTL Bug (confidence: 85-99%)

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
