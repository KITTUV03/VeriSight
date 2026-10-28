"""
VeriSight Interactive Guided Setup Wizard.

A unified, user-friendly CLI wizard providing:
1. VeriSight Debug   — Autonomous Root-Cause Analysis & Fix Generator.
2. VeriSight Plan    — Autonomous Verification Plan, Functional Coverage & SVA Suite.
3. XcelUVM Architect — Autonomous Full Production UVM 1.2 Testbench Environment.
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
    banner_content = (
        "[bold cyan]⚡ V E R I S I G H T[/bold cyan]  [dim]•[/dim]  [bold white]AUTONOMOUS ASIC & SOC VERIFICATION[/bold white]\n"
        "[dim cyan]Tri-Engine Architecture: Diagnostic Debug • Plan Synthesis • UVM Architecture[/dim cyan]\n"
        "[dim]Enterprise-grade multi-agent reasoning, deep AST inspection & protocol compliance[/dim]"
    )
    console.print()
    console.print(
        Panel(
            banner_content,
            box=box.ROUNDED,
            border_style="cyan",
            expand=False,
            padding=(1, 3),
            title="[bold cyan] VERISIGHT CORE ENGINE [/bold cyan]",
            title_align="center",
            subtitle="[dim]v1.2.0 Enterprise Edition[/dim]",
            subtitle_align="right",
        )
    )
    console.print()


def _configure_api_key() -> Tuple[str, Optional[str], Optional[str], bool, bool, str]:
    """
    Handle API key setup supporting Gemini, Anthropic Claude, Sovereign Air-Gapped (Ollama/vLLM),
    custom keys, or deterministic offline mode.
    Actively probes key health to prevent authentication crashes and retry spam.

    Returns:
        (provider, api_key, model_name, airgap, anonymize_rtl, local_endpoint)
    """
    from dotenv import load_dotenv
    from verisight.utils.key_validator import (
        probe_gemini_key,
        probe_anthropic_key,
        probe_local_engine,
    )

    # Ensure .env is freshly loaded with override=True so changes in .env are picked up
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=True)
    elif Path(".env").exists():
        load_dotenv(dotenv_path=Path(".env"), override=True)

    gemini_env = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    anthropic_env = (os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY") or "").strip()
    configured_provider = (os.getenv("VERISIGHT_PROVIDER") or "").strip().lower()

    # Fast non-blocking health probe
    with console.status("[dim]Probing AI execution environments & credentials...[/dim]"):
        g_valid, g_status = probe_gemini_key(gemini_env)
        a_valid, a_status = probe_anthropic_key(anthropic_env)
        l_valid, l_status = probe_local_engine()

    table = Table(
        title="[bold cyan]Detected AI Execution Environments & Health Status[/bold cyan]",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold cyan",
    )
    table.add_column("Environment / Provider", style="bold white", width=28)
    table.add_column("Live Health & Credentials", width=48)

    # Gemini Status
    if g_valid:
        g_cell = f"[bold green]● Active & Validated[/bold green] [dim]({g_status})[/dim]"
    elif gemini_env:
        g_cell = f"[bold yellow]▲ Probe Warning[/bold yellow] [dim]({g_status})[/dim]"
    else:
        g_cell = "[dim yellow]○ Not configured in .env[/dim yellow]"
    table.add_row("Google Gemini (Cloud)", g_cell)

    # Anthropic Status
    if a_valid:
        a_cell = f"[bold green]● Active & Validated[/bold green] [dim]({a_status})[/dim]"
    elif anthropic_env:
        a_cell = f"[bold yellow]▲ Probe Warning[/bold yellow] [dim]({a_status})[/dim]"
    else:
        a_cell = "[dim yellow]○ Not configured in .env[/dim yellow]"
    table.add_row("Anthropic Claude (Cloud)", a_cell)

    # Local Engine Status
    if l_valid:
        l_cell = f"[bold green]● Local Engine Online[/bold green] [dim]({l_status})[/dim]"
    else:
        l_cell = "[bold cyan]● Sovereign Local Ready[/bold cyan] [dim](Zero Cloud RTL Leakage Certified)[/dim]"
    table.add_row("🛡️ Sovereign On-Prem (Local)", l_cell)

    console.print(table)
    console.print()

    choices = []
    choice_map = {}
    idx = 1
    recommended_idx = "1"

    # 1. Sovereign Air-Gap (Always Available)
    choices.append(f"{idx}. 🛡️  Sovereign Air-Gapped Mode (Local Ollama/vLLM — Zero Cloud RTL Leakage)")
    choice_map[str(idx)] = "airgap"
    idx += 1

    # 2. Google Gemini
    gemini_choice_idx = None
    if gemini_env:
        gemini_choice_idx = str(idx)
        if g_valid:
            choices.append(f"{idx}. Use detected Gemini Cloud key [bold green]✓ ACTIVE[/bold green] (gemini-3.5-flash)")
        else:
            choices.append(f"{idx}. Use detected Gemini Cloud key [yellow]⚠ UNVERIFIED[/yellow] ({g_status})")
        choice_map[str(idx)] = ("gemini", gemini_env, "gemini-3.5-flash", False, False, "", g_valid, g_status)
        idx += 1

    # 3. Anthropic Claude
    claude_choice_idx = None
    if anthropic_env:
        claude_choice_idx = str(idx)
        if a_valid:
            choices.append(f"{idx}. Use detected Claude API key [bold green]✓ ACTIVE[/bold green] (claude-sonnet-5)")
        else:
            choices.append(f"{idx}. Use detected Claude Cloud key [yellow]⚠ UNVERIFIED[/yellow] ({a_status})")
        choice_map[str(idx)] = ("anthropic", anthropic_env, "claude-sonnet-5", False, False, "", a_valid, a_status)
        idx += 1

    # 4. Custom keys
    choices.append(f"{idx}. Enter custom Google Gemini API key")
    choice_map[str(idx)] = "custom_gemini"
    idx += 1

    choices.append(f"{idx}. Enter custom Anthropic Claude API key")
    choice_map[str(idx)] = "custom_claude"
    idx += 1

    # 5. Deterministic Offline
    choices.append(f"{idx}. Run in Offline / Deterministic Mode (pure rule-based analysis, no LLM)")
    choice_map[str(idx)] = "offline"

    # Determine recommended index based on provider preference & health
    if configured_provider in ("gemini", "google") and gemini_choice_idx:
        recommended_idx = gemini_choice_idx
    elif configured_provider in ("anthropic", "claude") and claude_choice_idx:
        recommended_idx = claude_choice_idx
    elif gemini_choice_idx and g_valid:
        recommended_idx = gemini_choice_idx
    elif claude_choice_idx and a_valid:
        recommended_idx = claude_choice_idx
    elif gemini_choice_idx:
        recommended_idx = gemini_choice_idx
    elif claude_choice_idx:
        recommended_idx = claude_choice_idx

    # Annotate recommended choice
    for i, c in enumerate(choices):
        prefix = f"{recommended_idx}."
        if c.startswith(prefix):
            choices[i] = c.replace(prefix, f"{prefix} [bold green][RECOMMENDED][/bold green]", 1)
            break

    console.print("[bold]Select AI Execution & Security Mode:[/bold]")
    for c in choices:
        console.print(f"  [cyan]{c}[/cyan]")

    sel = Prompt.ask(
        "\n[bold]Your choice[/bold]",
        choices=[str(i) for i in range(1, idx + 1)],
        default=recommended_idx,
    )

    action = choice_map[sel]

    # Sovereign Air-Gap Selection
    if action == "airgap":
        console.print("\n[bold green]🛡️ Sovereign Air-Gapped Mode Activated![/bold green]")
        console.print("[dim]Enforcing zero cloud RTL leakage. Outbound internet calls will be blocked.[/dim]")
        
        local_model = Prompt.ask(
            "[bold]Local LLM Model[/bold]",
            default="deepseek-coder:33b",
        ).strip()
        
        local_endpoint = Prompt.ask(
            "[bold]Local Inference Endpoint[/bold]",
            default="http://localhost:11434",
        ).strip()

        anonymize = Confirm.ask(
            "[bold]Enable Confidential RTL IP Token Masking (scrub proprietary signal names)?[/bold]",
            default=True,
        )

        return "ollama", "sovereign_local_key", local_model, True, anonymize, local_endpoint

    if isinstance(action, tuple):
        provider, key, model, airgap, anon, endpoint, is_healthy, health_msg = action
        
        # If the user selected a key that reported a health warning, ask if they want to proceed anyway
        if not is_healthy:
            console.print(f"\n[bold yellow]⚠️ Selected {provider.capitalize()} API key reported a health warning:[/bold yellow]")
            console.print(f"   [yellow]Probe Message:[/] {health_msg}")
            
            proceed_anyway = Confirm.ask(
                f"[bold]Would you like to proceed using this existing {provider.capitalize()} API key anyway?[/bold]",
                default=True,
            )
            if proceed_anyway:
                console.print(f"[green]✓ Proceeding with existing {provider.capitalize()} API key.[/green]")
                os.environ["VERISIGHT_PROVIDER"] = provider
                return provider, key, model, airgap, anon, endpoint

            remedy_choices = []
            remedy_map = {}
            r_idx = 1
            
            remedy_choices.append(f"{r_idx}. Proceed anyway with detected {provider.capitalize()} key (bypass probe check)")
            remedy_map[str(r_idx)] = "proceed_anyway"
            r_idx += 1

            if provider != "gemini" and gemini_env:
                remedy_choices.append(f"{r_idx}. Switch to Google Gemini (Detected in environment)")
                remedy_map[str(r_idx)] = "switch_gemini"
                r_idx += 1
            elif provider != "anthropic" and anthropic_env:
                remedy_choices.append(f"{r_idx}. Switch to Anthropic Claude (Detected in environment)")
                remedy_map[str(r_idx)] = "switch_anthropic"
                r_idx += 1
                
            remedy_choices.append(f"{r_idx}. Enter a new, working {provider.capitalize()} API key")
            remedy_map[str(r_idx)] = f"enter_{provider}"
            r_idx += 1

            remedy_choices.append(f"{r_idx}. Switch to Sovereign Air-Gapped Mode (Local Ollama/vLLM)")
            remedy_map[str(r_idx)] = "airgap"
            r_idx += 1

            remedy_choices.append(f"{r_idx}. Continue in Offline Deterministic Mode (no LLM, rule-based)")
            remedy_map[str(r_idx)] = "offline"

            console.print("\n[bold]Select diagnostic remediation:[/bold]")
            for rc in remedy_choices:
                console.print(f"  [cyan]{rc}[/cyan]")
                
            rem_sel = Prompt.ask("\n[bold]Your choice[/bold]", choices=[str(i) for i in range(1, r_idx + 1)], default="1")
            rem_action = remedy_map[rem_sel]

            if rem_action == "proceed_anyway":
                console.print(f"[green]✓ Proceeding with existing {provider.capitalize()} API key.[/green]")
                os.environ["VERISIGHT_PROVIDER"] = provider
                return provider, key, model, airgap, anon, endpoint
            elif rem_action == "switch_anthropic":
                console.print("[green]✓ Switched to Anthropic Claude.[/green]")
                os.environ["VERISIGHT_PROVIDER"] = "anthropic"
                return "anthropic", anthropic_env, "claude-sonnet-5", False, False, ""
            elif rem_action == "switch_gemini":
                console.print("[green]✓ Switched to Google Gemini.[/green]")
                os.environ["VERISIGHT_PROVIDER"] = "gemini"
                return "gemini", gemini_env, "gemini-3.5-flash", False, False, ""
            elif rem_action == f"enter_{provider}":
                action = f"custom_{provider}"
            elif rem_action == "airgap":
                return "ollama", "sovereign_local_key", "deepseek-coder:33b", True, False, "http://localhost:11434"
            else:
                return "gemini", None, "gemini-3.5-flash", True, False, ""

        if isinstance(action, tuple):
            console.print(f"[green]✓[/green] Using verified {provider.capitalize()} API key.")
            os.environ["VERISIGHT_PROVIDER"] = provider
            return provider, key, model, airgap, anon, endpoint

    if action == "custom_gemini":
        while True:
            key = Prompt.ask("[bold]Enter your Google Gemini API key[/bold]", password=True).strip()
            if not key:
                console.print("[red]API key cannot be empty.[/red]")
                continue
            
            with console.status("Validating Gemini key with Google..."):
                ok, msg = probe_gemini_key(key)
                
            if ok:
                console.print(f"[bold green]✓ Key validated successfully![/bold green] ({msg})")
                _offer_save_key("GEMINI_API_KEY", key)
                anon = Confirm.ask("Enable Confidential RTL IP Token Masking before sending to Google Cloud?", default=False)
                os.environ["VERISIGHT_PROVIDER"] = "gemini"
                return "gemini", key, "gemini-3.5-flash", False, anon, ""
            else:
                console.print(f"[bold yellow]⚠️ Key probe warning:[/] {msg}")
                use_anyway = Confirm.ask("Would you like to use this Gemini key anyway without validation?", default=True)
                if use_anyway:
                    _offer_save_key("GEMINI_API_KEY", key)
                    anon = Confirm.ask("Enable Confidential RTL IP Token Masking before sending to Google Cloud?", default=False)
                    os.environ["VERISIGHT_PROVIDER"] = "gemini"
                    return "gemini", key, "gemini-3.5-flash", False, anon, ""
                retry = Confirm.ask("Would you like to try entering the key again?", default=True)
                if not retry:
                    console.print("[yellow]Falling back to offline deterministic mode.[/yellow]")
                    return "gemini", None, "gemini-3.5-flash", True, False, ""

    if action == "custom_claude":
        while True:
            key = Prompt.ask("[bold]Enter your Anthropic Claude API key[/bold]", password=True).strip()
            if not key:
                console.print("[red]API key cannot be empty.[/red]")
                continue
            
            with console.status("Validating Claude key with Anthropic..."):
                ok, msg = probe_anthropic_key(key)
                
            if ok:
                console.print(f"[bold green]✓ Key validated successfully![/bold green] ({msg})")
                _offer_save_key("ANTHROPIC_API_KEY", key)
                anon = Confirm.ask("Enable Confidential RTL IP Token Masking before sending to Anthropic Cloud?", default=False)
                os.environ["VERISIGHT_PROVIDER"] = "anthropic"
                return "anthropic", key, "claude-sonnet-5", False, anon, ""
            else:
                console.print(f"[bold yellow]⚠️ Key probe warning:[/] {msg}")
                use_anyway = Confirm.ask("Would you like to use this Claude key anyway without validation?", default=True)
                if use_anyway:
                    _offer_save_key("ANTHROPIC_API_KEY", key)
                    anon = Confirm.ask("Enable Confidential RTL IP Token Masking before sending to Anthropic Cloud?", default=False)
                    os.environ["VERISIGHT_PROVIDER"] = "anthropic"
                    return "anthropic", key, "claude-sonnet-5", False, anon, ""
                retry = Confirm.ask("Would you like to try entering the key again?", default=True)
                if not retry:
                    console.print("[yellow]Falling back to offline deterministic mode.[/yellow]")
                    return "gemini", None, "gemini-3.5-flash", True, False, ""

    # Offline mode
    console.print("[yellow]! Running in offline deterministic mode (no LLM will be queried).[/yellow]")
    return "gemini", None, "gemini-3.5-flash", True, False, ""


def _offer_save_key(var_name: str, key_val: str):
    """Prompt user if they want to persist their key to .env for future convenience."""
    os.environ[var_name] = key_val  # Instantly update current process environment
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
    file_types: Optional[list] = None,
    allow_empty: bool = True,
    **kwargs,
) -> Optional[str]:
    """Prompt user for a file or directory path, verifying existence with retry."""
    req_label = "[red](Required)[/red]" if required else "[dim](Optional — press Enter to skip)[/dim]"
    while True:
        prompt_str = f"[bold white]{prompt_text}[/bold white] {req_label}"
        val = Prompt.ask(prompt_str, default=default).strip()

        if not val:
            if required and not allow_empty:
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


def run_plan_flow(
    provider: str,
    api_key: Optional[str],
    model_name: Optional[str],
    spec_path: Optional[str] = None,
    rtl_path: Optional[str] = None,
    coverage_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    airgap: bool = False,
    anonymize_rtl: bool = False,
    local_endpoint: str = "",
):
    """Execute the VeriSight Plan workflow."""
    console.print()
    console.print(
        Panel(
            "[bold white]Autonomous Verification Plan, Feature Decomposition & SVA Suite Synthesizer[/bold white]\n"
            "[dim]Translates specifications into formal test plans, protocol functional coverage, and SystemVerilog assertions.[/dim]",
            title="[bold cyan]📋 VERISIGHT PLAN ARCHITECT[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()

    if not spec_path:
        default_spec = "examples/specs/alu_spec.md" if Path("examples/specs/alu_spec.md").exists() else ""
        spec_path = _prompt_path("Specification document file or directory (.md, .txt, .pdf)", required=True, default=default_spec)
    if not rtl_path:
        default_rtl = ""
        if spec_path:
            sp = Path(spec_path)
            for cd in [sp.parent.parent / "rtl", sp.parent / "rtl"]:
                if cd.exists() and cd.is_dir():
                    rtl_cands = list(cd.glob("*.sv")) + list(cd.glob("*.v"))
                    if rtl_cands:
                        default_rtl = str(rtl_cands[0])
                        break
        if not default_rtl and Path("examples/rtl/alu.sv").exists():
            default_rtl = "examples/rtl/alu.sv"
        rtl_path = _prompt_path("RTL Source directory or file (.sv, .v)", required=False, default=default_rtl)
    if coverage_path is None:
        coverage_path = _prompt_path("Simulator Coverage Database / Report (optional .ucdb, .vdb, .txt, .json)", required=False, default="")
    if not output_dir:
        output_dir = Prompt.ask("[bold]Output directory for verification plan[/bold]", default="output/verification_plan").strip()

    # Pre-Flight Configuration Summary
    summary_table = Table(
        title="[bold cyan]VeriSight Plan Pre-Flight Configuration[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    summary_table.add_column("Parameter", style="cyan", width=24)
    summary_table.add_column("Configured Target", style="white", width=54)

    summary_table.add_row("Design Specification", str(spec_path) if spec_path else "[dim]None[/dim]")
    summary_table.add_row("RTL Source", str(rtl_path) if rtl_path else "[dim]Inferred / Optional[/dim]")
    summary_table.add_row("Coverage Database", str(coverage_path) if coverage_path else "[dim]None (Cold-start Plan)[/dim]")
    summary_table.add_row("AI Provider / Model", f"{provider.capitalize()} ({model_name or 'default'})" if not airgap else "Sovereign Air-Gapped (Local)")
    summary_table.add_row("Output Directory", output_dir)

    console.print(summary_table)
    console.print()

    # Configure VeriSight environment for Plan
    llm_kwargs: Dict[str, Any] = {
        "provider": provider,
        "airgap": airgap,
        "anonymize_rtl": anonymize_rtl,
        "local_endpoint": local_endpoint,
    }
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
    if api_key and not airgap:
        try:
            kb = KnowledgeBase()
            kb.initialize_collections()
        except Exception:
            kb = None

    with console.status("[bold green]Synthesizing Verification Architecture, Coverage Models & SVA...[/bold green]"):
        try:
            planner = VeriSightPlanner(output_dir=output_dir, knowledge_base=kb)
            report = planner.run(
                spec_path=spec_path,
                rtl_path=rtl_path,
                coverage_path=coverage_path if coverage_path else None,
            )
        except Exception as e:
            console.print(f"\n[bold red]Verification Planning failed:[/] {e}")
            return

    # Post-Execution Scorecard
    scorecard = Table(box=box.ROUNDED, show_header=False, border_style="green", expand=False)
    scorecard.add_column("Metric", style="bold cyan", width=25)
    scorecard.add_column("Value", style="bold white", width=53)

    scorecard.add_row("Synthesis Status", "[bold green]✓ Verification Plan Generated[/bold green]")
    scorecard.add_row("Target Design", f"[bold white]{report.design_name.upper()}[/bold white]")
    scorecard.add_row("Decomposed Features", f"[bold green]{report.total_features}[/bold green] functional features")
    scorecard.add_row("Defined Test Scenarios", f"[bold green]{report.total_tests}[/bold green] test scenarios")
    scorecard.add_row("Coverage Points", f"[bold green]{report.total_coverage_points}[/bold green] covergroups & bins")
    scorecard.add_row("SVA Formal Assertions", f"[bold green]{report.total_assertions}[/bold green] assertions synthesized")
    scorecard.add_row("Simulator Coverage Hit", f"[cyan]{report.actual_coverage_overall}% Hit[/cyan] (Target: {report.target_coverage_overall}%)")
    scorecard.add_row("Unhit Coverage Holes", f"[yellow]{report.unhit_bins_count} unhit bins identified[/yellow]")

    console.print()
    console.print(Panel(scorecard, title="[bold green] VERISIGHT PLAN METRICS SCORECARD [/bold green]", box=box.ROUNDED, border_style="green"))
    console.print()

    # Generated Artifacts Table
    art_table = Table(title=f"[bold cyan]Generated Plan Artifacts ({output_dir}/)[/bold cyan]", box=box.ROUNDED, show_lines=False)
    art_table.add_column("Artifact", style="bold white", width=26)
    art_table.add_column("Format / Purpose", style="dim white", width=52)

    art_table.add_row("verification_plan.html", "Interactive Web Dashboard (Coverage & Plan)")
    art_table.add_row("verification_plan.md", "Executive Engineering Verification Plan")
    art_table.add_row("traceability_matrix.csv", "Requirements Traceability Matrix (ISO 26262/DO-254)")
    art_table.add_row("coverage_model.sv", "Synthesized SystemVerilog Covergroups Package")
    art_table.add_row("dut_assertions.sv", "Synthesized SVA Formal Assertions Module")
    art_table.add_row("verification_plan.json", "Standardized Verification Schema")

    console.print(art_table)
    console.print()

    html_file = Path(output_dir) / "verification_plan.html"
    if html_file.exists():
        open_html = Confirm.ask("[bold]Open the interactive HTML Verification Plan in your browser?[/bold]", default=True)
        if open_html:
            if _open_html_in_browser(html_file):
                console.print(f"[green]✓ Opened in your browser: file://{html_file.resolve()}[/green]\n")
            else:
                console.print(f"[dim]You can open it at: file://{html_file.resolve()}[/dim]\n")


def run_debug_flow(
    provider: str,
    api_key: Optional[str],
    model_name: Optional[str],
    spec_path: Optional[str] = None,
    rtl_path: Optional[str] = None,
    tb_path: Optional[str] = None,
    log_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    airgap: bool = False,
    anonymize_rtl: bool = False,
    local_endpoint: str = "",
):
    """Execute the VeriSight Debug workflow."""
    console.print()
    console.print(
        Panel(
            "[bold white]Autonomous Root-Cause Analysis, Failure Localization & Bug Patching[/bold white]\n"
            "[dim]Analyzes simulation logs, parses VCD & AST, identifies root causes, and synthesizes verified patches.[/dim]",
            title="[bold cyan]🛠️  VERISIGHT DEBUG ENGINE[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()

    if not log_path:
        default_log = ""
        for cand_log in ["projects/ram/logs/sim.log", "examples/logs/sim.log"]:
            if Path(cand_log).exists():
                default_log = cand_log
                break
        log_path = _prompt_path("Simulation Log file (.log)", required=True, default=default_log)

    if not rtl_path:
        default_rtl = ""
        if log_path:
            lp = Path(log_path)
            for cand in [lp.parent.parent / "rtl", lp.parent / "rtl"]:
                if cand.exists() and cand.is_dir():
                    r_files = list(cand.glob("*.sv")) + list(cand.glob("*.v"))
                    if r_files:
                        default_rtl = str(r_files[0])
                        break
        if not default_rtl and Path("examples/rtl/alu.sv").exists():
            default_rtl = "examples/rtl/alu.sv"
        rtl_path = _prompt_path("RTL Source directory or file (.sv, .v)", required=False, default=default_rtl)

    if not tb_path:
        default_tb = ""
        if log_path:
            lp = Path(log_path)
            for cand in [lp.parent.parent / "tb", lp.parent / "tb"]:
                if cand.exists() and cand.is_dir():
                    t_files = list(cand.glob("*.sv")) + list(cand.glob("*.v"))
                    if t_files:
                        default_tb = str(t_files[0])
                        break
        if not default_tb and Path("examples/tb/alu_tb.sv").exists():
            default_tb = "examples/tb/alu_tb.sv"
        tb_path = _prompt_path("UVM Testbench directory or file (.sv)", required=False, default=default_tb)

    if not spec_path:
        default_spec = ""
        if log_path:
            lp = Path(log_path)
            for cand in [lp.parent.parent / "specs", lp.parent / "specs"]:
                if cand.exists() and cand.is_dir():
                    s_files = list(cand.glob("*.md")) + list(cand.glob("*.txt"))
                    if s_files:
                        default_spec = str(s_files[0])
                        break
        if not default_spec and Path("examples/specs/alu_spec.md").exists():
            default_spec = "examples/specs/alu_spec.md"
        spec_path = _prompt_path("Design Specification document (.md)", required=False, default=default_spec)

    if not output_dir:
        output_dir = Prompt.ask("[bold]Output directory for reports[/bold]", default="output/custom_debug").strip()

    # Pre-Flight Configuration Summary
    summary_table = Table(
        title="[bold cyan]Debug Pipeline Pre-Flight Configuration[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    summary_table.add_column("Parameter", style="cyan", width=24)
    summary_table.add_column("Configured Target", style="white", width=54)

    summary_table.add_row("Simulation Log", str(log_path) if log_path else "[dim]None[/dim]")
    summary_table.add_row("RTL Source", str(rtl_path) if rtl_path else "[dim]None[/dim]")
    summary_table.add_row("UVM Testbench", str(tb_path) if tb_path else "[dim]None[/dim]")
    summary_table.add_row("Design Spec", str(spec_path) if spec_path else "[dim]None[/dim]")
    summary_table.add_row("AI Provider / Model", f"{provider.capitalize()} ({model_name or 'default'})" if not airgap else "Sovereign Air-Gapped (Local)")
    summary_table.add_row("Output Directory", output_dir)

    console.print(summary_table)
    console.print()

    llm_kwargs: Dict[str, Any] = {
        "provider": provider,
        "airgap": airgap,
        "anonymize_rtl": anonymize_rtl,
        "local_endpoint": local_endpoint,
    }
    if api_key:
        llm_kwargs["api_key"] = api_key
    if model_name:
        llm_kwargs["model_name"] = model_name

    config = VeriSightConfig(
        llm=LLMConfig(**llm_kwargs),
        chroma=ChromaConfig(),
        pipeline=PipelineConfig(
            save_intermediates=True,
            enable_rag=bool(api_key and not airgap),
            output_dir=output_dir,
            verbose=False,
        ),
        xtracer=XTracerConfig(),
        fix=FixConfig(enabled=True),
        log_level="INFO",
    )

    with console.status("[bold green]Executing Multi-Agent RCA & Diagnostic Analysis...[/bold green]"):
        try:
            pipeline = VeriSightPipeline(config=config)
            report = pipeline.run(
                spec_path=spec_path,
                rtl_path=rtl_path,
                tb_path=tb_path,
                log_path=log_path,
            )
        except Exception as e:
            console.print(f"\n[bold red]Pipeline encountered an error:[/] {e}")
            return

    # Post-Execution Scorecard
    scorecard = Table(box=box.ROUNDED, show_header=False, border_style="green", expand=False)
    scorecard.add_column("Metric", style="bold cyan", width=24)
    scorecard.add_column("Value", style="bold white", width=54)

    scorecard.add_row("Diagnosis Status", "[bold green]✓ RCA Analysis Completed[/bold green]")
    scorecard.add_row("Classification", f"[bold yellow]{report.classification}[/bold yellow]")
    scorecard.add_row("Culprit Module", f"[bold white]{report.module}[/bold white]")
    scorecard.add_row("Failure Category", f"[bold white]{report.category}[/bold white]")
    scorecard.add_row("Identified Root Cause", f"[white]{report.root_cause}[/white]")

    console.print()
    console.print(Panel(scorecard, title="[bold green] VERISIGHT DEBUG RCA SCORECARD [/bold green]", box=box.ROUNDED, border_style="green"))
    console.print()

    # Generated Artifacts Table
    art_table = Table(title=f"[bold cyan]Generated Debug Artifacts ({output_dir}/)[/bold cyan]", box=box.ROUNDED, show_lines=False)
    art_table.add_column("Artifact", style="bold white", width=24)
    art_table.add_column("Format / Purpose", style="dim white", width=54)

    art_table.add_row("report.html", "Visual Interactive RCA Cockpit (Browser)")
    art_table.add_row("report.md", "Detailed Engineering Root-Cause Documentation")
    art_table.add_row("error.json", "Standardized Machine-Readable Error Schema")
    art_table.add_row("summary.txt", "Executive Summary for CI/CD Integration")
    art_table.add_row("fix/", "Automated RTL/TB Remediation Code Patch")

    console.print(art_table)
    console.print()

    html_file = Path(output_dir) / "report.html"
    if html_file.exists():
        open_html = Confirm.ask("[bold]Open the HTML report in your browser?[/bold]", default=True)
        if open_html:
            if _open_html_in_browser(html_file):
                console.print(f"[green]✓ Opened in your browser: file://{html_file.resolve()}[/green]\n")
            else:
                console.print(f"[dim]You can open it at: file://{html_file.resolve()}[/dim]\n")


def run_sim_flow(
    provider: str,
    api_key: Optional[str],
    model_name: Optional[str],
    rtl_path: Optional[str] = None,
    tb_path: Optional[str] = None,
    spec_path: Optional[str] = None,
    simulator: Optional[str] = None,
    output_dir: Optional[str] = None,
    airgap: bool = False,
    anonymize_rtl: bool = False,
    local_endpoint: str = "",
):
    """Execute the VeriSight One-Click Closed-Loop Simulation Runner."""
    from verisight.tools.sim_runner import execute_closed_loop_flow, find_best_simulator

    console.print("\n[bold cyan]🚀 One-Click Closed-Loop Simulation Runner[/bold cyan]")
    console.print("[dim]Simulate RTL + TB -> Capture Log, VCD & Coverage -> Auto-trigger RCA & Plan[/dim]\n")

    detected_sim = find_best_simulator()
    console.print(f"  [dim]Auto-detected system simulator:[/] [bold green]{detected_sim or 'None (fallback hints available)'}[/bold green]\n")

    if not rtl_path:
        rtl_path = _prompt_path("RTL Source file or directory (.sv, .v)", required=True, default="examples/rtl/alu.sv")
    if not tb_path:
        tb_path = _prompt_path("Testbench file or directory (.sv, .v)", required=True, default="examples/tb/alu_tb.sv")
    if not spec_path:
        spec_path = _prompt_path("Design Specification document (.md) [optional]", required=False, default="examples/specs/alu_spec.md")

    if not simulator:
        sim_choices = ["auto", "iverilog", "verilator", "questa", "modelsim", "vcs"]
        simulator = Prompt.ask(
            "[bold]Select EDA Simulator[/bold]",
            choices=sim_choices,
            default="auto" if detected_sim else "iverilog",
        )

    if not output_dir:
        output_dir = Prompt.ask("[bold]Output root directory[/bold]", default="output/closed_loop").strip()

    console.print("\n[bold cyan]⚡ Launching Closed-Loop Flow...[/bold cyan]\n")
    try:
        results = execute_closed_loop_flow(
            rtl_path=rtl_path,
            tb_path=tb_path,
            spec_path=spec_path if spec_path else None,
            output_dir=output_dir,
            simulator=simulator,
            airgap=airgap,
            anonymize_rtl=anonymize_rtl,
            api_key=api_key,
            provider=provider,
            model_name=model_name,
            local_endpoint=local_endpoint,
            launch_browser=False,
        )

        sim_res = results.get("sim")
        console.print("\n" + "=" * 62)
        console.print("[bold green]🎉 Closed-Loop Execution Completed![/bold green]")
        console.print("=" * 62)
        if sim_res:
            status_tag = "[bold green]PASS[/bold green]" if sim_res.success else "[bold red]FAIL (Anomalies Found)[/bold red]"
            console.print(f"  [bold]Sim Status:[/]     {status_tag}")
            console.print(f"  [bold]Simulator:[/]      {sim_res.simulator}")
            console.print(f"  [bold]Sim Errors:[/]     {sim_res.error_count} error(s)")
            console.print(f"  [bold]Sim Warnings:[/]   {sim_res.warning_count} warning(s)")
            console.print(f"  [bold]VCD Trace:[/]      {sim_res.vcd_path or 'None'}")
            console.print(f"  [bold]Log File:[/]       {sim_res.log_path}")

        rca_res = results.get("rca")
        if rca_res:
            console.print(f"\n  [bold cyan]RCA Diagnosis:[/]   {rca_res.classification}")
            console.print(f"  [bold]Root Cause:[/]      {rca_res.root_cause}")

        dashboards = results.get("dashboards", {})
        console.print(f"\n  [bold cyan]Interactive Cockpits & Dashboards:[/bold cyan]")
        if "debug_report_html" in dashboards:
            console.print(f"    • [white]Debug Waveform Cockpit:[/] {dashboards['debug_report_html']}")
        if "plan_cockpit_html" in dashboards:
            console.print(f"    • [white]Coverage Closure Plan:[/]  {dashboards['plan_cockpit_html']}")

        open_choice = Confirm.ask("\n[bold]Open dashboards in your browser now?[/bold]", default=True)
        if open_choice:
            for k, p in dashboards.items():
                p_path = Path(p)
                if p_path.exists():
                    _open_html_in_browser(p_path)
                    console.print(f"[green]✓ Opened: file://{p_path.resolve()}[/green]")

    except Exception as e:
        console.print(f"\n[bold red]Closed-Loop Execution failed:[/] {e}")


def run_edaplayground_export_flow(
    rtl_path: Optional[str] = None,
    tb_path: Optional[str] = None,
    output_dir: Optional[str] = None,
):
    """Interactive guided flow to export RTL and Testbench to EDA Playground."""
    from verisight.tools.eda_playground_exporter import export_to_edaplayground

    console.print("\n[bold cyan]📦 VeriSight — EDA Playground Cloud Bundle Exporter[/bold cyan]")
    console.print("[dim]Package RTL and Testbench for 1-click cloud simulation with Siemens Questa, Synopsys VCS, or Riviera-PRO.[/dim]\n")

    if not rtl_path:
        rtl_path = _prompt_path("RTL Source file or directory (.sv, .v)", required=True, default="examples/rtl/alu.sv")
    if not tb_path:
        tb_path = _prompt_path("Testbench file or directory (.sv, .v)", required=True, default="examples/tb/alu_tb.sv")
    if not output_dir:
        output_dir = Prompt.ask("[bold]Output bundle directory[/bold]", default="output/edaplayground").strip()

    preferred_sim = Prompt.ask(
        "[bold]Target Simulator for preconfigured flags[/bold]",
        choices=["questa", "vcs", "riviera", "xcelium", "verilator"],
        default="questa",
    )
    anonymize = Confirm.ask(
        "[bold]Enable RTL Token Masking (scrub proprietary identifiers before cloud upload)?[/bold]",
        default=False,
    )

    try:
        res = export_to_edaplayground(
            rtl_path=rtl_path,
            tb_path=tb_path,
            output_dir=output_dir,
            preferred_simulator=preferred_sim,
            anonymize_rtl=anonymize,
        )

        console.print("\n[bold green]✓ EDA Playground bundle created successfully![/bold green]")
        console.print(f"  • [cyan]design.sv:[/]             {res['design_sv']}")
        console.print(f"  • [cyan]testbench.sv:[/]          {res['testbench_sv']}")
        console.print(f"  • [cyan]Launch Studio (HTML):[/] {res['launch_html']}")
        console.print(f"  • [cyan]Auto-Injector Script:[/] {res.get('userscript_js', '')}")
        console.print(f"  • [cyan]Configuration (JSON):[/] {res['config_json']}")
        console.print(f"  • [cyan]User Guide (MD):[/]      {res['readme_md']}\n")

        console.print("[bold yellow]⚡ 1-Click Auto-Injector Included:[/] Drag the bookmarklet from Launch Studio to populate both files and flags into EDA Playground in 1 click!\n")

        open_dash = Confirm.ask("[bold]Open EDA Playground Launch Studio in browser now?[/bold]", default=True)
        if open_dash:
            _open_html_in_browser(Path(res["launch_html"]))
            console.print(f"[green]✓ Opened: file://{Path(res['launch_html']).resolve()}[/green]")
            console.print("[dim]Tip: Drag the '⚡ Inject to EDA Playground' bookmarklet to your browser bar, then click it on EDA Playground to load all files![/dim]")

    except Exception as e:
        console.print(f"\n[bold red]EDA Playground Export failed:[/] {e}")


def run_uvm_flow(
    rtl_path: Optional[str] = None,
    spec_path: Optional[str] = None,
    output_dir: Optional[str] = None,
):
    """Run autonomous UVM Testbench Environment Generator (XcelUVM Architect)."""
    console.print()
    console.print(
        Panel(
            "[bold white]Autonomous Production-Grade UVM 1.2 Testbench Environment Synthesis[/bold white]\n"
            "[dim]Parses RTL AST, detects protocol compliance, and synthesizes complete UVM components,\n"
            "scoreboards, reference models, functional coverage, and Questa/VCS simulation harnesses.[/dim]",
            title="[bold cyan]🏗️  XCELUVM ARCHITECT — UVM TESTBENCH GENERATOR[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()

    default_rtl = "projects/apb/rtl/apb_slave.sv" if Path("projects/apb/rtl/apb_slave.sv").exists() else "examples/rtl/alu.sv"
    if not rtl_path:
        rtl_path = _prompt_path(
            "Path to RTL source file or directory (.sv, .v)",
            required=False,
            default=default_rtl,
        )

    default_spec = "projects/apb/specs/apb_spec.md" if Path("projects/apb/specs/apb_spec.md").exists() else ""
    if not spec_path:
        spec_path = _prompt_path(
            "Path to specification file (optional, press Enter to infer from RTL)",
            required=False,
            default=default_spec,
        )

    if not output_dir:
        output_dir = Prompt.ask(
            "[bold]Output directory for generated UVM environment[/bold]",
            default="output/uvm_environment",
        ).strip()

    # Pre-Flight Configuration Summary
    summary_table = Table(
        title="[bold cyan]XcelUVM Architect Pre-Flight Configuration[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    summary_table.add_column("Parameter", style="cyan", width=24)
    summary_table.add_column("Configured Target", style="white", width=54)

    summary_table.add_row("Target RTL Design", str(rtl_path) if rtl_path else "[dim]Auto-synthesized[/dim]")
    summary_table.add_row("Design Specification", str(spec_path) if spec_path else "[dim]Inferred from RTL & Protocol[/dim]")
    summary_table.add_row("Output Directory", output_dir)
    summary_table.add_row("Methodology Standard", "IEEE 1800.2 UVM 1.2 Production Testbench")

    console.print(summary_table)
    console.print()

    from verisight.uvm.uvm_architect import UVMArchitect

    with console.status("[bold green]Synthesizing complete UVM 1.2 Testbench Environment...[/bold green]"):
        try:
            architect = UVMArchitect(output_dir=output_dir)
            res = architect.generate(
                rtl_path=str(rtl_path) if rtl_path else None,
                spec_path=str(spec_path) if spec_path else None,
                output_dir=output_dir,
            )
        except Exception as e:
            console.print(f"\n[bold red]UVM Synthesis failed:[/] {e}")
            return

    # Post-Execution Scorecard
    scorecard = Table(box=box.ROUNDED, show_header=False, border_style="green", expand=False)
    scorecard.add_column("Property", style="bold cyan", width=24)
    scorecard.add_column("Value", style="bold white", width=54)

    scorecard.add_row("Synthesis Status", "[bold green]✓ Complete UVM Environment Synthesized[/bold green]")
    scorecard.add_row("Target Design", f"[bold white]{res.design_name.upper()}[/bold white]")
    scorecard.add_row("Detected Protocol", f"[bold cyan]{res.protocol_detected.upper()}[/bold cyan]")
    scorecard.add_row("DUT Ports Mapped", f"[bold white]{res.inputs_count} inputs, {res.outputs_count} outputs[/bold white]")
    scorecard.add_row("Output Directory", f"[cyan]{res.output_dir}[/cyan]")
    scorecard.add_row("Generated Components", f"[bold green]{len(res.files_generated)} components[/bold green]")

    console.print()
    console.print(Panel(scorecard, title="[bold green] XCELUVM SYNTHESIS SCORECARD [/bold green]", box=box.ROUNDED, border_style="green"))
    console.print()

    # Formatted component table
    comp_table = Table(
        title=f"[bold cyan]Synthesized UVM Testbench Suite ({output_dir}/)[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    comp_table.add_column("File / Component", style="bold white", width=30)
    comp_table.add_column("UVM Class / Role", style="dim white", width=48)

    for f in res.files_generated:
        f_name = Path(f).name
        role = "UVM Component"
        if "_if.sv" in f_name:
            role = "SystemVerilog Interface & Modports"
        elif "_seq_item.sv" in f_name:
            role = "uvm_sequence_item (Constrained Transactions)"
        elif "_sequencer.sv" in f_name:
            role = "uvm_sequencer typedef"
        elif "_driver.sv" in f_name:
            role = "uvm_driver (Pin-level Protocol Driving)"
        elif "_monitor.sv" in f_name:
            role = "uvm_monitor (Protocol Sampling & Analysis Port)"
        elif "_agent.sv" in f_name:
            role = "uvm_agent (Active/Passive Configurable Agent)"
        elif "_ref_model.sv" in f_name or "_reference_model.sv" in f_name:
            role = "Behavioral Golden Reference Model"
        elif "_scoreboard.sv" in f_name:
            role = "uvm_scoreboard (In-order Checking & Error Counting)"
        elif "_coverage.sv" in f_name:
            role = "uvm_subscriber (Protocol Functional Coverage)"
        elif "_seq.sv" in f_name or "_sequence.sv" in f_name:
            role = "uvm_sequence (Sanity, Random & Corner-Case Sequences)"
        elif "_env.sv" in f_name:
            role = "uvm_env (Top Environment Topology)"
        elif "_test.sv" in f_name:
            role = "uvm_test (Base Test & Directed/Random Tests)"
        elif "_pkg.sv" in f_name:
            role = "SystemVerilog Package (`include wrapper)"
        elif "_tb_top.sv" in f_name:
            role = "Testbench Top Module (Clock/Reset Gen & DUT Instantiation)"
        elif "run.do" in f_name:
            role = "Siemens Questa / ModelSim Batch Simulation Script"
        elif "Makefile" in f_name:
            role = "Synopsys VCS / Questa Automation Makefile"

        comp_table.add_row(f_name, role)

    console.print(comp_table)
    console.print()

    # Next steps box
    sim_guide = (
        "[bold white]To run the synthesized UVM Testbench:[/bold white]\n"
        f"  [cyan]cd {output_dir}[/cyan]\n"
        "  • [bold]Siemens Questa / ModelSim:[/] [white]vsim -c -do run.do[/white]\n"
        "  • [bold]Synopsys VCS:[/]              [white]make run_vcs[/white]\n"
        "  • [bold]Cadence Xcelium:[/]           [white]make run_xcelium[/white]"
    )
    console.print(Panel(sim_guide, title="[bold cyan] Simulation Quick-Start [/bold cyan]", box=box.ROUNDED, border_style="cyan"))
    console.print()


def run_spec_driven_tb_flow(
    rtl_path: Optional[str] = None,
    spec_path: Optional[str] = None,
    output_dir: Optional[str] = None,
):
    """Run Spec-Driven Testbench Generation Agent (Workflow 4)."""
    console.print()
    console.print(
        Panel(
            "[bold white]Spec-Driven Testbench Generation Agent (Workflow 4)[/bold white]\n"
            "[dim]Synthesizes complete, specification-grounded SystemVerilog UVM 1.2 testbenches.\n"
            "Enforces that the Specification is the functional source of truth: reference models and\n"
            "scoreboards independently discover RTL defects rather than reproducing them.[/dim]",
            title="[bold magenta]🎯 VERISIGHT TESTBENCH — SPEC-DRIVEN UVM SYNTHESIS[/bold magenta]",
            box=box.ROUNDED,
            border_style="magenta",
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()

    default_rtl = "projects/ram/rtl/ram_rtl.sv" if Path("projects/ram/rtl/ram_rtl.sv").exists() else "examples/rtl/alu.sv"
    if not rtl_path:
        rtl_path = _prompt_path(
            "Path to RTL source file (.sv, .v)",
            required=True,
            default=default_rtl,
        )

    default_spec = "projects/ram/specs/spec.md" if Path("projects/ram/specs/spec.md").exists() else "examples/specs/alu_spec.md"
    if not spec_path:
        spec_path = _prompt_path(
            "Path to Design Specification file (.md, .txt)",
            required=True,
            default=default_spec,
        )

    if not output_dir:
        output_dir = Prompt.ask(
            "[bold]Output directory for generated UVM environment[/bold]",
            default="output/spec_driven_uvm",
        ).strip()

    from verisight.agents.spec_driven_tb_agent import SpecDrivenTestbenchAgent

    with console.status("[bold magenta]Running Spec-Driven Testbench Generation Agent...[/bold magenta]"):
        try:
            agent = SpecDrivenTestbenchAgent(output_dir=output_dir)
            res = agent.generate_testbench(
                spec_path=str(spec_path),
                rtl_path=str(rtl_path),
                output_dir=output_dir,
                run_sim=True,
            )
        except Exception as e:
            console.print(f"\n[bold red]Spec-Driven Testbench Generation failed:[/] {e}")
            return

    # Scorecard
    scorecard = Table(box=box.ROUNDED, show_header=False, border_style="magenta", expand=False)
    scorecard.add_column("Property", style="bold magenta", width=28)
    scorecard.add_column("Value", style="bold white", width=54)

    scorecard.add_row("Agent Workflow", "[bold magenta]Workflow 4: Spec-Driven Testbench[/bold magenta]")
    scorecard.add_row("Target Design", f"[bold white]{res.design_name.upper()}[/bold white]")
    scorecard.add_row("Specification Title", f"[cyan]{res.mental_model.spec_title}[/cyan]")
    scorecard.add_row("Requirements Grounded", f"[bold green]{len(res.requirements)} atomic REQ items[/bold green]")
    scorecard.add_row("Intent vs. RTL Checks", f"[bold yellow]{len(res.mental_model.intent_vs_implementation)} checkpoints[/bold yellow]")
    scorecard.add_row("Static Syntax Review", "[bold green]✓ Passed (pyslang IEEE 1800)[/bold green]" if res.static_validation.syntax_clean else "[bold red]Diagnostics Logged[/bold red]")
    if res.simulation_validation:
        sim_stat = "[bold yellow]RTL Defect Successfully Exposed![/bold yellow]" if res.simulation_validation.mismatches_detected > 0 else "[bold green]Simulation Passed Cleanly[/bold green]"
        scorecard.add_row("Simulation Status", sim_stat)
        scorecard.add_row("Scoreboard Findings", f"{res.simulation_validation.mismatches_detected} mismatches against spec")

    console.print()
    console.print(Panel(scorecard, title="[bold magenta] SPEC-DRIVEN VERIFICATION SCORECARD [/bold magenta]", box=box.ROUNDED, border_style="magenta"))
    console.print()

    # Formatted component table
    comp_table = Table(
        title=f"[bold magenta]Synthesized Spec-Driven UVM Suite ({output_dir}/)[/bold magenta]",
        box=box.ROUNDED,
        header_style="bold magenta",
        show_lines=False,
    )
    comp_table.add_column("File / Component", style="bold white", width=32)
    comp_table.add_column("UVM Class / Role", style="dim white", width=46)

    for comp in res.uvm_components:
        comp_table.add_row(comp.file_name, comp.role)

    console.print(comp_table)
    console.print()


def run_wizard():
    """Execute the unified interactive guided setup wizard."""
    try:
        _print_welcome_banner()

        table = Table(
            title="[bold cyan]Step 1: Select Autonomous Verification Engine[/bold cyan]",
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=True,
        )
        table.add_column("Opt", justify="center", style="bold yellow", width=5)
        table.add_column("Autonomous Engine", style="bold white", width=25)
        table.add_column("Primary Verification Capability", style="white")

        table.add_row(
            "1",
            "🛠️  VeriSight Debug",
            "Autonomous Root-Cause Analysis, Failure Localization & Code Patching",
        )
        table.add_row(
            "2",
            "📋 VeriSight Plan",
            "Test Plan Generation, Protocol Coverage Models & SVA Assertion Suites",
        )
        table.add_row(
            "3",
            "🏗️  XcelUVM Architect",
            "Autonomous Full Production UVM 1.2 Testbench Environment Synthesis",
        )
        table.add_row(
            "4",
            "🎯 VeriSight TestBench",
            "Spec-Driven UVM Testbench Synthesis with Specification-Grounded Reference Models",
        )
        table.add_row(
            "5",
            "🚪 Exit",
            "Quit VeriSight Launcher",
        )

        console.print(table)
        console.print()

        workflow = Prompt.ask(
            "[bold cyan]Select an option[/bold cyan]",
            choices=["1", "2", "3", "4", "5"],
            default="1",
        )

        if workflow == "5":
            console.print("\n[dim]Exiting VeriSight. Goodbye![/dim]\n")
            sys.exit(0)

        if workflow == "4":
            run_spec_driven_tb_flow()
            return

        if workflow == "3":
            run_uvm_flow()
            return

        console.print("\n[bold cyan]Step 2: LLM Configuration[/bold cyan]")
        provider, api_key, model_name, airgap, anonymize_rtl, local_endpoint = _configure_api_key()

        if workflow == "1":
            run_debug_flow(
                provider, api_key, model_name,
                airgap=airgap, anonymize_rtl=anonymize_rtl, local_endpoint=local_endpoint,
            )

        elif workflow == "2":
            run_plan_flow(
                provider, api_key, model_name,
                airgap=airgap, anonymize_rtl=anonymize_rtl, local_endpoint=local_endpoint,
            )

    except KeyboardInterrupt:
        console.print("\n\n[dim]Launcher interrupted by user. Exiting VeriSight.[/dim]\n")
        sys.exit(0)
