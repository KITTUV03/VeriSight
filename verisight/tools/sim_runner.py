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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

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
    "questa": (
        "vlog/vsim were not found on PATH. Ensure Siemens Questa SIM / ModelSim "
        "is installed and added to your environment PATH."
    ),
    "vcs": (
        "vcs was not found on PATH. Ensure Synopsys VCS is installed and added "
        "to your environment PATH."
    ),
    "xcelium": (
        "xrun was not found on PATH. Ensure Cadence Xcelium is installed and added "
        "to your environment PATH."
    ),
    "dsim": (
        "dsim was not found on PATH. Ensure Altair DSim is installed and added "
        "to your environment PATH."
    ),
    "xsim": (
        "xvlog/xelab/xsim were not found on PATH. Ensure AMD Vivado / XSim is installed "
        "and added to your environment PATH."
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
    returncode: int = 0
    simulator: str = ""
    top_module: str = ""
    coverage_path: Optional[Path] = None
    duration_s: float = 0.0
    error_count: int = 0
    warning_count: int = 0
    success: bool = False

    def __post_init__(self):
        if not self.success:
            self.success = (self.returncode == 0 and self.error_count == 0)


def _strip_comments(code: str) -> str:
    """Strip SystemVerilog single-line (//) and multi-line (/* */) comments."""
    def replacer(match):
        s = match.group(0)
        if s.startswith("/"):
            return " "
        return s

    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE,
    )
    return re.sub(pattern, replacer, code)


def is_uvm_testbench(tb_path: Any) -> bool:
    """
    Scan relevant .sv and .svh files for UVM package imports and macros:
    - import uvm_pkg::*
    - `include "uvm_macros.svh"
    Robustly handles comments, nested includes, and missing files without false positives.
    """
    if not tb_path:
        return False

    files_to_check: List[Path] = []
    if isinstance(tb_path, (list, tuple, set)):
        paths = list(tb_path)
    else:
        paths = [tb_path]

    for p in paths:
        if not p:
            continue
        p_obj = Path(p)
        if not p_obj.exists():
            continue
        if p_obj.is_file():
            if p_obj.suffix.lower() in (".sv", ".svh", ".v", ".vh"):
                files_to_check.append(p_obj)
        elif p_obj.is_dir():
            files_to_check.extend(discover_files(p_obj, TB_EXTENSIONS))

    if not files_to_check:
        return False

    uvm_import_pattern = re.compile(r"\bimport\s+uvm_pkg\s*::\s*\*")
    uvm_macro_pattern = re.compile(r'`include\s*["<]uvm_macros\.svh[">]')

    checked: set = set()
    queue = list(files_to_check)

    while queue:
        f = queue.pop(0)
        if f in checked or not f.is_file():
            continue
        checked.add(f)
        try:
            content = f.read_text(errors="ignore")
        except OSError:
            continue

        clean = _strip_comments(content)
        if uvm_import_pattern.search(clean) or uvm_macro_pattern.search(clean):
            return True

        # Process nested includes in same directory
        for m in _INCLUDE_DIRECTIVE.finditer(clean):
            inc = m.group(1)
            candidate = f.parent / inc
            if candidate.exists() and candidate not in checked:
                queue.append(candidate)

    return False


