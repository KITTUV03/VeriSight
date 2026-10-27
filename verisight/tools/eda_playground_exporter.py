"""
EDA Playground Exporter for VeriSight.

Packages RTL designs, testbenches, and UVM suites into clean, single-click
bundles formatted specifically for https://www.edaplayground.com, enabling
free cloud execution with commercial EDA simulators (Siemens Questa,
Synopsys VCS, Cadence Xcelium, Aldec Riviera-PRO).
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from verisight.tools.sim_runner import (
    RTL_EXTENSIONS,
    TB_EXTENSIONS,
    discover_files,
    is_uvm_testbench,
    _guess_top_module,
    _collect_sources,
)
from verisight.utils.anonymizer import RTLAnonymizer
from verisight.utils.logger import get_logger

logger = get_logger("edaplayground_exporter")


SIMULATOR_PRESETS = {
    "questa": {
        "name": "Siemens Questa 2023.2",
        "edap_name": "Questa 2023.2",
        "compile_options": "-timescale 1ns/1ps +acc=rn -sv",
        "run_options": "+UVM_VERBOSITY=UVM_HIGH",
        "uvm_options": "UVM 1.2",
        "description": "Siemens Questa SIM — Full SystemVerilog IEEE-1800 & UVM 1.2 execution.",
    },
    "vcs": {
        "name": "Synopsys VCS 2021.09",
        "edap_name": "Synopsys VCS 2021.09",
        "compile_options": "-sverilog -debug_access+all -kdb -timescale=1ns/1ps",
        "run_options": "+UVM_VERBOSITY=UVM_HIGH",
        "uvm_options": "UVM 1.2",
        "description": "Synopsys VCS — High-performance commercial SystemVerilog and UVM simulator.",
    },
    "riviera": {
        "name": "Aldec Riviera-PRO 2023.04",
        "edap_name": "Aldec Riviera-PRO 2023.04",
        "compile_options": "-dbg",
        "run_options": "+access+r",
        "uvm_options": "UVM 1.2",
        "description": "Aldec Riviera-PRO — Popular commercial SystemVerilog / UVM verification platform.",
    },
    "xcelium": {
        "name": "Cadence Xcelium 20.09",
        "edap_name": "Cadence Xcelium 20.09",
        "compile_options": "-access +rwc",
        "run_options": "+UVM_VERBOSITY=UVM_HIGH",
        "uvm_options": "UVM 1.2",
        "description": "Cadence Xcelium — Enterprise multi-core SystemVerilog and UVM simulator.",
    },
    "verilator": {
        "name": "Verilator 5.032",
        "edap_name": "Verilator 5.032",
        "compile_options": "--binary --timing -Wno-fatal --trace",
        "run_options": "",
        "uvm_options": "UVM 1.2 (via DPI-less wrapper)",
        "description": "Open-source high-speed SystemVerilog C++ simulation engine.",
    },
    "iverilog": {
        "name": "Icarus Verilog 0.10.0",
        "edap_name": "Icarus Verilog 0.10.0",
        "compile_options": "-g2012",
        "run_options": "",
        "uvm_options": "None (pure Verilog / SystemVerilog RTL)",
        "description": "Classic open-source Verilog simulator.",
    },
}


def _ensure_dumpvars(tb_code: str, top_module: str = "") -> str:
    """
    Ensure the testbench code writes a VCD file ('dump.vcd') so that
    EDA Playground's EPWave waveform viewer can render digital traces.
    """
    if "$dumpfile" in tb_code or "$dumpvars" in tb_code:
        return tb_code

    dump_block = (
        "\n\n// [VeriSight EDA Playground Exporter] Automatic VCD trace generator for EPWave\n"
        "module _verisight_epwave_dump;\n"
        "    initial begin\n"
        '        $dumpfile("dump.vcd");\n'
        '        $dumpvars(0);\n'
        "    end\n"
        "endmodule\n"
    )
    return tb_code + dump_block


def export_to_edaplayground(
    rtl_path: str,
    tb_path: str,
    output_dir: str = "output/edaplayground",
    spec_path: Optional[str] = None,
    preferred_simulator: str = "questa",
    anonymize_rtl: bool = False,
    auto_dumpvars: bool = True,
) -> Dict[str, Any]:
    """
    Export RTL and TB sources into an EDA Playground bundle.

    Creates:
    - design.sv: Merged RTL source files
    - testbench.sv: Merged testbench sources (with EPWave dump hook)
    - edaplayground_config.json: Complete simulator flags and settings
    - README.md: Usage and loopback ingestion instructions
    - launch_edaplayground.html: Rich interactive web dashboard with 1-click clipboard copy

    Returns metadata dictionary with paths and statistics.
    """
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sources, all_files = _collect_sources(rtl_path, tb_path)
    rtl_files = discover_files(Path(rtl_path), RTL_EXTENSIONS) if rtl_path else []
    tb_files = discover_files(Path(tb_path), TB_EXTENSIONS) if tb_path else []

    top_module = _guess_top_module(all_files) or "top_tb"
    is_uvm = is_uvm_testbench(tb_path)

    # 1. Assemble design.sv (RTL)
    design_parts = [
        "// ============================================================================",
        "// EDA Playground: design.sv",
        f"// Exported by VeriSight for Cloud Simulation ({', '.join(SIMULATOR_PRESETS.keys())})",
        f"// Top Module: {top_module} | UVM Enabled: {is_uvm}",
        "// ============================================================================\n",
    ]

    for f in rtl_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            design_parts.append(f"// --- Begin File: {f.name} ---")
            design_parts.append(content)
            design_parts.append(f"// --- End File: {f.name} ---\n")
        except OSError as e:
            logger.warning(f"Could not read RTL source {f}: {e}")

    design_content = "\n".join(design_parts)

    # 2. Assemble testbench.sv (TB)
    tb_parts = [
        "// ============================================================================",
        "// EDA Playground: testbench.sv",
        f"// Exported by VeriSight for Cloud Simulation ({', '.join(SIMULATOR_PRESETS.keys())})",
        f"// Top Module: {top_module} | UVM Enabled: {is_uvm}",
        "// ============================================================================\n",
    ]

    for f in tb_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            tb_parts.append(f"// --- Begin File: {f.name} ---")
            tb_parts.append(content)
            tb_parts.append(f"// --- End File: {f.name} ---\n")
        except OSError as e:
            logger.warning(f"Could not read TB source {f}: {e}")

    tb_content = "\n".join(tb_parts)

    if auto_dumpvars:
        tb_content = _ensure_dumpvars(tb_content, top_module)

    # 3. Anonymization if requested
    anon_count = 0
    anonymizer = None
    if anonymize_rtl:
        anonymizer = RTLAnonymizer()
        design_content, _ = anonymizer.anonymize_rtl(design_content)
        tb_content, _ = anonymizer.anonymize_rtl(tb_content)
        anon_count = len(anonymizer.orig_to_anon)
        logger.info(f"Anonymized {anon_count} proprietary RTL identifiers for EDA Playground export.")

    # 4. Write source files
    design_file = out_dir / "design.sv"
    design_file.write_text(design_content, encoding="utf-8")

    tb_file = out_dir / "testbench.sv"
    tb_file.write_text(tb_content, encoding="utf-8")

    # 5. Write config JSON
    sim_preset = SIMULATOR_PRESETS.get(preferred_simulator.lower(), SIMULATOR_PRESETS["questa"])
    config_data = {
        "export_timestamp": "2026-10-27",
        "top_module": top_module,
        "is_uvm": is_uvm,
        "anonymized": anonymize_rtl,
        "scrubbed_identifiers_count": anon_count,
        "recommended_simulator": preferred_simulator,
        "simulators": SIMULATOR_PRESETS,
        "files": {
            "design": str(design_file.name),
            "testbench": str(tb_file.name),
        },
        "edaplayground_url": "https://www.edaplayground.com",
        "instructions": {
            "step_1": "Open https://www.edaplayground.com in your browser.",
            "step_2": "Paste design.sv into the left pane ('design.sv').",
            "step_3": "Paste testbench.sv into the right pane ('testbench.sv').",
            "step_4": f"Select Tools & Simulators: '{sim_preset['edap_name']}'.",
            "step_5": f"Set Compile Options: '{sim_preset['compile_options']}' and Run Options: '{sim_preset['run_options']}'.",
            "step_6": "Check 'Open EPWave after run' to inspect waveforms.",
            "step_7": "Click 'Run' to execute in the cloud with Questa / VCS.",
            "step_8": "Download 'sim.log' and 'dump.vcd' and import into VeriSight for AI Root-Cause Analysis.",
        },
    }
    config_file = out_dir / "edaplayground_config.json"
    config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    # 6. Write README.md
    readme_file = out_dir / "README.md"
    readme_text = f"""# VeriSight — EDA Playground Cloud Execution Bundle

