"""
EDA Playground Exporter for VeriSight.

Packages RTL designs, testbenches, and UVM suites into clean, single-click
bundles formatted specifically for https://www.edaplayground.com, enabling
free cloud execution with commercial EDA simulators (Siemens Questa,
Synopsys VCS, Cadence Xcelium, Aldec Riviera-PRO).

Includes a 1-Click Auto-Injector Bookmarklet and Console Injector to eliminate
empty-screen sessions and automatically populate design.sv, testbench.sv, and
simulator compiler flags.
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
        "name": "Siemens Questa 2025.2",
        "edap_name": "Siemens Questa 2025.2",
        "sim_id": "1701",
        "compile_options": "-timescale 1ns/1ps +acc=rn -sv",
        "run_options": "+UVM_VERBOSITY=UVM_HIGH",
        "uvm_options": "UVM 1.2",
        "description": "Siemens Questa SIM — Full SystemVerilog IEEE-1800 & UVM 1.2 cloud execution.",
    },
    "vcs": {
        "name": "Synopsys VCS 2025.06",
        "edap_name": "Synopsys VCS 2025.06",
        "sim_id": "1301",
        "compile_options": "-sverilog -debug_access+all -kdb -timescale=1ns/1ps",
        "run_options": "+UVM_VERBOSITY=UVM_HIGH",
        "uvm_options": "UVM 1.2",
        "description": "Synopsys VCS — High-performance commercial SystemVerilog and UVM simulator.",
    },
    "riviera": {
        "name": "Aldec Riviera Pro 2025.04",
        "edap_name": "Aldec Riviera Pro 2025.04",
        "sim_id": "1204",
        "compile_options": "-dbg",
        "run_options": "+access+r",
        "uvm_options": "UVM 1.2",
        "description": "Aldec Riviera-PRO — Popular commercial SystemVerilog / UVM verification platform.",
    },
    "xcelium": {
        "name": "Cadence Xcelium 25.03",
        "edap_name": "Cadence Xcelium 25.03",
        "sim_id": "1501",
        "compile_options": "-access +rwc",
        "run_options": "+UVM_VERBOSITY=UVM_HIGH",
        "uvm_options": "UVM 1.2",
        "description": "Cadence Xcelium — Enterprise multi-core SystemVerilog and UVM simulator.",
    },
    "verilator": {
        "name": "Verilator v5.044",
        "edap_name": "Verilator v5.044",
        "sim_id": "1801",
        "compile_options": "--binary --timing -Wno-fatal --trace",
        "run_options": "",
        "uvm_options": "UVM 1.2 (via DPI-less wrapper)",
        "description": "Open-source high-speed SystemVerilog C++ simulation engine.",
    },
    "iverilog": {
        "name": "Icarus Verilog 12.0",
        "edap_name": "Icarus Verilog 12.0",
        "sim_id": "7",
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


def _generate_userscript(
    design_content: str,
    tb_content: str,
    sim_preset: Dict[str, Any],
    is_uvm: bool,
) -> str:
    """Generate installable Tampermonkey/Violentmonkey UserScript for zero-click loading."""
    escaped_tb = json.dumps(tb_content)
    escaped_d = json.dumps(design_content)
    sim_id = sim_preset.get("sim_id", "1701")
    sim_name = sim_preset.get("edap_name", "Siemens Questa")
    compile_opts = sim_preset.get("compile_options", "")
    run_opts = sim_preset.get("run_options", "")
    is_uvm_str = "true" if is_uvm else "false"

    return f"""// ==UserScript==
// @name         VeriSight — EDA Playground Auto-Injector
// @namespace    https://github.com/verisight
// @version      1.2
// @description  Automatically loads VeriSight exported RTL & Testbench into EDA Playground
// @author       VeriSight
// @match        https://www.edaplayground.com/*
// @grant        none
// ==/UserScript==

