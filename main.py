#!/usr/bin/env python3
"""
VeriSight CLI — AI-Powered RTL/UVM Debugging Framework

Usage:
    python main.py --spec examples/specs/alu_spec.md \\
                   --rtl examples/rtl/ \\
                   --tb examples/tb/ \\
                   --log examples/logs/sim.log \\
                   --output output/
"""

import argparse
import os
import sys
from pathlib import Path

from verisight.config import VeriSightConfig, LLMConfig, ChromaConfig, PipelineConfig, XTracerConfig, FixConfig
from verisight.orchestrator import VeriSightPipeline
from verisight.tools import sim_runner
from verisight.tools.sim_runner import SimulatorNotFoundError, SimulationError
from verisight.utils.logger import setup_logging, console


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="verisight",
        description="VeriSight — AI-Powered RTL/UVM Debugging Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline with all inputs
  python main.py --spec examples/specs/alu_spec.md \\
                 --rtl examples/rtl/ \\
                 --tb examples/tb/ \\
                 --log examples/logs/sim.log

  # Without LLM (deterministic analysis only)
  python main.py --rtl examples/rtl/ \\
                 --log examples/logs/sim.log \\
                 --no-rag

  # Verbose mode
  python main.py --spec examples/specs/alu_spec.md \\
                 --rtl examples/rtl/ \\
                 --tb examples/tb/ \\
                 --log examples/logs/sim.log \\
                 --verbose
        """,
    )

    # Input files
    parser.add_argument(
        "--spec",
        type=str,
        help="Path to design specification (.md file)",
    )
    parser.add_argument(
        "--rtl",
        type=str,
        help="Path to RTL source file or directory",
    )
    parser.add_argument(
        "--tb",
        type=str,
        help="Path to UVM testbench source file or directory",
    )
    parser.add_argument(
        "--log",
        type=str,
        help="Path to simulation log file",
    )
    parser.add_argument(
        "--coverage",
        type=str,
        help="Path to coverage report file (optional)",
    )

    # Output
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output",
        help="Output directory for reports (default: output/)",
    )

    # Options
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable RAG knowledge base",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "--no-intermediates",
        action="store_true",
        help="Don't save intermediate JSON artifacts",
    )
    parser.add_argument(
        "--no-fix",
        action="store_true",
        help="Disable automated fix generation (Agent 5)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help=(
            "Minimum evidence-weighted confidence (0.0–1.0) required before Agent 5 "
            "emits a fix. Default: 0.70. Fixes below this threshold are declined."
        ),
    )

    # Simulation (--simulate) — all optional
    sim_group = parser.add_argument_group("Simulation")
    sim_group.add_argument(
        "--simulate",
        action="store_true",
        help="Run the simulation internally (via iverilog or verilator) instead of "
             "requiring a pre-existing --log/--vcd. Requires --rtl and --tb",
    )
    sim_group.add_argument(
        "--simulator",
        type=str,
        choices=["iverilog", "verilator"],
        default="iverilog",
        help="Simulator backend for --simulate (default: iverilog — best UVM-lite "
             "compatibility, size, and ease of use; verilator is experimental)",
    )
    sim_group.add_argument(
        "--sim-top",
        type=str,
        help="Top-level module to simulate (auto-detected if omitted)",
    )
    sim_group.add_argument(
        "--uvm-home",
        type=str,
        help="Path to a UVM library for --simulate (else VERISIGHT_UVM_HOME env var)",
    )
    sim_group.add_argument(
        "--sim-timeout",
        type=int,
        default=300,
        help="Simulation timeout in seconds (default: 300)",
    )

    # X-Propagation Analysis (x-tracer) — all optional
    xtrace_group = parser.add_argument_group("X-Propagation Analysis (x-tracer)")
    xtrace_group.add_argument(
        "--xtrace",
        action="store_true",
        help="Enable real X-propagation root-cause tracing via x-tracer "
             "(requires yosys or --netlist, and a --vcd waveform)",
    )
    xtrace_group.add_argument(
        "--netlist",
        action="append",
        help="Path to a pre-synthesized gate-level netlist (.v). Repeatable. "
             "If omitted, VeriSight synthesizes one from --rtl using yosys",
    )
    xtrace_group.add_argument(
        "--top",
        type=str,
        help="Top module name for synthesis/x-tracer hierarchy (auto-detected if omitted)",
    )
    xtrace_group.add_argument(
        "--vcd",
        type=str,
        help="Path to simulation waveform (VCD) for x-tracer analysis",
    )
    xtrace_group.add_argument(
        "--xtrace-signal",
        type=str,
        help="Explicit signal path to trace (e.g. tb.dut.y[0]), overrides "
             "auto-derivation from the sim log. Must be given with --xtrace-time",
    )
    xtrace_group.add_argument(
        "--xtrace-time",
        type=int,
        help="Explicit query time in picoseconds, overrides auto-derivation. "
             "Must be given with --xtrace-signal",
    )
    xtrace_group.add_argument(
        "--xtracer-path",
        type=str,
        help="Path to x_tracer.py (else VERISIGHT_XTRACER_PATH env var or auto-detected)",
    )
    xtrace_group.add_argument(
        "--xtrace-max-depth",
        type=int,
        default=100,
        help="Max trace depth for x-tracer (default: 100)",
    )

    # LLM options
    parser.add_argument(
        "--provider",
        type=str,
        choices=["gemini", "anthropic", "claude"],
        help="LLM provider (default: gemini or auto-detected from environment)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="LLM API key (overrides GEMINI_API_KEY or ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="LLM model name (default: gemini-2.0-flash or claude-sonnet-4-20250514)",
    )

    return parser.parse_args()


def validate_inputs(args) -> bool:
    """Validate that required inputs exist."""
    valid = True

    if args.spec and not Path(args.spec).exists():
        console.print(f"[red]Error:[/red] Spec file not found: {args.spec}")
        valid = False

    if args.rtl and not Path(args.rtl).exists():
        console.print(f"[red]Error:[/red] RTL path not found: {args.rtl}")
        valid = False

    if args.tb and not Path(args.tb).exists():
        console.print(f"[red]Error:[/red] TB path not found: {args.tb}")
        valid = False

    if args.log and not args.simulate and not Path(args.log).exists():
        console.print(f"[red]Error:[/red] Log file not found: {args.log}")
        valid = False

    for netlist in (args.netlist or []):
        if not Path(netlist).exists():
            console.print(f"[red]Error:[/red] Netlist file not found: {netlist}")
            valid = False

    if args.vcd and not Path(args.vcd).exists():
        console.print(f"[red]Error:[/red] VCD file not found: {args.vcd}")
        valid = False

    if bool(args.xtrace_signal) != bool(args.xtrace_time is not None):
        console.print(
            "[red]Error:[/red] --xtrace-signal and --xtrace-time must be given together"
        )
        valid = False

    if args.simulate:
        if not (args.rtl and args.tb):
            console.print("[red]Error:[/red] --simulate requires both --rtl and --tb")
            valid = False
        if args.log:
            console.print(
                "[yellow]Warning:[/yellow] --log is ignored with --simulate — "
                "the freshly generated simulation log will be used instead"
            )
    elif not any([args.spec, args.rtl, args.tb, args.log]):
        console.print("[red]Error:[/red] At least one input must be provided")
        console.print("  Use --spec, --rtl, --tb, or --log")
        valid = False

    return valid


def main():
    """Main entry point for VeriSight CLI."""
    args = parse_args()

    # Validate inputs
    if not validate_inputs(args):
        sys.exit(1)

    # Normalize output dir (drop any trailing separators so display/paths
    # don't end up with a doubled slash, e.g. "output//").
    args.output = args.output.rstrip("/\\") or "."

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(level=log_level)

    # ─── Optional: run the simulation ourselves (--simulate) ──────────
    # Always produces a fresh log + VCD, which we parse into
    # knowledge.vcd for Agent 2/3 debugging evidence regardless of
    # whether --xtrace was also passed. We only feed the VCD into the
    # x-tracer path (which triggers yosys netlist synthesis) when the
    # user explicitly opted into that via --xtrace/--netlist — --simulate
    # and --xtrace are independent, composable flags.
    vcd_for_knowledge = args.vcd
    if args.simulate:
        console.print(f"[dim]Simulator:[/]  {args.simulator}")
        console.print("[dim]Running simulation...[/]\n")
        try:
            sim_result = sim_runner.run_simulation(
                rtl_path=args.rtl,
                tb_path=args.tb,
                simulator=args.simulator,
                top_module=args.sim_top or args.top or "",
                uvm_home=args.uvm_home or os.getenv("VERISIGHT_UVM_HOME", ""),
                timeout_s=args.sim_timeout,
                output_dir=Path(args.output) / "sim",
            )
        except (SimulatorNotFoundError, SimulationError) as e:
            console.print(f"[bold red]Simulation failed:[/] {e}")
            sys.exit(1)

        args.log = str(sim_result.log_path)
        vcd_for_knowledge = args.vcd or str(sim_result.vcd_path)
        if args.xtrace or args.netlist:
            args.vcd = args.vcd or str(sim_result.vcd_path)
        if not args.top and not args.sim_top:
            args.top = sim_result.top_module

        console.print(
            f"[dim]Simulation complete[/] (top={sim_result.top_module}, "
            f"exit={sim_result.returncode})\n"
            f"  log: {sim_result.log_path}\n"
            f"  vcd: {sim_result.vcd_path}\n"
        )

    # Build configuration
    kwargs = {}
    if args.provider:
        kwargs["provider"] = args.provider
    if args.api_key:
        kwargs["api_key"] = args.api_key
    if args.model:
        kwargs["model_name"] = args.model

    llm_config = LLMConfig(**kwargs)

    xtracer_config = XTracerConfig(
        enabled=bool(args.xtrace or args.vcd or args.netlist),
        netlist_paths=args.netlist or [],
        top_module=args.top or "",
        vcd_path=args.vcd or "",
        signal=args.xtrace_signal or "",
        time_ps=args.xtrace_time,
        xtracer_path=args.xtracer_path or "",
        max_depth=args.xtrace_max_depth,
    )

    config = VeriSightConfig(
        llm=llm_config,
        chroma=ChromaConfig(),
        pipeline=PipelineConfig(
            save_intermediates=not args.no_intermediates,
            enable_rag=not args.no_rag,
            output_dir=args.output,
            verbose=args.verbose,
        ),
        xtracer=xtracer_config,
        fix=FixConfig(
            enabled=not args.no_fix,
            min_confidence=(
                args.min_confidence
                if args.min_confidence is not None
                else 0.70
            ),
        ),
        log_level=log_level,
    )

    # Print banner
    console.print("\n[bold cyan]╔══════════════════════════════════════════════════════════╗[/]")
    console.print("[bold cyan]║[/]  [bold white]VeriSight[/] — AI-Powered RTL/UVM Debugging Framework     [bold cyan]║[/]")
    console.print("[bold cyan]╚══════════════════════════════════════════════════════════╝[/]\n")

    console.print(f"  [dim]Provider:[/]  {config.llm.provider}")
    console.print(f"  [dim]Model:[/]     {config.llm.model_name}")
    console.print(f"  [dim]Spec:[/]     {args.spec or 'not provided'}")
    console.print(f"  [dim]RTL:[/]      {args.rtl or 'not provided'}")
    console.print(f"  [dim]TB:[/]       {args.tb or 'not provided'}")
    console.print(f"  [dim]Log:[/]      {args.log or 'not provided'}")
    console.print(f"  [dim]Coverage:[/] {args.coverage or 'not provided'}")
    console.print(f"  [dim]VCD:[/]      {vcd_for_knowledge or 'not provided'}")
    console.print(f"  [dim]Output:[/]   {args.output}")
    console.print(f"  [dim]RAG:[/]      {'enabled' if not args.no_rag else 'disabled'}")
    console.print(f"  [dim]Simulate:[/] {'enabled (' + args.simulator + ')' if args.simulate else 'disabled'}")
    console.print(f"  [dim]X-Tracer:[/] {'enabled' if xtracer_config.enabled else 'disabled'}")
    console.print()

    # Execute pipeline
    try:
        pipeline = VeriSightPipeline(config=config)
        report = pipeline.run(
            spec_path=args.spec,
            rtl_path=args.rtl,
            tb_path=args.tb,
            log_path=args.log,
            coverage_path=args.coverage,
            vcd_path=vcd_for_knowledge,
        )

        # Print final summary
        console.print()
        console.print("[bold green]Pipeline completed successfully![/]")
        console.print()
        console.print(f"  [bold]Classification:[/] {report.classification}")
        console.print(f"  [bold]Confidence:[/]     {report.confidence}%")
        console.print(f"  [bold]Root Cause:[/]     {report.root_cause[:80]}")
        console.print(f"  [bold]Module:[/]         {report.module}")
        console.print(f"  [bold]Category:[/]       {report.category}")
        console.print()
        console.print(f"  Reports saved to: [bold]{args.output}/[/]")
        console.print(f"    • error.json")
        console.print(f"    • report.md")
        console.print(f"    • report.html")
        console.print(f"    • summary.txt")
        console.print()

    except Exception as e:
        console.print(f"\n[bold red]Pipeline failed:[/] {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
