"""
VeriSight Interactive Guided Setup Wizard.

A unified, user-friendly CLI wizard providing:
1. VeriSight Debug  — Autonomous Root-Cause Analysis & Fix Generator.
2. VeriSight Plan   — Autonomous Verification Plan, Functional Coverage & SVA Suite.
3. Quick Demos      — Instant runs on ALU and FIFO designs.
"""

import os
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

from verisight.config import (
    VeriSightConfig,
    LLMConfig,
    ChromaConfig,
    PipelineConfig,
    XTracerConfig,
    FixConfig,
    set_config,
)
from verisight.orchestrator import VeriSightPipeline
from verisight.plan.planner_orchestrator import VeriSightPlanner
from verisight.rag.knowledge_base import KnowledgeBase

console = Console()


def _open_html_in_browser(html_path: Path) -> bool:
    """
    Open an HTML file in the default web browser, supporting WSL2/Windows, Linux, and macOS.
    """
    import shutil
    import subprocess

    resolved = html_path.resolve()

    # 1. Detect if running inside Windows Subsystem for Linux (WSL)
    is_wsl = False
    if os.path.exists("/proc/version"):
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    is_wsl = True
        except Exception:
            pass

    if is_wsl:
        # A. Try wslview if available
        if shutil.which("wslview"):
            try:
                res = subprocess.run(["wslview", str(resolved)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    return True
            except Exception:
                pass

        # B. Convert to Windows path and launch via powershell Start-Process
        if shutil.which("wslpath") and shutil.which("powershell.exe"):
            try:
                out = subprocess.run(["wslpath", "-w", str(resolved)], capture_output=True, text=True, check=True)
                win_path = out.stdout.strip()
                res = subprocess.run(
                    ["powershell.exe", "-Command", f"Start-Process '{win_path}'"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if res.returncode == 0:
                    return True
            except Exception:
                pass

    # 2. Native fallback (Linux xdg-open / macOS open / standard Python webbrowser)
    try:
        return webbrowser.open(f"file://{resolved}")
    except Exception:
        return False


def _print_welcome_banner():
    """Print the interactive wizard welcome banner."""
    title = (
        "[bold cyan]🔍 VeriSight — Autonomous Verification & Debugging Platform[/bold cyan]\n"
        "[bold white]Dual-Engine Autonomous Suite: VeriSight Debug & VeriSight Plan[/bold white]"
    )
    console.print()
    console.print(
        Panel(
            title,
            box=box.DOUBLE,
            border_style="cyan",
            expand=False,
            padding=(1, 4),
        )
    )
    console.print(
        "[dim]Welcome! Select an autonomous workflow below to get started.[/dim]\n"
    )


def _configure_api_key() -> Tuple[str, Optional[str], Optional[str]]:
    """
    Handle API key setup supporting Gemini, Anthropic Claude, custom keys, or offline mode.

    Returns:
        (provider, api_key, model_name)
    """
    gemini_env = os.getenv("GEMINI_API_KEY", "").strip()
    anthropic_env = os.getenv("ANTHROPIC_API_KEY", "").strip()

    table = Table(title="Detected LLM Environment", box=box.ROUNDED, show_lines=True)
    table.add_column("Provider", style="cyan", width=18)
    table.add_column("Status", width=36)

    table.add_row(
        "Google Gemini",
        f"[green]✓ Found in environment[/green] ({gemini_env[:4]}...{gemini_env[-4:]})"
        if gemini_env
        else "[yellow]Not detected[/yellow]",
    )
    table.add_row(
        "Anthropic Claude",
        f"[green]✓ Found in environment[/green] ({anthropic_env[:4]}...{anthropic_env[-4:]})"
        if anthropic_env
        else "[yellow]Not detected[/yellow]",
    )
    console.print(table)
    console.print()

    choices = []
    choice_map = {}
    idx = 1

    if gemini_env:
        choices.append(f"{idx}. Use detected Gemini API key (gemini-2.0-flash)")
        choice_map[str(idx)] = ("gemini", gemini_env, "gemini-2.0-flash")
        idx += 1

    if anthropic_env:
        choices.append(f"{idx}. Use detected Claude API key (claude-sonnet-5)")
        choice_map[str(idx)] = ("anthropic", anthropic_env, "claude-sonnet-5")
        idx += 1

    choices.append(f"{idx}. Enter a new / custom Google Gemini API key")
    choice_map[str(idx)] = "custom_gemini"
    idx += 1

    choices.append(f"{idx}. Enter a new / custom Anthropic Claude API key")
    choice_map[str(idx)] = "custom_claude"
    idx += 1

    choices.append(f"{idx}. Run in Offline / Deterministic Mode (no LLM, heuristic analysis)")
    choice_map[str(idx)] = "offline"

    console.print("[bold]Select LLM & API Key option:[/bold]")
    for c in choices:
        console.print(f"  [cyan]{c}[/cyan]")

    sel = Prompt.ask(
        "\n[bold]Your choice[/bold]",
        choices=[str(i) for i in range(1, idx + 1)],
        default="1",
    )

    action = choice_map[sel]

    if isinstance(action, tuple):
        provider, key, model = action
        console.print(f"[green]✓[/green] Using {provider.capitalize()} API key.")
        return provider, key, model

    if action == "custom_gemini":
        key = Prompt.ask("[bold]Enter your Google Gemini API key[/bold]", password=True)
        while not key.strip():
            console.print("[red]API key cannot be empty.[/red]")
            key = Prompt.ask("[bold]Enter your Google Gemini API key[/bold]", password=True)
        key = key.strip()
        _offer_save_key("GEMINI_API_KEY", key)
        return "gemini", key, "gemini-2.0-flash"

    if action == "custom_claude":
        key = Prompt.ask("[bold]Enter your Anthropic Claude API key[/bold]", password=True)
        while not key.strip():
            console.print("[red]API key cannot be empty.[/red]")
            key = Prompt.ask("[bold]Enter your Anthropic Claude API key[/bold]", password=True)
        key = key.strip()
        _offer_save_key("ANTHROPIC_API_KEY", key)
        return "anthropic", key, "claude-sonnet-5"

    # Offline mode
    console.print("[yellow]! Running in offline deterministic mode (no LLM will be queried).[/yellow]")
    return "gemini", None, "gemini-2.0-flash"


def _offer_save_key(var_name: str, key_val: str):
    """Prompt user if they want to persist their key to .env for future convenience."""
    save = Confirm.ask("Would you like to save this key to your local .env file for future runs?", default=True)
    if save:
        env_path = Path(".env")
        try:
            lines = []
            key_set = False
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(lines):
                    if line.strip().startswith(f"{var_name}="):
                        lines[i] = f'{var_name}="{key_val}"'
                        key_set = True
                        break
            if not key_set:
                lines.append(f'{var_name}="{key_val}"')

            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            console.print(f"[green]✓ Saved {var_name} to .env[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not write to .env: {e}[/yellow]")


def _normalize_input_path(val: str) -> Path:
    """Normalize input string to Path, converting Windows drive paths (C:/) to WSL paths (/mnt/c/)."""
    import re
    cleaned = val.strip().strip("'\"")
    m = re.match(r"^([a-zA-Z]):[/\\](.*)", cleaned)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}")
    return Path(cleaned).expanduser()


def _prompt_path(
    prompt_text: str,
    required: bool = False,
    is_dir: bool = False,
    default: str = "",
) -> Optional[str]:
    """Prompt user for a file or directory path, verifying existence with retry."""
    req_label = "[red](Required)[/red]" if required else "[dim](Optional — press Enter to skip)[/dim]"
    while True:
        prompt_str = f"[bold]{prompt_text}[/bold] {req_label}"
        val = Prompt.ask(prompt_str, default=default).strip()

        if not val:
            if required:
                console.print("[red]This input is required.[/red]")
                continue
            return None

        p = _normalize_input_path(val)
        if not p.exists():
            # 1. Check if an extension was omitted (e.g. .pdf, .md, .txt, .sv, .v, .log)
            found = False
            for ext in [".pdf", ".md", ".txt", ".sv", ".v", ".log"]:
                cand = p.with_suffix(ext)
                if cand.exists():
                    p = cand
                    console.print(f"[green]✓ Auto-resolved extension: {p.name}[/green]")
                    found = True
                    break

            # 2. Check if parent directory contains matching files
            if not found and p.parent.exists():
                stem_lower = p.stem.lower()
                if "Specification" in prompt_text:
                    valid_exts = {".pdf", ".md", ".txt"}
                elif "RTL" in prompt_text:
                    valid_exts = {".sv", ".v"}
                else:
                    valid_exts = None

                matches = [
                    f for f in p.parent.iterdir()
                    if stem_lower in f.name.lower()
                    and (valid_exts is None or f.suffix.lower() in valid_exts)
                ]

                if len(matches) == 1:
                    p = matches[0]
                    console.print(f"[green]✓ Auto-matched file: {p.name}[/green]")
                    found = True
                elif len(matches) > 1:
                    console.print(f"[yellow]Multiple matching files found in {p.parent}:[/yellow]")
                    for idx, m_file in enumerate(matches[:5], 1):
                        console.print(f"  [{idx}] {m_file.name}")
                    choice = Prompt.ask("Select number to use, or press Enter to retry", default="")
                    if choice.isdigit() and 1 <= int(choice) <= len(matches[:5]):
                        p = matches[int(choice) - 1]
                        console.print(f"[green]✓ Selected: {p.name}[/green]")
                        found = True

            if not found:
                console.print(f"[red]Error: Path '{val}' does not exist. Please check and try again.[/red]")
                if val.startswith(("C:", "c:", "D:", "d:")):
                    console.print("[dim]Tip: In Linux/WSL, Windows drives are located at /mnt/c/...[/dim]")
                if not required:
                    skip = Confirm.ask("Would you like to skip this input instead?", default=False)
                    if skip:
                        return None
                continue

        # If it's a directory and spec is expected, auto-detect the file
        if p.is_dir() and "Specification" in prompt_text:
            candidates = list(p.glob("*.md")) + list(p.glob("*.txt")) + list(p.glob("*.pdf"))
            if candidates:
                console.print(f"[green]✓ Found spec file: {candidates[0]}[/green]")
                return str(candidates[0])
            else:
                console.print(f"[red]Error: No .md, .txt, or .pdf specification file found inside '{val}'.[/red]")
                continue

        return str(p)


def run_plan_flow(provider: str, api_key: Optional[str], model_name: Optional[str], spec_path: Optional[str] = None, rtl_path: Optional[str] = None, output_dir: Optional[str] = None):
    """Execute the VeriSight Plan workflow."""
    console.print("\n[bold cyan]📋 VeriSight Plan — Verification & Architecture Plan[/bold cyan]")
    console.print("[dim]Generate Test Plan, Feature Decomposition, SystemVerilog Coverage & SVA Suite.[/dim]\n")

    if not spec_path:
        spec_path = _prompt_path("Specification document file or directory (.md, .txt, .pdf)", required=True, default="")
    if not rtl_path:
        rtl_path = _prompt_path("RTL Source directory or file (.sv, .v)", required=False, default="")
    if not output_dir:
        output_dir = Prompt.ask("[bold]Output directory for verification plan[/bold]", default="output/verification_plan").strip()

    # Configure VeriSight environment for Plan
    llm_kwargs: Dict[str, Any] = {"provider": provider}
    if api_key:
        llm_kwargs["api_key"] = api_key
    if model_name:
        llm_kwargs["model_name"] = model_name

    cfg = VeriSightConfig(
        llm=LLMConfig(**llm_kwargs),
        chroma=ChromaConfig(),
        pipeline=PipelineConfig(output_dir=output_dir),
    )
    set_config(cfg)

    kb = None
    if api_key:
        try:
            kb = KnowledgeBase()
            kb.initialize_collections()
        except Exception:
            kb = None

    console.print("\n[bold cyan]🚀 Launching VeriSight Plan Architect...[/bold cyan]\n")
    try:
        planner = VeriSightPlanner(output_dir=output_dir, knowledge_base=kb)
        report = planner.run(spec_path=spec_path, rtl_path=rtl_path)

        console.print("\n" + "=" * 62)
        console.print("[bold green]🎉 Verification Plan Generated Successfully![/bold green]")
        console.print("=" * 62)
        console.print(f"  [bold]Target Design:[/]         {report.design_name}")
        console.print(f"  [bold]Decomposed Features:[/]   {report.total_features}")
        console.print(f"  [bold]Defined Test Scenarios:[/] {report.total_tests}")
        console.print(f"  [bold]Coverage Points:[/]        {report.total_coverage_points}")
        console.print(f"  [bold]SVA Formal Assertions:[/] {report.total_assertions}")
        console.print()
        console.print(f"  [bold cyan]Generated Artifacts in {output_dir}/:[/bold cyan]")
        console.print(f"    • [white]verification_plan.html[/white]  (Interactive HTML Dashboard)")
        console.print(f"    • [white]verification_plan.md[/white]    (Engineering Markdown Plan)")
        console.print(f"    • [white]traceability_matrix.csv[/white] (ISO 26262/DO-254 Matrix)")
        console.print(f"    • [white]coverage_model.sv[/white]      (SystemVerilog Covergroups Package)")
        console.print(f"    • [white]dut_assertions.sv[/white]      (SystemVerilog Assertions Suite)")
        console.print(f"    • [white]verification_plan.json[/white]  (Unified JSON Schema)")
        console.print()

        html_file = Path(output_dir) / "verification_plan.html"
        if html_file.exists():
            open_html = Confirm.ask("[bold]Open the interactive HTML Verification Plan in your browser?[/bold]", default=True)
            if open_html:
                if _open_html_in_browser(html_file):
                    console.print(f"[green]✓ Opened in your browser: file://{html_file.resolve()}[/green]")
                else:
                    console.print(f"[dim]You can open it at: file://{html_file.resolve()}[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]Verification Planning failed:[/] {e}")


def run_debug_flow(provider: str, api_key: Optional[str], model_name: Optional[str], spec_path: Optional[str] = None, rtl_path: Optional[str] = None, tb_path: Optional[str] = None, log_path: Optional[str] = None, output_dir: Optional[str] = None):
    """Execute the VeriSight Debug workflow."""
    console.print("\n[bold cyan]🛠️ VeriSight Debug — Autonomous Simulation RCA & Fix[/bold cyan]")
    console.print("[dim]Analyze simulation logs, trace root cause, and generate automated code fixes.[/dim]\n")

    if not log_path:
        log_path = _prompt_path("Simulation Log file (.log)", required=True, default="")
    if not rtl_path:
        rtl_path = _prompt_path("RTL Source directory or file (.sv, .v)", required=False, default="")
    if not tb_path:
        tb_path = _prompt_path("UVM Testbench directory or file (.sv)", required=False, default="")
    if not spec_path:
        spec_path = _prompt_path("Design Specification document (.md)", required=False, default="")
    if not output_dir:
        output_dir = Prompt.ask("[bold]Output directory for reports[/bold]", default="output/custom_debug").strip()

    llm_kwargs: Dict[str, Any] = {"provider": provider}
    if api_key:
        llm_kwargs["api_key"] = api_key
    if model_name:
        llm_kwargs["model_name"] = model_name

    config = VeriSightConfig(
        llm=LLMConfig(**llm_kwargs),
        chroma=ChromaConfig(),
        pipeline=PipelineConfig(
            save_intermediates=True,
            enable_rag=bool(api_key),
            output_dir=output_dir,
            verbose=False,
        ),
        xtracer=XTracerConfig(),
        fix=FixConfig(enabled=True),
        log_level="INFO",
    )

    console.print("\n[bold cyan]🚀 Launching VeriSight Debug Pipeline...[/bold cyan]\n")
    try:
        pipeline = VeriSightPipeline(config=config)
        report = pipeline.run(
            spec_path=spec_path,
            rtl_path=rtl_path,
            tb_path=tb_path,
            log_path=log_path,
        )

        console.print("\n" + "=" * 62)
        console.print("[bold green]🎉 Analysis Completed Successfully![/bold green]")
        console.print("=" * 62)
        console.print(f"  [bold]Classification:[/]  {report.classification}")
        console.print(f"  [bold]Confidence:[/]      {report.confidence}%")
        console.print(f"  [bold]Root Cause:[/]      {report.root_cause}")
        console.print(f"  [bold]Category:[/]        {report.category}")
        console.print(f"  [bold]Module:[/]          {report.module}")
        console.print()
        console.print(f"  [bold cyan]Generated Reports in {output_dir}/:[/bold cyan]")
        console.print(f"    • [white]report.html[/white]  (Visual interactive report)")
        console.print(f"    • [white]report.md[/white]    (Detailed markdown documentation)")
        console.print(f"    • [white]error.json[/white]   (Machine-readable error schema)")
        console.print(f"    • [white]summary.txt[/white]  (Executive summary)")
        console.print(f"    • [white]fix/[/white]         (Automated code patch)")
        console.print()

        html_file = Path(output_dir) / "report.html"
        if html_file.exists():
            open_html = Confirm.ask("[bold]Open the HTML report in your browser?[/bold]", default=True)
            if open_html:
                if _open_html_in_browser(html_file):
                    console.print(f"[green]✓ Opened in your browser: file://{html_file.resolve()}[/green]")
                else:
                    console.print(f"[dim]You can open it at: file://{html_file.resolve()}[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]Pipeline encountered an error:[/] {e}")


def run_wizard():
    """Execute the unified interactive guided setup wizard."""
    _print_welcome_banner()

    console.print("[bold cyan]Step 1: Choose Autonomous Workflow[/bold cyan]")
    console.print("  [1] [bold green]🛠️  VeriSight Debug[/bold green]  — Root-Cause Analysis & Fix for Sim Failures")
    console.print("  [2] [bold green]📋 VeriSight Plan[/bold green]   — Generate Test Plan, Coverage Model & SVA Suite")
    console.print("  [3] [bold yellow]⚡ Quick Demos[/bold yellow]      — Instant 1-Click Run on ALU or FIFO")
    console.print("  [4] [bold red]🚪 Exit[/bold red]")
    console.print()

    workflow = Prompt.ask(
        "[bold]Select an option[/bold]",
        choices=["1", "2", "3", "4"],
        default="1",
    )

    if workflow == "4":
        console.print("[dim]Exiting VeriSight. Goodbye![/dim]")
        sys.exit(0)

    console.print("\n[bold cyan]Step 2: LLM Configuration[/bold cyan]")
    provider, api_key, model_name = _configure_api_key()

    if workflow == "1":
        run_debug_flow(provider, api_key, model_name)

    elif workflow == "2":
        run_plan_flow(provider, api_key, model_name)

    elif workflow == "3":
        console.print("\n[bold cyan]Select Pre-packaged Demo:[/bold cyan]")
        console.print("  [1] ALU Debug Demo   (Detect Missing Reset Bug)")
        console.print("  [2] FIFO Debug Demo  (Synchronous FIFO UVM Debug)")
        console.print("  [3] ALU Plan Demo    (Generate Full Test Plan, SV Coverage & SVA for ALU)")
        console.print("  [4] FIFO Plan Demo   (Generate Full Test Plan, SV Coverage & SVA for FIFO)")

        demo_sel = Prompt.ask("[bold]Your choice[/bold]", choices=["1", "2", "3", "4"], default="1")

        if demo_sel == "1":
            run_debug_flow(
                provider, api_key, model_name,
                spec_path="examples/specs/alu_spec.md",
                rtl_path="examples/rtl/",
                tb_path="examples/tb/",
                log_path="examples/logs/sim.log",
                output_dir="output/demo_alu_debug",
            )
        elif demo_sel == "2":
            run_debug_flow(
                provider, api_key, model_name,
                spec_path="projects/fifo/specs/spec.md",
                rtl_path="projects/fifo/rtl/",
                tb_path="projects/fifo/tb/",
                log_path="projects/fifo/logs/sim.log",
                output_dir="output/demo_fifo_debug",
            )
        elif demo_sel == "3":
            run_plan_flow(
                provider, api_key, model_name,
                spec_path="examples/specs/alu_spec.md",
                rtl_path="examples/rtl/",
                output_dir="output/demo_alu_plan",
            )
        elif demo_sel == "4":
            run_plan_flow(
                provider, api_key, model_name,
                spec_path="projects/fifo/specs/spec.md",
                rtl_path="projects/fifo/rtl/",
                output_dir="output/demo_fifo_plan",
            )