def resolve_simulator(requested: str = "auto", is_uvm: bool = False) -> str:
    """
    Resolve simulator executable according to priority and testbench type:
    - For auto with UVM: vcs → vsim (questa) → xrun (xcelium) → dsim → xvlog (xsim) → verilator
    - For auto without UVM: iverilog → verilator → xvlog (xsim) → questa → vcs → xcelium → dsim
    - If iverilog is explicitly selected for UVM: report limitations and fail clearly.
    - Verify selected executable before execution.
    """
    norm = (requested or "auto").lower()
    if norm in ("modelsim", "vsim"):
        norm = "questa"
    elif norm in ("xrun",):
        norm = "xcelium"
    elif norm in ("xvlog", "xelab"):
        norm = "xsim"

    if norm == "auto":
        if is_uvm:
            priority = [
                ("vcs", "vcs"),
                ("questa", "vsim"),
                ("xcelium", "xrun"),
                ("dsim", "dsim"),
                ("xsim", "xvlog"),
                ("verilator", "verilator"),
            ]
            for sim_name, bin_name in priority:
                if shutil.which(bin_name):
                    return sim_name

            if shutil.which("verilator"):
                return "verilator"
            if shutil.which("iverilog"):
                raise SimulatorNotFoundError(
                    "Detected UVM testbench, but no full IEEE-1800 UVM 1.2 simulator was found on PATH "
                    "(searched priority: vcs, vsim, xrun, dsim, xvlog, verilator). "
                    "Icarus Verilog lacks support for standard UVM 1.2 class hierarchy and constraints."
                )
            raise SimulatorNotFoundError(
                "Detected UVM testbench, but no supported simulator binary was found on PATH "
                "(searched priority: vcs, vsim, xrun, dsim, xvlog, verilator)."
            )
        else:
            priority = [
                ("iverilog", "iverilog"),
                ("verilator", "verilator"),
                ("xsim", "xvlog"),
                ("questa", "vsim"),
                ("vcs", "vcs"),
                ("xcelium", "xrun"),
                ("dsim", "dsim"),
            ]
            for sim_name, bin_name in priority:
                if shutil.which(bin_name):
                    return sim_name
            raise SimulatorNotFoundError("No supported simulator binary found on PATH.")

    if norm == "iverilog" and is_uvm:
        raise SimulationError(
            "Icarus Verilog (iverilog) does not support standard IEEE-1800 SystemVerilog UVM 1.2 "
            "(lacks class constraints, randomize(), factory overrides, and dynamic casting). "
            "Please select a compliant UVM simulator (vcs, questa, xcelium, dsim, xsim, or verilator 5+)."
        )

    find_simulator(norm)
    return norm


def find_best_simulator() -> str:
    """Auto-detect the best available simulator on system PATH (legacy helper)."""
    try:
        return resolve_simulator("auto", is_uvm=False)
    except SimulatorNotFoundError:
        return "iverilog"


def find_simulator(name: str) -> str:
    """Resolve the primary binary for a simulator ('iverilog', 'verilator', 'questa', 'vcs', 'xcelium', 'dsim', 'xsim')."""
    if name == "auto":
        name = find_best_simulator()

    bin_map = {
        "iverilog": "iverilog",
        "vvp": "vvp",
        "verilator": "verilator",
        "questa": "vsim",
        "modelsim": "vsim",
        "vsim": "vsim",
        "vcs": "vcs",
        "xcelium": "xrun",
        "xrun": "xrun",
        "dsim": "dsim",
        "xsim": "xsim",
        "xvlog": "xvlog",
        "xelab": "xelab",
    }
    target = bin_map.get(name.lower(), name)
    binary = shutil.which(target)
    if not binary:
        raise SimulatorNotFoundError(SIM_INSTALL_HINTS.get(name.lower(), f"{name} not found on PATH"))
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


# ─── Backend Command Builders ─────────────────────────────────────────────

def build_iverilog_cmd(
    sources: List[Path],
    include_dirs: List[str],
    dump_wrapper: Path,
    vvp_path: Path,
    leading_files: Optional[List[Path]] = None,
    uvm_home: str = "",
) -> List[str]:
    """Build Icarus Verilog compilation command."""
    cmd = ["iverilog", "-g2012", "-o", str(vvp_path)]
    for d in include_dirs:
        cmd.extend(["-I", d])
    if uvm_home:
        cmd.extend(["-I", uvm_home])
    if leading_files:
        cmd.extend([str(p) for p in leading_files])
    cmd.extend([str(p) for p in sources])
    cmd.append(str(dump_wrapper))
    return cmd


