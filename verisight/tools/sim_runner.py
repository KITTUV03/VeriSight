"""
Simulation runner — the optional --simulate flow.

Runs an actual UVM/RTL simulation to produce a sim log and a VCD waveform,
so VeriSight can analyze a live design instead of requiring pre-existing
log/VCD artifacts. Entirely optional: when --simulate isn't passed, nothing
in this module is touched and VeriSight behaves exactly as before.

Simulator choice: Icarus Verilog (iverilog/vvp) is the default and
recommended backend — it is lightweight (a single small package via the
system package manager), has a trivial two-step compile+run workflow, and
makes VCD dumping trivial via an auto-injected $dumpfile/$dumpvars wrapper
that needs no changes to the user's testbench. It has decent, actively
maintained UVM-lite support for class-based, non-timing-critical
testbenches, which covers this project's target use case. Verilator is
offered as an alternate backend for users who already have it set up and
need simulation speed on large designs, at the cost of a heavier toolchain
and less mature SystemVerilog class/UVM support — pick it explicitly via
--simulator verilator.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from verisight.utils.file_utils import discover_files, RTL_EXTENSIONS, TB_EXTENSIONS
from verisight.utils.logger import get_logger

logger = get_logger("sim_runner")

SIM_INSTALL_HINTS = {
    "iverilog": (
        "iverilog/vvp were not found on PATH. Install Icarus Verilog:\n"
        "  Debian/Ubuntu: sudo apt install iverilog\n"
        "  macOS:         brew install icarus-verilog\n"
        "Or build from source: https://github.com/steveicarus/iverilog"
    ),
    "verilator": (
        "verilator was not found on PATH. Install it with:\n"
        "  Debian/Ubuntu: sudo apt install verilator\n"
        "  macOS:         brew install verilator\n"
        "Or build from source: https://github.com/verilator/verilator"
    ),
}

_NOT_MODULES = {
    "module", "function", "task", "if", "else", "case", "for",
    "while", "assign", "always", "initial", "begin", "end",
    "input", "output", "inout", "wire", "reg", "logic",
    "parameter", "localparam", "generate", "integer",
    "always_ff", "always_comb", "always_latch", "interface", "package",
}

_MODULE_DECL = re.compile(r"\bmodule\s+(\w+)\b")
_INSTANTIATION = re.compile(r"\b(\w+)\s+(?:#\s*\([^)]*\)\s+)?\w+\s*\(")


class SimulatorNotFoundError(RuntimeError):
    """Raised when the requested simulator binary cannot be located."""
    pass


class SimulationError(RuntimeError):
    """
    Raised for simulation *infrastructure* failures (missing tool, compile
    error, timeout) — never for a simulation that ran to completion but
    whose DUT/testbench reported failures. Those still produce a usable log.
    """
    pass


@dataclass
class SimResult:
    log_path: Path
    vcd_path: Path
    returncode: int
    simulator: str
    top_module: str


def find_simulator(name: str) -> str:
    """Resolve the primary binary for a simulator ('iverilog' or 'verilator')."""
    binary = shutil.which(name)
    if not binary:
        raise SimulatorNotFoundError(SIM_INSTALL_HINTS.get(name, f"{name} not found on PATH"))
    return binary


def _guess_top_module(files: List[Path]) -> str:
    """
    Best-effort guess at the simulation top module: the module declared in
    these sources that is never instantiated by any other module in the set
    (mirrors the same heuristic used by rtl_parser.py's top-module detection).
    """
    declared: List[str] = []
    instantiated = set()

    for f in files:
        try:
            content = f.read_text(errors="ignore")
        except OSError:
            continue
        declared.extend(_MODULE_DECL.findall(content))
        for match in _INSTANTIATION.finditer(content):
            candidate = match.group(1)
            if candidate not in _NOT_MODULES:
                instantiated.add(candidate)

    candidates = [m for m in declared if m not in instantiated]
    return candidates[-1] if candidates else (declared[-1] if declared else "")


_INCLUDE_DIRECTIVE = re.compile(r'`include\s*"([^"]+)"')


def _filter_top_level_sources(sources: List[Path]) -> List[Path]:
    """
    Drop any source file that's `` `include``-ed (by basename) by another
    file in the set. Many real UVM testbenches split one class per file
    but only ever pull them in via `` `include`` inside a package/top file
    (rather than compiling each class file as its own top-level unit) —
    passing every discovered file straight to iverilog double-compiles
    them and produces disconnected-scope errors (e.g. a class extending
    uvm_agent with no uvm_pkg import in that unit). Excluding included
    files is safe: -I already makes them resolvable wherever they're
    `` `include``-ed from.
    """
    included_names = set()
    for f in sources:
        try:
            content = f.read_text(errors="ignore")
        except OSError:
            continue
        included_names.update(_INCLUDE_DIRECTIVE.findall(content))

    top_level = [f for f in sources if f.name not in included_names]
    return top_level or sources  # never return an empty list


def _collect_sources(rtl_path: str, tb_path: str) -> "tuple[List[Path], List[Path]]":
    """Returns (top_level_sources_to_compile, all_discovered_files_for_include_dirs)."""
    rtl_files = discover_files(Path(rtl_path), RTL_EXTENSIONS) if rtl_path else []
    tb_files = discover_files(Path(tb_path), TB_EXTENSIONS) if tb_path else []
    # Preserve order, drop duplicates (rtl/tb paths could overlap).
    seen = set()
    ordered = []
    for f in [*rtl_files, *tb_files]:
        if f not in seen:
            seen.add(f)
            ordered.append(f)
    return _filter_top_level_sources(ordered), ordered


def _write_dump_wrapper(output_dir: Path, top_module: str, vcd_path: Path) -> Path:
    """
    Write a small extra module that dumps the full design to VCD, so the
    user's testbench never needs its own $dumpfile/$dumpvars. Icarus treats
    any module with no instantiations as an additional simulation root, so
    this coexists with the real top module without an explicit -s flag.
    """
    wrapper_path = output_dir / "_verisight_dump.v"
    wrapper_path.write_text(
        "module _verisight_dump;\n"
        "  initial begin\n"
        f'    $dumpfile("{vcd_path}");\n'
        f"    $dumpvars(0, {top_module});\n"
        "  end\n"
        "endmodule\n"
    )
    return wrapper_path


def run_iverilog(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
) -> SimResult:
    """Compile with iverilog and run with vvp, producing a log and a VCD."""
    find_simulator("iverilog")
    vvp_bin = find_simulator("vvp")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, all_files = _collect_sources(rtl_path, tb_path)
    if not sources:
        raise SimulationError(f"No RTL/TB source files found under {rtl_path!r}, {tb_path!r}")

    top_module = top_module or _guess_top_module(all_files)
    if not top_module:
        raise SimulationError(
            "Could not determine a top module to simulate — pass --sim-top explicitly"
        )

    vcd_path = output_dir / "sim.vcd"
    log_path = output_dir / "sim.log"
    vvp_path = output_dir / "sim.vvp"
    dump_wrapper = _write_dump_wrapper(output_dir, top_module, vcd_path)

    include_dirs = sorted({str(p.resolve().parent) for p in all_files})
    cmd = ["iverilog", "-g2012", "-o", str(vvp_path)]
    for d in include_dirs:
        cmd += ["-I", d]

    leading_files = []
    if uvm_home:
        cmd += ["-I", uvm_home]
        # `uvm_*` macros must be defined, and the `uvm_pkg` package itself
        # must be compiled, before ANY source that uses `` `uvm_* `` macros
        # or `import uvm_pkg::*;` is compiled — Icarus preprocesses files in
        # command-line order and doesn't re-check earlier files once a
        # macro/package is defined later, so a plain alphabetical file list
        # breaks as soon as such a file sorts before whatever first
        # `` `include``s uvm_pkg.sv. Force it in via a tiny bootstrap file
        # compiled first, regardless of source file order.
        boot_path = output_dir / "_verisight_uvm_boot.v"
        boot_path.write_text('`include "uvm_pkg.sv"\n')
        leading_files.append(boot_path)

    cmd += [str(p) for p in leading_files] + [str(p) for p in sources] + [str(dump_wrapper)]

    logger.info(f"Compiling with iverilog (top={top_module}): {' '.join(cmd)}")
    compile_result = subprocess.run(cmd, capture_output=True, text=True)
    if compile_result.returncode != 0:
        raise SimulationError(
            f"iverilog compilation failed (exit {compile_result.returncode}):\n"
            f"{compile_result.stderr or compile_result.stdout}"
        )

    logger.info(f"Running simulation: vvp {vvp_path}")
    try:
        run_result = subprocess.run(
            [vvp_bin, str(vvp_path)],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + (e.stderr or "")
        log_path.write_text(partial + f"\n\n[VERISIGHT] Simulation timed out after {timeout_s}s\n")
        raise SimulationError(
            f"Simulation timed out after {timeout_s}s. Partial log saved to {log_path}"
        )

    log_path.write_text(run_result.stdout + run_result.stderr)
    logger.info(f"Simulation log written to {log_path}")

    if not vcd_path.exists():
        logger.warning(
            f"Simulation completed but no VCD was produced at {vcd_path} — "
            f"'{top_module}' may not be the actual elaborated root, or the "
            f"testbench finished before the dump wrapper's initial block ran"
        )

    return SimResult(
        log_path=log_path, vcd_path=vcd_path,
        returncode=run_result.returncode, simulator="iverilog", top_module=top_module,
    )


def run_verilator(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
) -> SimResult:
    """
    Compile and run with Verilator (--binary --trace). Experimental/
    best-effort backend: Verilator's SystemVerilog class/UVM support is
    less complete than Icarus's for typical UVM-lite testbenches, so this
    is offered for users who need raw simulation speed on synthesizable-
    heavy designs and have already validated their TB compiles under it.
    """
    find_simulator("verilator")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, all_files = _collect_sources(rtl_path, tb_path)
    if not sources:
        raise SimulationError(f"No RTL/TB source files found under {rtl_path!r}, {tb_path!r}")

    top_module = top_module or _guess_top_module(all_files)
    if not top_module:
        raise SimulationError(
            "Could not determine a top module to simulate — pass --sim-top explicitly"
        )

    log_path = output_dir / "sim.log"
    include_dirs = sorted({str(p.resolve().parent) for p in all_files})

    cmd = [
        "verilator", "--binary", "--trace", "--timing",
        "--top-module", top_module,
        "-Mdir", str(output_dir / "obj_dir"),
        "-o", "sim_bin",
    ]
    for d in include_dirs:
        cmd += ["-I" + d]
    if uvm_home:
        cmd += ["-I" + uvm_home]
    cmd += [str(p) for p in sources]

    logger.info(f"Building with verilator (top={top_module}): {' '.join(cmd)}")
    build_result = subprocess.run(cmd, capture_output=True, text=True)
    if build_result.returncode != 0:
        raise SimulationError(
            f"verilator build failed (exit {build_result.returncode}):\n"
            f"{build_result.stderr or build_result.stdout}"
        )

    binary = output_dir / "obj_dir" / "sim_bin"
    logger.info(f"Running simulation: {binary}")
    try:
        run_result = subprocess.run(
            [str(binary)], capture_output=True, text=True, timeout=timeout_s,
            cwd=str(output_dir),
        )
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + (e.stderr or "")
        log_path.write_text(partial + f"\n\n[VERISIGHT] Simulation timed out after {timeout_s}s\n")
        raise SimulationError(
            f"Simulation timed out after {timeout_s}s. Partial log saved to {log_path}"
        )

    log_path.write_text(run_result.stdout + run_result.stderr)
    logger.info(f"Simulation log written to {log_path}")

    # Verilator's --trace writes VCD next to the binary's cwd by default.
    vcd_path = next(output_dir.glob("*.vcd"), output_dir / "sim.vcd")

    return SimResult(
        log_path=log_path, vcd_path=vcd_path,
        returncode=run_result.returncode, simulator="verilator", top_module=top_module,
    )


def run_simulation(
    rtl_path: str,
    tb_path: str,
    simulator: str = "iverilog",
    top_module: str = "",
    uvm_home: str = "",
    timeout_s: int = 300,
    output_dir: Optional[Path] = None,
) -> SimResult:
    """
    Dispatch to the requested simulator backend and return its SimResult.

    Raises:
        SimulatorNotFoundError: the simulator binary isn't installed.
        SimulationError: compile failure, timeout, or no sources found.
    """
    output_dir = Path(output_dir) if output_dir else Path("output") / "sim"

    if simulator == "iverilog":
        return run_iverilog(rtl_path, tb_path, top_module, output_dir, uvm_home, timeout_s)
    elif simulator == "verilator":
        return run_verilator(rtl_path, tb_path, top_module, output_dir, uvm_home, timeout_s)
    else:
        raise SimulationError(f"Unknown simulator '{simulator}' — expected 'iverilog' or 'verilator'")
