"""
EDA Playground Automated Browser Runner for VeriSight.

Enables automated loading of RTL designs, testbenches, and compiler options
directly into https://www.edaplayground.com via Playwright (or browser fallback),
eliminating blank-screen sessions and manual copy-pasting.
"""

import argparse
import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional

from verisight.utils.logger import get_logger

logger = get_logger("eda_runner")


def run_eda_browser(
    bundle_dir: str = "output/edaplayground",
    headless: bool = False,
    auto_run: bool = False,
    timeout_sec: int = 300,
) -> bool:
    """
    Launch an automated browser session on EDA Playground and inject bundle files.

    If Playwright is installed, launches a Chromium instance, opens EDA Playground,
    populates testbench.sv and design.sv into CodeMirror, selects the target
    simulator and options, and checks EPWave.

    If Playwright is not installed, opens the interactive Launch Studio HTML
    with the 1-click Bookmarklet and Console Injector.
    """
    bundle_path = Path(bundle_dir).resolve()
    if not bundle_path.exists():
        logger.error(f"Bundle directory does not exist: {bundle_path}")
        print(f"Error: Bundle directory not found: {bundle_path}")
        print("Run export first: python -m verisight.tools.eda_playground_exporter")
        return False

    design_file = bundle_path / "design.sv"
    tb_file = bundle_path / "testbench.sv"
    config_file = bundle_path / "edaplayground_config.json"
    launch_html = bundle_path / "launch_edaplayground.html"

    if not design_file.exists() or not tb_file.exists():
        logger.error(f"Missing design.sv or testbench.sv in {bundle_path}")
        print(f"Error: Incomplete bundle in {bundle_path}")
        return False

    design_code = design_file.read_text(encoding="utf-8", errors="ignore")
    tb_code = tb_file.read_text(encoding="utf-8", errors="ignore")

    config = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    preferred_sim = config.get("recommended_simulator", "questa")
    sim_info = config.get("simulators", {}).get(preferred_sim, {})
    sim_id = sim_info.get("sim_id", "1701")
    sim_name = sim_info.get("edap_name", "Siemens Questa")
    compile_opts = sim_info.get("compile_options", "")
    run_opts = sim_info.get("run_options", "")
    is_uvm = config.get("is_uvm", False)

    # Check if Playwright is available
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n" + "=" * 68)
        print("  ⚡ VeriSight — EDA Playground Automated Browser Runner")
        print("=" * 68)
        print("Playwright is not installed in the current Python environment.")
        print("To enable fully automated, autonomous browser injection:")
        print("    pip install playwright && playwright install chromium\n")
        print("Opening the VeriSight Launch Studio with 1-Click Auto-Injector...")
        print("=" * 68 + "\n")

        if launch_html.exists():
            webbrowser.open(f"file://{launch_html.resolve()}")
            print(f"✓ Opened Launch Studio: file://{launch_html.resolve()}")
            print("Tip: Drag the '⚡ Inject to EDA Playground' bookmarklet to your")
            print("bookmarks bar, then click it on EDA Playground to load code in 1 click!")
        else:
            webbrowser.open("https://www.edaplayground.com")
        return True

    # Playwright automated execution
    print(f"\n🚀 Launching Chromium to load EDA Playground ({preferred_sim.upper()})...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            page.goto("https://www.edaplayground.com", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".CodeMirror", timeout=15000)

            # Evaluate injection inside browser context
            injection_script = """
            ([tb, design, simId, simName, compileOpts, runOpts, isUvm]) => {
                let tbDone = false;
                if (window.testbenchEditors && window.testbenchEditors[0] && window.testbenchEditors[0].editor) {
                    window.testbenchEditors[0].editor.setValue(tb);
                    tbDone = true;
                }
                const cms = document.querySelectorAll('.CodeMirror');
                if (!tbDone && cms.length > 0 && cms[0].CodeMirror) {
                    cms[0].CodeMirror.setValue(tb);
                }

                let dDone = false;
                if (window.designEditors && window.designEditors[0] && window.designEditors[0].editor) {
                    window.designEditors[0].editor.setValue(design);
                    dDone = true;
                }
                if (!dDone && cms.length > 1 && cms[1].CodeMirror) {
                    cms[1].CodeMirror.setValue(design);
                }

                if (window.$) {
                    const $sim = $('#simulator');
                    if ($sim.length) {
                        if (simId && $sim.find('option[value="' + simId + '"]').length) {
                            $sim.val(simId).trigger('change');
                        } else {
                            $sim.find('option').each(function() {
                                if ($(this).text().toLowerCase().includes(simName.toLowerCase())) {
                                    $sim.val($(this).val()).trigger('change');
                                    return false;
                                }
                            });
                        }
                    }

                    if (isUvm) {
                        $('#methodologyLibrary').val('701').trigger('change');
                    }

                    $('#openEpwaveAfterRun').prop('checked', true);

                    setTimeout(() => {
                        const optPairs = [
                            ['#questaCompileOptions', '#questaRunOptions'],
                            ['#vcsCompileOptions', '#vcsRunOptions'],
                            ['#rivieraCompileOptions', '#rivieraRunOptions'],
                            ['#verilatorCompileOptions', '#verilatorRunOptions'],
                            ['#icarusVerilog09CompileOptions', '#icarusVerilog09RunOptions']
                        ];
                        for (const [cId, rId] of optPairs) {
                            const cEl = $(cId);
                            const rEl = $(rId);
                            if (cEl.length && (cEl.is(':visible') || cId.includes('questa'))) {
                                if (compileOpts) cEl.val(compileOpts);
                                if (runOpts) rEl.val(runOpts);
                            }
                        }
                    }, 300);
                }
                return true;
            }
            """

            page.evaluate(
                injection_script,
                [tb_code, design_code, sim_id, sim_name, compile_opts, run_opts, is_uvm],
            )
            print("✓ Files injected into EDA Playground (design.sv, testbench.sv, simulator options).")

            if auto_run:
                print("⚡ Triggering cloud simulation ('Run')...")
                page.click("#runButton")
                page.wait_for_timeout(5000)

            if not headless:
                print("Browser is active. You can now observe waveforms and simulation log directly.")
                print(f"Keeping session alive for up to {timeout_sec} seconds (press Ctrl+C to close)...")
                try:
                    time.sleep(timeout_sec)
                except KeyboardInterrupt:
                    print("\nClosing browser session.")

            browser.close()
            return True

    except Exception as e:
        logger.error(f"Playwright automation encountered an error: {e}")
        print(f"Playwright automation notice: {e}")
        print("Falling back to Launch Studio in default browser...")
        if launch_html.exists():
            webbrowser.open(f"file://{launch_html.resolve()}")
        return False


def main():
    parser = argparse.ArgumentParser(description="VeriSight EDA Playground Automated Browser Runner")
    parser.add_argument(
        "--bundle",
        "-b",
        default="output/edaplayground",
        help="Path to exported EDA Playground bundle directory (default: output/edaplayground)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (default: False)",
    )
    parser.add_argument(
        "--auto-run",
        action="store_true",
        help="Automatically click 'Run' button after injection (default: False)",
    )
    args = parser.parse_args()

    run_eda_browser(
        bundle_dir=args.bundle,
        headless=args.headless,
        auto_run=args.auto_run,
    )


if __name__ == "__main__":
    main()