def build_verilator_cmd(
    sources: List[Path],
    include_dirs: List[str],
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    is_uvm: bool = False,
) -> List[str]:
    """Build Verilator 5+ compilation command."""
    cmd = [
        "verilator",
        "--binary",
        "--timing",
        "-Wno-fatal",
        "--trace",
        "--top-module",
        top_module,
        "-Mdir",
        str(output_dir / "obj_dir"),
        "-o",
        "sim_bin",
    ]
    for d in include_dirs:
        cmd.append(f"-I{d}")
    if uvm_home:
        cmd.append(f"-I{uvm_home}")
    if is_uvm:
        cmd.extend(["+define+UVM_NO_DPI", "-Wno-style"])
    cmd.extend([str(p) for p in sources])
    return cmd


def build_xsim_cmds(
    sources: List[Path],
    include_dirs: List[str],
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    is_uvm: bool = False,
) -> Tuple[List[str], List[str], List[str]]:
    """Build Vivado/XSim xvlog, xelab, and xsim commands."""
    xvlog_cmd = ["xvlog", "-sv"]
    for d in include_dirs:
        xvlog_cmd.extend(["-i", d])
    if uvm_home:
        xvlog_cmd.extend(["-i", uvm_home])
    xvlog_cmd.extend([str(p) for p in sources])

    xelab_cmd = ["xelab", top_module, "-debug", "typical", "-s", "sim_snap"]
    if is_uvm:
        xelab_cmd.extend(["-L", "uvm"])

    xsim_cmd = ["xsim", "sim_snap", "-R"]
    return xvlog_cmd, xelab_cmd, xsim_cmd


def build_dsim_cmd(
    sources: List[Path],
    include_dirs: List[str],
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    is_uvm: bool = False,
) -> List[str]:
    """Build Altair DSim command."""
    vcd_path = output_dir / "sim.vcd"
    cmd = [
        "dsim",
        "-sv",
        "+acc+b",
        "-waves",
        str(vcd_path),
        "-top",
        top_module,
    ]
    if is_uvm:
        cmd.extend(["-uvm", "1.2"])
    for d in include_dirs:
        cmd.append(f"+incdir+{d}")
    if uvm_home:
        cmd.append(f"+incdir+{uvm_home}")
    cmd.extend([str(p) for p in sources])
    return cmd


def build_vcs_cmd(
    sources: List[Path],
    include_dirs: List[str],
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    is_uvm: bool = False,
) -> List[str]:
    """Build Synopsys VCS compilation command."""
    cmd = [
        "vcs",
        "-full64",
        "-sverilog",
        "-debug_access+all",
        "-o",
        str(output_dir / "simv"),
        "-top",
        top_module,
    ]
    if is_uvm:
        cmd.extend(["-ntb_opts", "uvm-1.2"])
    for d in include_dirs:
        cmd.append(f"+incdir+{d}")
    if uvm_home:
        cmd.append(f"+incdir+{uvm_home}")
    cmd.extend([str(p) for p in sources])
    return cmd


def build_questa_cmds(
    sources: List[Path],
    include_dirs: List[str],
    top_module: str,
    work_dir: Path,
    ucdb_path: Path,
    vcd_path: Path,
    uvm_home: str = "",
    is_uvm: bool = False,
) -> Tuple[List[str], List[str]]:
    """Build Siemens Questa vlog and vsim commands."""
    vlog_bin = shutil.which("vlog") or "vlog"
    vsim_bin = shutil.which("vsim") or "vsim"

    vlog_cmd = [vlog_bin, "-sv", "+cover=bcesfx", "-work", str(work_dir)]
    for d in include_dirs:
        vlog_cmd.append(f"+incdir+{d}")
    if uvm_home:
        vlog_cmd.append(f"+incdir+{uvm_home}")
    vlog_cmd.extend([str(p) for p in sources])

    do_commands = f"coverage save -onexit {ucdb_path}; vcd file {vcd_path}; vcd add -r /*; run -all; quit"
    vsim_cmd = [vsim_bin, "-c", "-do", do_commands, "-lib", str(work_dir), top_module]
    return vlog_cmd, vsim_cmd


