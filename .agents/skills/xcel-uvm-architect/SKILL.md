---
name: xcel-uvm-architect
description: Autonomous generation of complete, cycle-accurate, production-grade UVM (Universal Verification Methodology) testbench suites from RTL designs and specifications. Generates interface, sequence items with protocol constraints, driver, monitor, agent, scoreboard, behavioral reference model, coverage collector subscriber, SVA assertions, environment, tests, and top module.
---

# XcelUVM Architect Skill

Autonomous UVM 1.2 testbench environment generator inspired by **XcelUVM** (`Abdel-Hay21/XcelUVM`).

This skill equips the agent to transform any hardware design (RTL AST or specification) into an enterprise-ready, cycle-accurate, standards-compliant Universal Verification Methodology (UVM) verification environment with zero hallucinated signals.

---

## Architecture Overview

XcelUVM generates every layer of an industry-standard UVM testbench directory:

```
<design>_uvm/
├── verif/
│   ├── <design>_if.sv               # SystemVerilog Interface (clocking blocks & modports)
│   ├── <design>_seq_item.sv         # Sequence Item (rand stimulus, fields & constraints)
│   ├── <design>_sequencer.sv        # UVM Sequencer
│   ├── <design>_driver.sv           # Cycle-accurate pin driver
│   ├── <design>_monitor.sv          # Cycle-accurate passive monitor with analysis port
│   ├── <design>_agent.sv            # Configurable active/passive agent
│   ├── <design>_reference_model.sv  # Cycle-exact golden behavioral reference model
│   ├── <design>_scoreboard.sv       # Scoreboard with automated matching and statistics
│   ├── <design>_coverage.sv         # Functional Coverage Collector (UVM Subscriber)
│   ├── <design>_sequence.sv         # Base, reset, random, and corner-case stress sequences
│   ├── <design>_env.sv              # Top-level UVM Environment
│   ├── <design>_test.sv             # UVM Test Suite (Base, Random, & Stress tests)
│   └── <design>_pkg.sv              # Package importing uvm_pkg and includes
├── top/
│   └── <design>_tb_top.sv           # Top-level testbench (DUT + Interface + run_test)
├── run.do                           # QuestaSim / ModelSim / VCS / EDA Playground Script
└── Makefile                         # Multi-simulator Makefile
```

---

## 5-Section Prompt Architecture (Anti-Hallucination)

When prompting LLMs for SystemVerilog / UVM code completion, the 5-section prompt structure is enforced:

1. **Section 0: Tool Architecture** — Mandatory cycle-by-cycle facts, clock edges, reset active levels, and timing semantics.
2. **Section 1: Style & Format Reference** — UVM coding conventions (`_item`, `_drv`, `_mon`, `_sb`, `_cov`), macro usages (`uvm_component_utils`, `uvm_field_int`).
3. **Section 2: Project Context** — Exact parsed RTL port list with bit widths and directions from pyslang AST. No invented signal names.
4. **Section 3: Target Skeleton** — The exact component file skeleton with fill-in blocks.
5. **Section 4: Task-Specific Critical Rules**:
   - Every input port must have a corresponding `rand` field in `seq_item`.
   - Output signals must never be driven by the driver.
   - Monitors must only sample on clocking block edges (`@(vif.cb_mon)`).
   - Drivers must drive outputs strictly at `#0` or via `vif.cb_drv`.
   - Scoreboards must raise `uvm_error` upon mismatches and print verification report in `report_phase`.

---

## Python API Usage

```python
from verisight.uvm.uvm_architect import UVMArchitect

architect = UVMArchitect(output_dir="output/uvm_environment")
result = architect.generate(
    rtl_path="projects/apb/rtl/apb_slave.sv",
    spec_path="projects/apb/specs/apb_spec.md",
    design_name="apb_slave",
)

print(f"Generated {len(result.files_generated)} UVM verification files in {result.output_dir}")
for f in result.files_generated:
    print(f"  • {f}")
```

---

## Interactive CLI Execution

Launch the wizard:
```bash
./start
```
Select option `[7] 🏗️  XcelUVM Testbench Architect` or generate directly via python:
```bash
.venv/bin/python3 -c "
from verisight.uvm.uvm_architect import UVMArchitect
res = UVMArchitect().generate(rtl_path='projects/apb/rtl/apb_slave.sv')
print('UVM generation complete:', res.output_dir)
"
```

---

## EDA Playground & Cloud Simulation Integration

Every generated UVM testbench includes:
- `run.do`: Native QuestaSim / ModelSim / VCS / Aldec Riviera simulation command script.
- All files include `` `ifndef `` guards and self-contained package includes for 1-click cloud copy-paste into [EDA Playground](https://www.edaplayground.com).