This bundle prepares your design for instant, free simulation on [EDA Playground](https://www.edaplayground.com) using commercial simulators (**Siemens Questa**, **Synopsys VCS**, **Aldec Riviera-PRO**, or **Cadence Xcelium**).

---

## 📁 Bundle Files

| File | Purpose |
|------|---------|
| [`design.sv`](file://{design_file}) | Bundled RTL logic ({len(rtl_files)} source files) |
| [`testbench.sv`](file://{tb_file}) | Bundled Testbench + EPWave `$dumpvars` hook |
| [`launch_edaplayground.html`](file://{out_dir / 'launch_edaplayground.html'}) | **Interactive 1-Click Launch Dashboard** (copy code & open site) |
| [`edaplayground_config.json`](file://{config_file}) | Simulator settings & compiler flags |

---

## 🚀 Quick Execution (3 Minutes)

1. Open **[https://www.edaplayground.com](https://www.edaplayground.com)**
2. In the left editor pane, paste the entire content of [`design.sv`](file://{design_file}).
3. In the right editor pane, paste the entire content of [`testbench.sv`](file://{tb_file}).
4. In the left sidebar:
   - **Tools & Simulators**: Select `{sim_preset['edap_name']}` (or `Synopsys VCS 2021.09`)
   - **Compile Options**: `{sim_preset['compile_options']}`
   - **Run Options**: `{sim_preset['run_options']}`
   - **UVM / OVM**: {"`UVM 1.2`" if is_uvm else "`None`"}
   - **Waveform**: Check `Open EPWave after run`
5. Click **Run** (Ctrl + Enter).

---

## 🔍 Step 2: Feed EDA Playground Results back into VeriSight

Once simulation completes on EDA Playground, download or copy the console log to `sim.log`, and download `dump.vcd` (from EPWave -> File -> Download VCD).

Run VeriSight's autonomous root-cause agent pipeline:

```bash
python main.py --log {out_dir}/sim.log \\
               --vcd {out_dir}/dump.vcd \\
               --rtl {rtl_path} \\
               --tb {tb_path}
```

VeriSight will instantly analyze the cloud Questa/VCS simulation log, trace signal anomalies in the waveform, identify the bug root cause, and propose a self-healing patch!
"""
    readme_file.write_text(readme_text, encoding="utf-8")

    # 7. Generate interactive launch_edaplayground.html dashboard
    launch_html_file = out_dir / "launch_edaplayground.html"
    launch_html = _generate_launch_html(
        design_content=design_content,
        tb_content=tb_content,
        top_module=top_module,
        is_uvm=is_uvm,
        anonymized=anonymize_rtl,
        sim_presets=SIMULATOR_PRESETS,
        preferred_sim=preferred_simulator,
        rtl_path=rtl_path,
        tb_path=tb_path,
    )
    launch_html_file.write_text(launch_html, encoding="utf-8")

    logger.info(f"EDA Playground export successfully written to {out_dir}")

    return {
        "output_dir": str(out_dir),
        "design_sv": str(design_file),
        "testbench_sv": str(tb_file),
        "launch_html": str(launch_html_file),
        "readme_md": str(readme_file),
        "config_json": str(config_file),
        "top_module": top_module,
        "is_uvm": is_uvm,
        "anonymized": anonymize_rtl,
        "anonymized_count": anon_count,
        "rtl_files_count": len(rtl_files),
        "tb_files_count": len(tb_files),
    }


def _generate_launch_html(
    design_content: str,
    tb_content: str,
    top_module: str,
    is_uvm: bool,
    anonymized: bool,
    sim_presets: Dict[str, Any],
    preferred_sim: str,
    rtl_path: str,
    tb_path: str,
) -> str:
    """Generate modern, rich glassmorphic HTML launch studio for EDA Playground."""

    # Escape for embedding in JS template strings
    escaped_design = json.dumps(design_content)
    escaped_tb = json.dumps(tb_content)
    presets_json = json.dumps(sim_presets)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VeriSight — EDA Playground Cloud Simulation Studio</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(18, 24, 38, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent-cyan: #06b6d4;
      --accent-blue: #3b82f6;
      --accent-purple: #8b5cf6;
      --accent-green: #10b981;
      --accent-yellow: #f59e0b;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --code-bg: #060911;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', sans-serif;
      background: radial-gradient(circle at 15% 15%, #131d33 0%, #080c14 100%);
      color: var(--text-main);
      min-height: 100vh;
      padding: 2rem;
      line-height: 1.5;
    }}

    .container {{
      max-width: 1280px;
      margin: 0 auto;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--card-border);
      flex-wrap: wrap;
      gap: 1rem;
    }}

    .logo-area h1 {{
      font-size: 1.75rem;
      font-weight: 800;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .badge {{
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: rgba(6, 182, 212, 0.15);
      color: var(--accent-cyan);
      border: 1px solid rgba(6, 182, 212, 0.3);
    }}

    .badge.green {{
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent-green);
      border-color: rgba(16, 185, 129, 0.3);
    }}

    .badge.purple {{
      background: rgba(139, 92, 246, 0.15);
      color: var(--accent-purple);
      border-color: rgba(139, 92, 246, 0.3);
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.75rem 1.25rem;
      font-weight: 600;
      font-size: 0.95rem;
      border-radius: 8px;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s ease;
      border: none;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, #0284c7, #2563eb);
      color: white;
      box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
    }}
    .btn-primary:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5);
    }}

    .btn-secondary {{
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-main);
      border: 1px solid var(--card-border);
    }}
    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.14);
    }}

    .grid-2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
      margin-bottom: 2rem;
    }}

    @media (max-width: 900px) {{
      .grid-2 {{ grid-template-columns: 1fr; }}
    }}

    .card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.37);
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }}

    .card-title {{
      font-size: 1.15rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .step-list {{
      list-style: none;
      counter-reset: steps;
      margin: 1rem 0;
    }}

    .step-list li {{
      counter-increment: steps;
      margin-bottom: 1rem;
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      font-size: 0.95rem;
    }}

    .step-list li::before {{
      content: counter(steps);
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
      color: white;
      font-weight: 700;
      font-size: 0.8rem;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 2px;
    }}

    .selector-bar {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 1rem;
    }}

    .sim-tab {{
      padding: 0.5rem 0.9rem;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.15s;
    }}

    .sim-tab.active {{
      background: rgba(6, 182, 212, 0.15);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
    }}

    .code-box {{
      background: var(--code-bg);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      color: #e2e8f0;
      max-height: 380px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
      position: relative;
    }}

    .field-row {{
      margin-bottom: 0.85rem;
    }}
    .field-label {{
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.25rem;
    }}
    .field-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.88rem;
      background: rgba(0, 0, 0, 0.35);
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .copy-mini-btn {{
      background: transparent;
      border: none;
      color: var(--accent-cyan);
      cursor: pointer;
      font-size: 0.8rem;
      font-weight: 600;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      transition: background 0.15s;
    }}
    .copy-mini-btn:hover {{
      background: rgba(6, 182, 212, 0.15);
    }}

    .toast {{
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: #10b981;
      color: #022c22;
      font-weight: 700;
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(16, 185, 129, 0.4);
      display: none;
      z-index: 1000;
      animation: fadeIn 0.2s ease;
    }}

    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(10px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo-area">
        <h1>⚡ EDA Playground Cloud Simulation Studio</h1>
        <p style="color: var(--text-muted); font-size: 0.9rem; margin-top: 0.25rem;">
          Exported by <strong>VeriSight</strong> • Run commercial Questa / VCS / Riviera in the cloud for free
        </p>
      </div>
      <div style="display: flex; gap: 0.75rem; align-items: center;">
        <span class="badge green">Top: {top_module}</span>
        <span class="badge purple">{'UVM 1.2' if is_uvm else 'SystemVerilog RTL'}</span>
        {'<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.3);">🛡️ RTL Anonymized</span>' if anonymized else ''}
        <a href="https://www.edaplayground.com" target="_blank" rel="noopener" class="btn btn-primary">
          🚀 Open EDA Playground ↗
        </a>
      </div>
    </header>

    <!-- Step-by-step workflow -->
    <div class="card" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, rgba(14, 25, 48, 0.8), rgba(20, 16, 40, 0.8));">
      <div class="card-title" style="color: var(--accent-cyan); margin-bottom: 0.5rem;">
        📋 3-Minute Cloud Simulation Instructions
      </div>
      <ol class="step-list">
        <li>
          <span>Click <strong>Copy design.sv</strong> below and paste it into the left editor pane on EDA Playground.</span>
        </li>
        <li>
          <span>Click <strong>Copy testbench.sv</strong> below and paste it into the right editor pane on EDA Playground.</span>
        </li>
        <li>
          <span>Select <strong>Tools & Simulators</strong> in the left sidebar (e.g. <em>Siemens Questa</em> or <em>Synopsys VCS</em>) and copy the recommended compile/run flags below.</span>
        </li>
        <li>
          <span>Check <strong>Open EPWave after run</strong> and click <strong>Run</strong> (Ctrl+Enter) to simulate in the cloud!</span>
        </li>
        <li>
          <span>Download <code>sim.log</code> and <code>dump.vcd</code> (from EPWave) into this project, and run VeriSight for automated AI root-cause diagnosis.</span>
        </li>
      </ol>
    </div>

    <!-- Simulator Settings Card -->
    <div class="card" style="margin-bottom: 1.5rem;">
      <div class="card-header">
        <div class="card-title">⚙️ EDA Playground Simulator Configuration</div>
        <span style="font-size: 0.85rem; color: var(--text-muted);">Click a simulator to load options</span>
      </div>

      <div class="selector-bar" id="simTabs">
        <!-- Rendered via JS -->
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-top: 1rem;">
        <div class="field-row">
          <div class="field-label">Selected Simulator</div>
          <div class="field-val" id="valSimName">Loading...</div>
        </div>
        <div class="field-row">
          <div class="field-label">Compile Options (paste into EDA Playground)</div>
          <div class="field-val">
            <span id="valCompileOpts">-timescale 1ns/1ps</span>
            <button class="copy-mini-btn" onclick="copyText(document.getElementById('valCompileOpts').innerText, 'Compile options copied!')">Copy</button>
          </div>
        </div>
        <div class="field-row">
          <div class="field-label">Run Options</div>
          <div class="field-val">
            <span id="valRunOpts">+UVM_VERBOSITY=UVM_HIGH</span>
            <button class="copy-mini-btn" onclick="copyText(document.getElementById('valRunOpts').innerText, 'Run options copied!')">Copy</button>
          </div>
        </div>
        <div class="field-row">
          <div class="field-label">UVM / OVM Selector</div>
          <div class="field-val" id="valUvmOpt">UVM 1.2</div>
        </div>
      </div>
    </div>

    <!-- Dual Code Panes -->
    <div class="grid-2">
      <!-- design.sv -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">📄 design.sv (RTL)</div>
          <button class="btn btn-secondary" onclick="copyDesign()">📋 Copy design.sv</button>
        </div>
        <div class="code-box" id="codeDesign"></div>
      </div>

      <!-- testbench.sv -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">🧪 testbench.sv (Testbench)</div>
          <button class="btn btn-secondary" onclick="copyTb()">📋 Copy testbench.sv</button>
        </div>
        <div class="code-box" id="codeTb"></div>
      </div>
    </div>

    <!-- Import Back to VeriSight Card -->
    <div class="card" style="margin-top: 1.5rem; border-color: rgba(16, 185, 129, 0.3);">
      <div class="card-title" style="color: var(--accent-green); margin-bottom: 0.5rem;">
        🎯 Step 2: Feed EDA Playground Simulation Back into VeriSight
      </div>
      <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 0.75rem;">
        Once your simulation runs on Questa or VCS on EDA Playground, download the console log and <code>dump.vcd</code> (from EPWave -> File -> Download VCD), then run:
      </p>
      <div class="field-val" style="background: var(--code-bg); padding: 0.85rem 1rem;">
        <span id="loopbackCmd">python main.py --log sim.log --vcd dump.vcd --rtl {rtl_path} --tb {tb_path}</span>
        <button class="copy-mini-btn" onclick="copyText(document.getElementById('loopbackCmd').innerText, 'VeriSight command copied!')">Copy Command</button>
      </div>
    </div>
  </div>

  <div id="toast" class="toast">Copied to clipboard!</div>

  <script>
    const designCode = {escaped_design};
    const tbCode = {escaped_tb};
    const presets = {presets_json};
    let currentSim = "{preferred_sim.lower()}";

    document.getElementById('codeDesign').textContent = designCode;
    document.getElementById('codeTb').textContent = tbCode;

    function renderTabs() {{
      const container = document.getElementById('simTabs');
      container.innerHTML = '';
      for (const [key, p] of Object.entries(presets)) {{
        const btn = document.createElement('button');
        btn.className = 'sim-tab' + (key === currentSim ? ' active' : '');
        btn.textContent = p.name;
        btn.onclick = () => selectSim(key);
        container.appendChild(btn);
      }}
      updateSimDetails();
    }}

    function selectSim(key) {{
      currentSim = key;
      renderTabs();
    }}

    function updateSimDetails() {{
      const p = presets[currentSim] || presets['questa'];
      document.getElementById('valSimName').textContent = p.edap_name;
      document.getElementById('valCompileOpts').textContent = p.compile_options || '(None required)';
      document.getElementById('valRunOpts').textContent = p.run_options || '(None required)';
      document.getElementById('valUvmOpt').textContent = p.uvm_options || 'None';
    }}

    function copyText(text, msg) {{
      navigator.clipboard.writeText(text).then(() => {{
        showToast(msg || 'Copied to clipboard!');
      }});
    }}

    function copyDesign() {{
      copyText(designCode, '✓ design.sv copied to clipboard!');
    }}

    function copyTb() {{
      copyText(tbCode, '✓ testbench.sv copied to clipboard!');
    }}

    function showToast(msg) {{
      const toast = document.getElementById('toast');
      toast.textContent = msg;
      toast.style.display = 'block';
      setTimeout(() => {{
        toast.style.display = 'none';
      }}, 2400);
    }}

    renderTabs();
  </script>
</body>
</html>
"""