def build_xcelium_cmd(
    sources: List[Path],
    include_dirs: List[str],
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    is_uvm: bool = False,
) -> List[str]:
    """Build Cadence Xcelium xrun command."""
    cmd = [
        "xrun",
        "-sv",
        "-access",
        "+rwc",
        "-top",
        top_module,
    ]
    if is_uvm:
        cmd.append("-uvm")
    for d in include_dirs:
        cmd.extend(["-incdir", d])
    if uvm_home:
        cmd.extend(["-incdir", uvm_home])
    cmd.extend([str(p) for p in sources])
    return cmd


# ─── Execution Flows ───────────────────────────────────────────────────────

def run_iverilog(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
    is_uvm: bool = False,
) -> SimResult:
    """Compile with iverilog and run with vvp, producing a log and a VCD."""
    if is_uvm:
        raise SimulationError(
            "Icarus Verilog (iverilog) does not support standard IEEE-1800 SystemVerilog UVM 1.2 "
            "(lacks class constraints, randomize(), factory overrides, and dynamic casting). "
            "Please select a compliant UVM simulator (vcs, questa, xcelium, dsim, xsim, or verilator 5+)."
        )

    find_simulator("iverilog")
    vvp_bin = find_simulator("vvp")

    start_time = time.time()
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
    leading_files = []
    if uvm_home:
        boot_path = output_dir / "_verisight_uvm_boot.v"
        boot_path.write_text('`include "uvm_pkg.sv"\n')
        leading_files.append(boot_path)

    cmd = build_iverilog_cmd(sources, include_dirs, dump_wrapper, vvp_path, leading_files, uvm_home)

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

    full_log = run_result.stdout + run_result.stderr
    log_path.write_text(full_log)
    logger.info(f"Simulation log written to {log_path}")

    local_vcd = Path("sim.vcd")
    if local_vcd.exists() and not vcd_path.exists():
        try:
            shutil.move(str(local_vcd), str(vcd_path))
        except Exception:
            pass

    if not vcd_path.exists():
        logger.warning(
            f"Simulation completed but no VCD was produced at {vcd_path} — "
            f"'{top_module}' may not be the actual elaborated root, or the "
            f"testbench finished before the dump wrapper's initial block ran"
        )

    err_matches = len(re.findall(r"(?:UVM_ERROR|UVM_FATAL|Error:|MISMATCH:|FAILED)", full_log, re.IGNORECASE))
    duration_s = round(time.time() - start_time, 2)

    return SimResult(
        log_path=log_path,
        vcd_path=vcd_path,
        returncode=run_result.returncode,
        simulator="iverilog",
        top_module=top_module,
        duration_s=duration_s,
        error_count=err_matches,
    )


def run_verilator(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
    is_uvm: bool = False,
) -> SimResult:
    """Compile and run with Verilator 5+ (--binary --timing -Wno-fatal --trace)."""
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
    start_time = time.time()

    cmd = build_verilator_cmd(sources, include_dirs, top_module, output_dir, uvm_home, is_uvm)

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

    full_log = run_result.stdout + run_result.stderr
    log_path.write_text(full_log)
    logger.info(f"Simulation log written to {log_path}")

    vcd_path = next(output_dir.glob("*.vcd"), output_dir / "sim.vcd")
    duration_s = round(time.time() - start_time, 2)
    err_matches = len(re.findall(r"(?:UVM_ERROR|UVM_FATAL|Error:|MISMATCH:|FAILED)", full_log, re.IGNORECASE))

    return SimResult(
        log_path=log_path,
        vcd_path=vcd_path,
        returncode=run_result.returncode,
        simulator="verilator",
        top_module=top_module,
        duration_s=duration_s,
        error_count=err_matches,
    )