(function() {{
    'use strict';

    function injectVeriSight() {{
        var tb = {escaped_tb};
        var design = {escaped_d};
        var simId = "{sim_id}";
        var simName = "{sim_name}";
        var compileOpts = "{compile_opts}";
        var runOpts = "{run_opts}";
        var isUvm = {is_uvm_str};

        var tbDone = false;
        if (window.testbenchEditors && window.testbenchEditors[0] && window.testbenchEditors[0].editor) {{
            window.testbenchEditors[0].editor.setValue(tb);
            tbDone = true;
        }}
        var cms = document.querySelectorAll('.CodeMirror');
        if (!tbDone && cms.length > 0 && cms[0].CodeMirror) {{
            cms[0].CodeMirror.setValue(tb);
        }}

        var dDone = false;
        if (window.designEditors && window.designEditors[0] && window.designEditors[0].editor) {{
            window.designEditors[0].editor.setValue(design);
            dDone = true;
        }}
        if (!dDone && cms.length > 1 && cms[1].CodeMirror) {{
            cms[1].CodeMirror.setValue(design);
        }}

        if (window.$) {{
            var $sim = $('#simulator');
            if ($sim.length) {{
                if (simId && $sim.find('option[value="' + simId + '"]').length) {{
                    $sim.val(simId).trigger('change');
                }} else {{
                    $sim.find('option').each(function() {{
                        if ($(this).text().toLowerCase().indexOf(simName.toLowerCase()) !== -1) {{
                            $sim.val($(this).val()).trigger('change');
                            return false;
                        }}
                    }});
                }}
            }}

            if (isUvm) {{
                var $uvm = $('#methodologyLibrary');
                if ($uvm.length) $uvm.val('701').trigger('change');
            }}

            var $ep = $('#openEpwaveAfterRun');
            if ($ep.length) $ep.prop('checked', true);

            setTimeout(function() {{
                var optPairs = [
                    ['#questaCompileOptions', '#questaRunOptions'],
                    ['#vcsCompileOptions', '#vcsRunOptions'],
                    ['#rivieraCompileOptions', '#rivieraRunOptions'],
                    ['#verilatorCompileOptions', '#verilatorRunOptions'],
                    ['#icarusVerilog09CompileOptions', '#icarusVerilog09RunOptions']
                ];
                for (var i = 0; i < optPairs.length; i++) {{
                    var cEl = $(optPairs[i][0]);
                    var rEl = $(optPairs[i][1]);
                    if (cEl.length && (cEl.is(':visible') || i === 0)) {{
                        if (compileOpts) cEl.val(compileOpts);
                        if (runOpts) rEl.val(runOpts);
                    }}
                }}
            }}, 300);
        }}
    }}

    window.addEventListener('load', function() {{
        setTimeout(function() {{
            var floatingBtn = document.createElement('button');
            floatingBtn.id = 'verisight-auto-inject-btn';
            floatingBtn.innerHTML = '⚡ VeriSight: Inject Code';
            floatingBtn.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:999999;background:linear-gradient(135deg,#0284c7,#2563eb);color:#fff;border:1px solid #38bdf8;padding:12px 20px;border-radius:10px;font-weight:700;font-size:14px;cursor:pointer;box-shadow:0 8px 30px rgba(0,0,0,0.5);font-family:sans-serif;';
            floatingBtn.onclick = function() {{
                injectVeriSight();
                floatingBtn.innerHTML = '✓ VeriSight Injected!';
                floatingBtn.style.background = '#10b981';
                setTimeout(function() {{ floatingBtn.remove(); }}, 3000);
            }};
            document.body.appendChild(floatingBtn);

            if (window.location.hash.indexOf('verisight') !== -1) {{
                injectVeriSight();
            }}
        }}, 800);
    }});
}})();
"""


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
    - edaplayground_config.json: Simulator flags, simulator IDs, and settings
    - launch_edaplayground.html: Rich interactive studio with 1-Click Bookmarklet Injector
    - verisight_autoloader.user.js: Tampermonkey userscript for 0-click auto-loading
    - README.md: Usage and loopback ingestion instructions

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
            "step_1": "Drag the '⚡ Inject to EDA Playground' bookmarklet to your browser bookmarks bar.",
            "step_2": "Click 'Open EDA Playground' to open https://www.edaplayground.com in a new tab.",
            "step_3": "Click your bookmark on EDA Playground to instantly load design.sv, testbench.sv, simulator, and flags.",
            "step_4": "Click 'Run' (Ctrl + Enter) to simulate in the cloud for free with Siemens Questa or Synopsys VCS.",
            "step_5": "Download sim.log and dump.vcd, and feed them into VeriSight for AI root-cause analysis.",
        },
    }
    config_file = out_dir / "edaplayground_config.json"
    config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    # 6. Write UserScript (.user.js)
    userscript_file = out_dir / "verisight_autoloader.user.js"
    userscript_content = _generate_userscript(
        design_content=design_content,
        tb_content=tb_content,
        sim_preset=sim_preset,
        is_uvm=is_uvm,
    )
    userscript_file.write_text(userscript_content, encoding="utf-8")

    # 7. Write README.md
    readme_file = out_dir / "README.md"
    readme_text = f"""# VeriSight — EDA Playground Cloud Execution Bundle

This bundle prepares your design for instant, free simulation on [EDA Playground](https://www.edaplayground.com) using commercial simulators (**Siemens Questa**, **Synopsys VCS**, **Aldec Riviera-PRO**, or **Cadence Xcelium**).

---

## 📁 Bundle Files

| File | Purpose |
|------|---------|
| [`design.sv`](file://{design_file}) | Bundled RTL logic ({len(rtl_files)} source files) |
| [`testbench.sv`](file://{tb_file}) | Bundled Testbench + EPWave `$dumpvars` hook |
| [`launch_edaplayground.html`](file://{out_dir / 'launch_edaplayground.html'}) | **Interactive 1-Click Launch Studio** (Bookmarklet Auto-Injector) |
| [`verisight_autoloader.user.js`](file://{userscript_file}) | Tampermonkey Userscript for 0-click auto-loading |
| [`edaplayground_config.json`](file://{config_file}) | Simulator settings, IDs & compiler flags |

---

## ⚡ Instant 1-Click Execution (No Manual Copy-Pasting!)

1. Open [`launch_edaplayground.html`](file://{out_dir / 'launch_edaplayground.html'}) in your browser.
2. Drag the button **`⚡ Inject to EDA Playground`** to your browser's Bookmarks bar (one-time setup).
3. Click **`🚀 Open EDA Playground ↗`** to open the simulator in a new tab.
4. Click your **`⚡ Inject to EDA Playground`** bookmark!
   - Both `design.sv` and `testbench.sv` are loaded into CodeMirror automatically.
   - Simulator ({sim_preset['edap_name']}) is selected in the dropdown.
   - Compiler and run flags are populated.
   - EPWave waveforms are enabled.
5. Click **Run** (Ctrl + Enter) to simulate!

---

## 🤖 Automated Python Browser Runner (Playwright)

You can also run automated browser injection directly from the command line:

```bash
python -m verisight.tools.eda_runner --bundle {out_dir}
```

---

## 🔍 Step 2: Feed Simulation Results Back into VeriSight

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

    # 8. Generate interactive launch_edaplayground.html dashboard
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
        out_dir=str(out_dir),
    )
    launch_html_file.write_text(launch_html, encoding="utf-8")

    logger.info(f"EDA Playground export successfully written to {out_dir}")

    return {
        "output_dir": str(out_dir),
        "design_sv": str(design_file),
        "testbench_sv": str(tb_file),
        "launch_html": str(launch_html_file),
        "userscript_js": str(userscript_file),
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
    out_dir: str = "",
) -> str:
    """Generate modern, rich glassmorphic HTML launch studio with 1-click Auto-Injector."""

    escaped_design = json.dumps(design_content)
    escaped_tb = json.dumps(tb_content)
    presets_json = json.dumps(sim_presets)
    is_uvm_json = "true" if is_uvm else "false"
    design_lines = len(design_content.splitlines())
    tb_lines = len(tb_content.splitlines())

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
      --bg: #090d16;
      --card-bg: rgba(15, 23, 42, 0.78);
      --card-border: rgba(255, 255, 255, 0.09);
      --accent-cyan: #38bdf8;
      --accent-blue: #0284c7;
      --accent-indigo: #6366f1;
      --accent-green: #10b981;
      --accent-yellow: #f59e0b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --code-bg: #050811;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: radial-gradient(circle at 15% 15%, #0f1c34 0%, #060911 100%);
      color: var(--text-main);
      min-height: 100vh;
      padding: 2rem;
      line-height: 1.55;
    }}

    .container {{
      max-width: 1320px;
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
      gap: 1.25rem;
    }}

    .logo-area h1 {{
      font-size: 1.85rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}

    .badge {{
      display: inline-block;
      padding: 0.3rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.78rem;
      font-weight: 600;
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-cyan);
      border: 1px solid rgba(56, 189, 248, 0.28);
    }}

    .badge.green {{
      background: rgba(16, 185, 129, 0.12);
      color: var(--accent-green);
      border-color: rgba(16, 185, 129, 0.3);
    }}

    .badge.purple {{
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      border-color: rgba(99, 102, 241, 0.35);
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.75rem 1.35rem;
      font-weight: 600;
      font-size: 0.92rem;
      border-radius: 8px;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      border: none;
      user-select: none;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, #0284c7, #2563eb);
      color: white;
      box-shadow: 0 4px 16px rgba(2, 132, 199, 0.35);
    }}
    .btn-primary:hover {{
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(2, 132, 199, 0.55);
    }}

    .btn-inject {{
      background: linear-gradient(135deg, #0284c7, #7c3aed);
      color: #ffffff;
      border: 1px solid rgba(255, 255, 255, 0.25);
      box-shadow: 0 4px 20px rgba(124, 58, 237, 0.35);
      font-size: 0.98rem;
      padding: 0.85rem 1.5rem;
      cursor: grab;
    }}
    .btn-inject:hover {{
      transform: translateY(-2px) scale(1.02);
      box-shadow: 0 8px 28px rgba(124, 58, 237, 0.55);
    }}
    .btn-inject:active {{
      cursor: grabbing;
    }}

    .btn-secondary {{
      background: rgba(255, 255, 255, 0.06);
      color: var(--text-main);
      border: 1px solid var(--card-border);
    }}
    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.2);
    }}

    .card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.6rem;
      box-shadow: 0 10px 32px rgba(0, 0, 0, 0.45);
      margin-bottom: 1.5rem;
    }}

    .hero-inject-card {{
      background: linear-gradient(135deg, rgba(16, 28, 54, 0.92), rgba(24, 18, 48, 0.92));
      border: 1px solid rgba(56, 189, 248, 0.3);
      box-shadow: 0 12px 40px rgba(2, 132, 199, 0.18);
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      flex-wrap: wrap;
      gap: 0.75rem;
    }}

    .card-title {{
      font-size: 1.2rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      letter-spacing: -0.01em;
    }}

    .steps-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1.2rem;
      margin-top: 1.25rem;
    }}

    @media (max-width: 960px) {{
      .steps-grid {{ grid-template-columns: 1fr; }}
    }}

    .step-box {{
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 1.25rem;
      position: relative;
    }}

    .step-num {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: linear-gradient(135deg, #0284c7, #6366f1);
      color: white;
      font-weight: 800;
      font-size: 0.85rem;
      margin-bottom: 0.75rem;
    }}

    .step-box h3 {{
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 0.4rem;
      color: var(--accent-cyan);
    }}

    .step-box p {{
      font-size: 0.88rem;
      color: var(--text-muted);
      line-height: 1.45;
    }}

    .selector-bar {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 1rem;
    }}

    .sim-tab {{
      padding: 0.6rem 1rem;
      border-radius: 7px;
      font-size: 0.85rem;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.15s;
    }}

    .sim-tab:hover {{
      color: var(--text-main);
      background: rgba(255, 255, 255, 0.08);
    }}

    .sim-tab.active {{
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
    }}

    .grid-2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
      margin-bottom: 1.5rem;
    }}

    @media (max-width: 960px) {{
      .grid-2 {{ grid-template-columns: 1fr; }}
    }}

    .code-box {{
      background: var(--code-bg);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.83rem;
      color: #e2e8f0;
      max-height: 380px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }}

    .field-row {{
      margin-bottom: 0.85rem;
    }}
    .field-label {{
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 0.35rem;
    }}
    .field-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.86rem;
      background: rgba(0, 0, 0, 0.35);
      padding: 0.6rem 0.85rem;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
    }}

    .copy-mini-btn {{
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--accent-cyan);
      cursor: pointer;
      font-size: 0.78rem;
      font-weight: 600;
      padding: 0.3rem 0.6rem;
      border-radius: 5px;
      transition: all 0.15s;
      flex-shrink: 0;
    }}
    .copy-mini-btn:hover {{
      background: rgba(56, 189, 248, 0.25);
    }}

    .toast {{
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: #0284c7;
      color: white;
      font-weight: 700;
      font-size: 0.9rem;
      padding: 0.85rem 1.4rem;
      border-radius: 8px;
      box-shadow: 0 10px 30px rgba(2, 132, 199, 0.45);
      display: none;
      z-index: 1000;
      border: 1px solid rgba(255, 255, 255, 0.2);
      animation: fadeIn 0.2s ease;
    }}

    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(8px); }}
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
      <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
        <span class="badge green">Top: {top_module}</span>
        <span class="badge purple">{'UVM 1.2 Suite' if is_uvm else 'SystemVerilog RTL'}</span>
        {'<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.3);">🛡️ Anonymized</span>' if anonymized else ''}
        <a href="https://www.edaplayground.com" target="_blank" rel="noopener" class="btn btn-primary" id="openEdapBtn">
          🚀 Open EDA Playground ↗
        </a>
      </div>
    </header>

    <!-- ⚡ Hero 1-Click Auto-Injector Station -->
    <div class="card hero-inject-card">
      <div class="card-header">
        <div>
          <div class="card-title" style="color: #38bdf8; font-size: 1.3rem;">
            ⚡ 1-Click Auto-Injector (No Blank-Screen, No Manual Copy-Pasting!)
          </div>
          <p style="color: #cbd5e1; font-size: 0.92rem; margin-top: 0.35rem; max-width: 860px;">
            EDA Playground opens blank by default because its server requires database-saved playgrounds and does not accept raw code in URLs. Use VeriSight's <strong>1-Click Bookmarklet</strong> or <strong>Console Injector</strong> to populate all files in under 1 second.
          </p>
        </div>
      </div>

      <!-- Action buttons -->
      <div style="display: flex; gap: 1rem; align-items: center; margin: 1.25rem 0 1.5rem 0; flex-wrap: wrap;">
        <!-- The Draggable Bookmarklet -->
        <a id="bookmarkletLink" href="#" class="btn btn-inject" title="Drag this button to your browser Bookmarks Bar">
          ⭐ Drag to Bookmarks Bar: ⚡ Inject to EDA Playground
        </a>

        <!-- Console Script Copy -->
        <button class="btn btn-secondary" onclick="copyConsoleScript()">
          📋 Copy Console Script (F12)
        </button>

        <!-- Optional Userscript -->
        <a href="verisight_autoloader.user.js" download="verisight_autoloader.user.js" class="btn btn-secondary" title="Install in Tampermonkey / Violentmonkey for zero-click automatic loading">
          🧩 Tampermonkey Script (.user.js)
        </a>
      </div>

      <!-- 3-Step Flow Grid -->
      <div class="steps-grid">
        <div class="step-box">
          <div class="step-num">1</div>
          <h3>Drag to Bookmarks</h3>
          <p>Drag the purple <strong>"⚡ Inject to EDA Playground"</strong> button above onto your browser's Bookmarks bar (one-time setup).</p>
        </div>

        <div class="step-box">
          <div class="step-num">2</div>
          <h3>Open EDA Playground</h3>
          <p>Click <strong>"🚀 Open EDA Playground"</strong> to open <code>edaplayground.com</code> in a new tab (log in with Google/GitHub if prompted).</p>
        </div>

        <div class="step-box">
          <div class="step-num">3</div>
          <h3>Click Bookmark & Run</h3>
          <p>Click your <strong>"⚡ Inject to EDA Playground"</strong> bookmark! Both <code>design.sv</code> and <code>testbench.sv</code> populate immediately. Click <strong>Run</strong>!</p>
        </div>
      </div>
    </div>

    <!-- Simulator Settings Card -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">⚙️ EDA Playground Simulator Configuration</div>
        <span style="font-size: 0.85rem; color: var(--text-muted);">Switching simulators automatically updates the Bookmarklet and flags</span>
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
          <div class="field-label">Compile Options</div>
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
          <div class="card-title">
            📄 design.sv (RTL)
            <span class="badge" style="font-size: 0.72rem; margin-left: 0.5rem;">{design_lines} lines</span>
          </div>
          <button class="btn btn-secondary" onclick="copyDesign()">📋 Copy design.sv</button>
        </div>
        <div class="code-box" id="codeDesign"></div>
      </div>

      <!-- testbench.sv -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            🧪 testbench.sv (Testbench)
            <span class="badge" style="font-size: 0.72rem; margin-left: 0.5rem;">{tb_lines} lines</span>
          </div>
          <button class="btn btn-secondary" onclick="copyTb()">📋 Copy testbench.sv</button>
        </div>
        <div class="code-box" id="codeTb"></div>
      </div>
    </div>

    <!-- Automated Python Runner Option -->
    <div class="card" style="border-color: rgba(99, 102, 241, 0.35);">
      <div class="card-title" style="color: #a5b4fc; margin-bottom: 0.5rem;">
        🤖 Automated Command-Line Browser Runner (Playwright)
      </div>
      <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 0.75rem;">
        Prefer fully autonomous execution? Run VeriSight's browser runner to launch Chromium and automatically inject code via headless or headed mode:
      </p>
      <div class="field-val" style="background: var(--code-bg); padding: 0.75rem 1rem;">
        <span id="runnerCmd">python -m verisight.tools.eda_runner --bundle {out_dir or 'output/edaplayground'}</span>
        <button class="copy-mini-btn" onclick="copyText(document.getElementById('runnerCmd').innerText, 'Runner command copied!')">Copy Command</button>
      </div>
    </div>

    <!-- Import Back to VeriSight Card -->
    <div class="card" style="border-color: rgba(16, 185, 129, 0.3);">
      <div class="card-title" style="color: var(--accent-green); margin-bottom: 0.5rem;">
        🎯 Step 2: Feed Simulation Log & Waveforms Back into VeriSight
      </div>
      <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 0.75rem;">
        Once simulation finishes on Questa or VCS on EDA Playground, download the console log and <code>dump.vcd</code> (from EPWave -> File -> Download VCD), then run:
      </p>
      <div class="field-val" style="background: var(--code-bg); padding: 0.75rem 1rem;">
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
    const isUvm = {is_uvm_json};
    let currentSim = "{preferred_sim.lower()}";

    document.getElementById('codeDesign').textContent = designCode;
    document.getElementById('codeTb').textContent = tbCode;

    function buildInjectorScript(simKey) {{
      const p = presets[simKey] || presets['questa'];
      const simId = p.sim_id || '1701';
      const simName = p.edap_name || 'Questa';
      const compileOpts = p.compile_options || '';
      const runOpts = p.run_options || '';

      return `(function() {{
  var tbCode = ${{JSON.stringify(tbCode)}};
  var designCode = ${{JSON.stringify(designCode)}};
  var targetSimId = ${{JSON.stringify(simId)}};
  var targetSimName = ${{JSON.stringify(simName)}};
  var compileOpts = ${{JSON.stringify(compileOpts)}};
  var runOpts = ${{JSON.stringify(runOpts)}};
  var isUvm = ${{isUvm}};

  // 1. Inject Testbench
  var tbDone = false;
  if (window.testbenchEditors && window.testbenchEditors[0] && window.testbenchEditors[0].editor) {{
    window.testbenchEditors[0].editor.setValue(tbCode);
    tbDone = true;
  }}
  var cms = document.querySelectorAll('.CodeMirror');
  if (!tbDone && cms.length > 0 && cms[0].CodeMirror) {{
    cms[0].CodeMirror.setValue(tbCode);
    tbDone = true;
  }}

  // 2. Inject Design
  var dDone = false;
  if (window.designEditors && window.designEditors[0] && window.designEditors[0].editor) {{
    window.designEditors[0].editor.setValue(designCode);
    dDone = true;
  }}
  if (!dDone && cms.length > 1 && cms[1].CodeMirror) {{
    cms[1].CodeMirror.setValue(designCode);
    dDone = true;
  }}

  // 3. Configure Form Controls
  if (window.$) {{
    var $sim = $('#simulator');
    if ($sim.length) {{
      if (targetSimId && $sim.find('option[value="' + targetSimId + '"]').length) {{
        $sim.val(targetSimId).trigger('change');
      }} else {{
        $sim.find('option').each(function() {{
          if ($(this).text().toLowerCase().indexOf(targetSimName.toLowerCase()) !== -1) {{
            $sim.val($(this).val()).trigger('change');
            return false;
          }}
        }});
      }}
    }}

    if (isUvm) {{
      var $uvm = $('#methodologyLibrary');
      if ($uvm.length) $uvm.val('701').trigger('change');
    }}

    var $ep = $('#openEpwaveAfterRun');
    if ($ep.length) $ep.prop('checked', true);

    setTimeout(function() {{
      var optPairs = [
        ['#questaCompileOptions', '#questaRunOptions'],
        ['#vcsCompileOptions', '#vcsRunOptions'],
        ['#rivieraCompileOptions', '#rivieraRunOptions'],
        ['#verilatorCompileOptions', '#verilatorRunOptions'],
        ['#icarusVerilog09CompileOptions', '#icarusVerilog09RunOptions']
      ];
      for (var i = 0; i < optPairs.length; i++) {{
        var cEl = $(optPairs[i][0]);
        var rEl = $(optPairs[i][1]);
        if (cEl.length && (cEl.is(':visible') || i === 0)) {{
          if (compileOpts) cEl.val(compileOpts);
          if (runOpts) rEl.val(runOpts);
        }}
      }}
    }}, 250);
  }}

  // 4. Notification Toast on EDA Playground
  var prev = document.getElementById('verisight-notification');
  if (prev) prev.remove();
  var note = document.createElement('div');
  note.id = 'verisight-notification';
  note.style.cssText = 'position:fixed;top:20px;right:20px;z-index:999999;background:#090d16;color:#f8fafc;padding:16px 20px;border-radius:10px;box-shadow:0 12px 36px rgba(0,0,0,0.6);border:1px solid #0284c7;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:380px;';
  note.innerHTML = '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;"><span style="color:#38bdf8;font-size:18px;">⚡</span><strong style="font-size:14px;color:#38bdf8;">VeriSight Code Injected!</strong></div><p style="font-size:12.5px;color:#94a3b8;line-height:1.4;margin:0 0 10px 0;">design.sv & testbench.sv loaded. Simulator preconfigured.</p><button id="verisight-run-now" style="background:#0284c7;color:#fff;border:none;padding:6px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Click to Run Simulation</button>';
  document.body.appendChild(note);
  var btn = document.getElementById('verisight-run-now');
  if (btn) {{
    btn.onclick = function() {{
      if (window.$ && $('#runButton').length) $('#runButton').click();
      note.remove();
    }};
  }}
  setTimeout(function() {{ if (note.parentNode) note.remove(); }}, 9000);
}})();`;
    }}

    function updateBookmarklet() {{
      const scriptCode = buildInjectorScript(currentSim);
      const bookmarkletHref = 'javascript:' + encodeURIComponent(scriptCode);
      const bLink = document.getElementById('bookmarkletLink');
      if (bLink) {{
        bLink.setAttribute('href', bookmarkletHref);
      }}
    }}

    function copyConsoleScript() {{
      const scriptCode = buildInjectorScript(currentSim);
      copyText(scriptCode, '✓ Console Injector Script copied! Press F12 on EDA Playground and paste into Console.');
    }}

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
      updateBookmarklet();
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
      }}).catch(() => {{
        // Fallback for non-https contexts
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
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
      }}, 3200);
    }}

    renderTabs();
  </script>
</body>
</html>
"""