def run_questa(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
    is_uvm: bool = False,
) -> SimResult:
    """Compile with vlog and simulate with vsim, generating UCDB coverage and VCD."""
    find_simulator("questa")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, all_files = _collect_sources(rtl_path, tb_path)
    if not sources:
        raise SimulationError(f"No RTL/TB source files found under {rtl_path!r}, {tb_path!r}")

    top_module = top_module or _guess_top_module(all_files)
    if not top_module:
        raise SimulationError("Could not determine top module to simulate")

    log_path = output_dir / "sim.log"
    vcd_path = output_dir / "sim.vcd"
    ucdb_path = output_dir / "coverage.ucdb"
    start_time = time.time()

    include_dirs = sorted({str(p.resolve().parent) for p in all_files})
    work_dir = output_dir / "work"

    vlog_cmd, vsim_cmd = build_questa_cmds(
        sources, include_dirs, top_module, work_dir, ucdb_path, vcd_path, uvm_home, is_uvm
    )

    logger.info(f"Compiling with Questa vlog: {' '.join(vlog_cmd)}")
    c_res = subprocess.run(vlog_cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))
    if c_res.returncode != 0:
        raise SimulationError(f"Questa vlog failed:\n{c_res.stderr or c_res.stdout}")

    logger.info(f"Running Questa vsim: {' '.join(vsim_cmd)}")
    run_result = subprocess.run(vsim_cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))

    full_log = c_res.stdout + run_result.stdout + run_result.stderr
    log_path.write_text(full_log)
    duration_s = round(time.time() - start_time, 2)
    err_matches = len(re.findall(r"(?:UVM_ERROR|UVM_FATAL|Error:|MISMATCH:|FAILED)", full_log, re.IGNORECASE))

    return SimResult(
        log_path=log_path,
        vcd_path=vcd_path,
        returncode=run_result.returncode,
        simulator="questa",
        top_module=top_module,
        coverage_path=ucdb_path if ucdb_path.exists() else None,
        duration_s=duration_s,
        error_count=err_matches,
    )


def run_vcs(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
    is_uvm: bool = False,
) -> SimResult:
    """Compile with Synopsys VCS and simulate."""
    find_simulator("vcs")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, all_files = _collect_sources(rtl_path, tb_path)
    if not sources:
        raise SimulationError(f"No RTL/TB source files found under {rtl_path!r}, {tb_path!r}")

    top_module = top_module or _guess_top_module(all_files)
    if not top_module:
        raise SimulationError("Could not determine top module to simulate")

    log_path = output_dir / "sim.log"
    vcd_path = output_dir / "sim.vcd"
    start_time = time.time()
    include_dirs = sorted({str(p.resolve().parent) for p in all_files})

    cmd = build_vcs_cmd(sources, include_dirs, top_module, output_dir, uvm_home, is_uvm)
    logger.info(f"Compiling with Synopsys VCS: {' '.join(cmd)}")
    c_res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))
    if c_res.returncode != 0:
        raise SimulationError(f"VCS compilation failed (exit {c_res.returncode}):\n{c_res.stderr or c_res.stdout}")

    simv = output_dir / "simv"
    logger.info(f"Running VCS simulation: {simv}")
    run_res = subprocess.run([str(simv), f"+vcs+dumpvars+{vcd_path}"], capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))
    full_log = c_res.stdout + run_res.stdout + run_res.stderr
    log_path.write_text(full_log)
    duration_s = round(time.time() - start_time, 2)
    err_matches = len(re.findall(r"(?:UVM_ERROR|UVM_FATAL|Error:|MISMATCH:|FAILED)", full_log, re.IGNORECASE))

    return SimResult(
        log_path=log_path,
        vcd_path=vcd_path,
        returncode=run_res.returncode,
        simulator="vcs",
        top_module=top_module,
        duration_s=duration_s,
        error_count=err_matches,
    )


def run_xcelium(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
    is_uvm: bool = False,
) -> SimResult:
    """Compile and simulate with Cadence Xcelium."""
    find_simulator("xcelium")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, all_files = _collect_sources(rtl_path, tb_path)
    if not sources:
        raise SimulationError(f"No RTL/TB source files found under {rtl_path!r}, {tb_path!r}")

    top_module = top_module or _guess_top_module(all_files)
    if not top_module:
        raise SimulationError("Could not determine top module to simulate")

    log_path = output_dir / "sim.log"
    vcd_path = output_dir / "sim.vcd"
    start_time = time.time()
    include_dirs = sorted({str(p.resolve().parent) for p in all_files})

    cmd = build_xcelium_cmd(sources, include_dirs, top_module, output_dir, uvm_home, is_uvm)
    logger.info(f"Running Cadence Xcelium: {' '.join(cmd)}")
    run_res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))
    full_log = run_res.stdout + run_res.stderr
    log_path.write_text(full_log)
    duration_s = round(time.time() - start_time, 2)
    err_matches = len(re.findall(r"(?:UVM_ERROR|UVM_FATAL|Error:|MISMATCH:|FAILED)", full_log, re.IGNORECASE))

    return SimResult(
        log_path=log_path,
        vcd_path=vcd_path,
        returncode=run_res.returncode,
        simulator="xcelium",
        top_module=top_module,
        duration_s=duration_s,
        error_count=err_matches,
    )


def run_dsim(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
    is_uvm: bool = False,
) -> SimResult:
    """Compile and simulate with Altair DSim."""
    find_simulator("dsim")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, all_files = _collect_sources(rtl_path, tb_path)
    if not sources:
        raise SimulationError(f"No RTL/TB source files found under {rtl_path!r}, {tb_path!r}")

    top_module = top_module or _guess_top_module(all_files)
    if not top_module:
        raise SimulationError("Could not determine top module to simulate")

    log_path = output_dir / "sim.log"
    vcd_path = output_dir / "sim.vcd"
    start_time = time.time()
    include_dirs = sorted({str(p.resolve().parent) for p in all_files})

    cmd = build_dsim_cmd(sources, include_dirs, top_module, output_dir, uvm_home, is_uvm)
    logger.info(f"Running Altair DSim: {' '.join(cmd)}")
    run_res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))
    full_log = run_res.stdout + run_res.stderr
    log_path.write_text(full_log)
    duration_s = round(time.time() - start_time, 2)
    err_matches = len(re.findall(r"(?:UVM_ERROR|UVM_FATAL|Error:|MISMATCH:|FAILED)", full_log, re.IGNORECASE))

    return SimResult(
        log_path=log_path,
        vcd_path=vcd_path,
        returncode=run_res.returncode,
        simulator="dsim",
        top_module=top_module,
        duration_s=duration_s,
        error_count=err_matches,
    )


def run_xsim(
    rtl_path: str,
    tb_path: str,
    top_module: str,
    output_dir: Path,
    uvm_home: str = "",
    timeout_s: int = 300,
    is_uvm: bool = False,
) -> SimResult:
    """Compile and simulate with Vivado / XSim (xvlog -> xelab -> xsim)."""
    find_simulator("xvlog")
    find_simulator("xelab")
    find_simulator("xsim")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, all_files = _collect_sources(rtl_path, tb_path)
    if not sources:
        raise SimulationError(f"No RTL/TB source files found under {rtl_path!r}, {tb_path!r}")

    top_module = top_module or _guess_top_module(all_files)
    if not top_module:
        raise SimulationError("Could not determine top module to simulate")

    log_path = output_dir / "sim.log"
    vcd_path = output_dir / "sim.vcd"
    start_time = time.time()
    include_dirs = sorted({str(p.resolve().parent) for p in all_files})

    xvlog_cmd, xelab_cmd, xsim_cmd = build_xsim_cmds(
        sources, include_dirs, top_module, output_dir, uvm_home, is_uvm
    )

    logger.info(f"Compiling with Vivado xvlog: {' '.join(xvlog_cmd)}")
    c_res = subprocess.run(xvlog_cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))
    if c_res.returncode != 0:
        raise SimulationError(f"xvlog failed (exit {c_res.returncode}):\n{c_res.stderr or c_res.stdout}")

    logger.info(f"Elaborating with Vivado xelab: {' '.join(xelab_cmd)}")
    e_res = subprocess.run(xelab_cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))
    if e_res.returncode != 0:
        raise SimulationError(f"xelab failed (exit {e_res.returncode}):\n{e_res.stderr or e_res.stdout}")

    logger.info(f"Simulating with Vivado xsim: {' '.join(xsim_cmd)}")
    run_res = subprocess.run(xsim_cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(output_dir))

    full_log = c_res.stdout + e_res.stdout + run_res.stdout + run_res.stderr
    log_path.write_text(full_log)
    duration_s = round(time.time() - start_time, 2)
    err_matches = len(re.findall(r"(?:UVM_ERROR|UVM_FATAL|Error:|MISMATCH:|FAILED)", full_log, re.IGNORECASE))

    return SimResult(
        log_path=log_path,
        vcd_path=vcd_path,
        returncode=run_res.returncode,
        simulator="xsim",
        top_module=top_module,
        duration_s=duration_s,
        error_count=err_matches,
    )


def run_simulation(
    rtl_path: Optional[Any] = None,
    tb_path: Optional[Any] = None,
    simulator: str = "auto",
    top_module: str = "",
    uvm_home: str = "",
    timeout_s: int = 300,
    output_dir: Optional[Any] = None,
    **kwargs,
) -> SimResult:
    """
    Dispatch to the requested simulator backend ('auto', 'iverilog', 'verilator', 'questa',
    'vcs', 'xcelium', 'dsim', 'xsim') and return its SimResult.
    """
    rtl_in = rtl_path or kwargs.get("rtl_files")
    tb_in = tb_path or kwargs.get("tb_files")
    if not rtl_in or not tb_in:
        raise ValueError("Both rtl_path and tb_path must be provided to run_simulation")

    is_uvm = is_uvm_testbench(tb_in)
    sim_choice = resolve_simulator(simulator, is_uvm=is_uvm)
    logger.info(f"Simulator resolved: {sim_choice} (is_uvm={is_uvm})")

    output_dir = Path(output_dir) if output_dir else Path("output") / "sim"

    if sim_choice == "iverilog":
        return run_iverilog(rtl_in, tb_in, top_module, output_dir, uvm_home, timeout_s, is_uvm=is_uvm)
    elif sim_choice == "verilator":
        return run_verilator(rtl_in, tb_in, top_module, output_dir, uvm_home, timeout_s, is_uvm=is_uvm)
    elif sim_choice in ("questa", "modelsim"):
        return run_questa(rtl_in, tb_in, top_module, output_dir, uvm_home, timeout_s, is_uvm=is_uvm)
    elif sim_choice == "vcs":
        return run_vcs(rtl_in, tb_in, top_module, output_dir, uvm_home, timeout_s, is_uvm=is_uvm)
    elif sim_choice == "xcelium":
        return run_xcelium(rtl_in, tb_in, top_module, output_dir, uvm_home, timeout_s, is_uvm=is_uvm)
    elif sim_choice == "dsim":
        return run_dsim(rtl_in, tb_in, top_module, output_dir, uvm_home, timeout_s, is_uvm=is_uvm)
    elif sim_choice == "xsim":
        return run_xsim(rtl_in, tb_in, top_module, output_dir, uvm_home, timeout_s, is_uvm=is_uvm)
    else:
        raise SimulationError(
            f"Unknown simulator '{simulator}' — expected 'auto', 'verilator', 'iverilog', 'xsim', 'dsim', 'vcs', 'questa', or 'xcelium'"
        )


def execute_closed_loop_flow(
    rtl_path: str,
    tb_path: str,
    spec_path: Optional[str] = None,
    simulator: str = "auto",
    top_module: str = "",
    uvm_home: str = "",
    timeout_s: int = 300,
    output_dir: str = "output/closed_loop",
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    airgap: bool = False,
    anonymize_rtl: bool = False,
    local_endpoint: str = "",
    launch_browser: bool = False,
) -> Dict[str, Any]:
    """
    Unified One-Click Closed-Loop Simulation Runner:
    1. Runs RTL + TB simulation via chosen or auto-detected simulator (Icarus / Verilator / Questa).
    2. Collects sim.log and sim.vcd waveform trace.
    3. Triggers Root-Cause Analysis (Agents 1-4 + Fix) -> generates report.html with embedded Waveform Studio!
    4. If spec_path is provided, triggers VeriSight Plan -> correlates coverage & generates verification_plan.html!
    5. Returns artifact paths and metrics.
    """
    from verisight.orchestrator import VeriSightPipeline
    from verisight.plan.planner_orchestrator import VeriSightPlanner
    from verisight.config import set_config, VeriSightConfig, LLMConfig

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    sim_out = out_path / "sim"

    logger.info(f"Step 1: Running Simulation with {simulator} backend...")
    sim_res = run_simulation(
        rtl_path=rtl_path,
        tb_path=tb_path,
        simulator=simulator,
        top_module=top_module,
        uvm_home=uvm_home,
        timeout_s=timeout_s,
        output_dir=sim_out,
    )

    logger.info(
        f"Simulation finished (exit={sim_res.returncode}, duration={sim_res.duration_s}s, "
        f"{sim_res.error_count} error patterns detected in log)"
    )

    # Configure AI Engine
    from verisight.config import (
        set_config,
        VeriSightConfig,
        LLMConfig,
        PipelineConfig,
        ChromaConfig,
        XTracerConfig,
        FixConfig,
    )

    cfg = VeriSightConfig(
        llm=LLMConfig(
            provider=provider or "gemini",
            api_key=api_key,
            model_name=model_name or "gemini-3.8-flash",
            airgap=airgap,
            anonymize_rtl=anonymize_rtl,
            local_endpoint=local_endpoint,
        ),
        pipeline=PipelineConfig(
            output_dir=str(out_path / "debug"),
            save_intermediates=True,
            enable_rag=bool(api_key and not airgap),
            verbose=False,
        ),
        chroma=ChromaConfig(),
        xtracer=XTracerConfig(),
        fix=FixConfig(enabled=True),
    )
    set_config(cfg)

    # Step 2: Root-Cause Analysis Pipeline
    logger.info("Step 2: Launching Autonomous Debug Analysis Engine...")
    pipeline = VeriSightPipeline(config=cfg)
    debug_report = pipeline.run(
        log_path=str(sim_res.log_path),
        rtl_path=rtl_path,
        spec_path=spec_path,
        tb_path=tb_path,
        vcd_path=str(sim_res.vcd_path) if sim_res.vcd_path.exists() else None,
        coverage_path=str(sim_res.coverage_path) if sim_res.coverage_path and sim_res.coverage_path.exists() else None,
    )

    # Step 3: Verification Plan & Live Coverage Cockpit
    plan_report = None
    if spec_path and Path(spec_path).exists():
        logger.info("Step 3: Launching Autonomous Verification Plan Architect...")
        planner = VeriSightPlanner(output_dir=str(out_path / "plan"))
        cov_source = str(sim_res.coverage_path) if sim_res.coverage_path and sim_res.coverage_path.exists() else None
        plan_report = planner.run(
            spec_path=spec_path,
            rtl_path=rtl_path,
            design_name=sim_res.top_module or "DUT",
            coverage_path=cov_source,
        )

    debug_html = out_path / "debug" / "report.html"
    plan_html = (out_path / "plan" / "verification_plan.html") if plan_report else None

    dashboards = {
        "debug_report_html": str(debug_html),
    }
    if plan_html and plan_html.exists():
        dashboards["plan_cockpit_html"] = str(plan_html)

    if launch_browser:
        import webbrowser
        if debug_html.exists():
            webbrowser.open(f"file://{debug_html.resolve()}")
        if plan_html and plan_html.exists():
            webbrowser.open(f"file://{plan_html.resolve()}")

    return {
        "sim": sim_res,
        "sim_result": sim_res,
        "rca": debug_report,
        "debug_report": debug_report,
        "plan": plan_report,
        "plan_report": plan_report,
        "dashboards": dashboards,
        "output_dir": out_path,
        "report_html": debug_html,
        "plan_html": plan_html,
        "vcd_path": sim_res.vcd_path,
        "log_path": sim_res.log_path,
    }
