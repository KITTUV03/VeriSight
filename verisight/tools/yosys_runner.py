"""
Yosys synthesis runner.

Synthesizes a gate-level Verilog netlist from RTL sources, for use as
input to x-tracer (see xtracer_runner.py). Only invoked when the user
opts into real X-propagation analysis and doesn't supply their own
netlist via --netlist.
"""

import shutil
import subprocess
from pathlib import Path
from typing import List

from verisight.utils.logger import get_logger

logger = get_logger("yosys_runner")

YOSYS_INSTALL_HINT = (
    "yosys was not found on PATH. Install it with your system package "
    "manager, e.g.:\n"
    "  Debian/Ubuntu: sudo apt install yosys\n"
    "  macOS:         brew install yosys\n"
    "Or build from source: https://github.com/YosysHQ/yosys"
)


def synthesize_netlist(rtl_files: List[str], top_module: str, output_path: Path) -> Path:
    """
    Synthesize a gate-level netlist from RTL sources using yosys.

    Args:
        rtl_files: RTL source files to read (SystemVerilog subset yosys supports).
        top_module: Top-level module name to synthesize.
        output_path: Where to write the resulting structural Verilog netlist.

    Returns:
        output_path, on success.

    Raises:
        RuntimeError: if yosys is missing, misconfigured, or synthesis fails.
    """
    if not rtl_files:
        raise RuntimeError("No RTL source files provided for synthesis")
    if not top_module:
        raise RuntimeError("No top module specified for synthesis")

    yosys_bin = shutil.which("yosys")
    if not yosys_bin:
        raise RuntimeError(YOSYS_INSTALL_HINT)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    include_dirs = sorted({str(Path(f).resolve().parent) for f in rtl_files})
    include_flags = " ".join(f'-I"{d}"' for d in include_dirs)
    read_cmd = " ".join(f'"{f}"' for f in rtl_files)
    script = (
        f"read_verilog -sv {include_flags} {read_cmd}; "
        f"synth -top {top_module}; "
        f'write_verilog -noattr "{output_path}"'
    )

    logger.info(f"Running yosys synthesis for top module '{top_module}'")
    result = subprocess.run(
        [yosys_bin, "-p", script],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"yosys synthesis failed (exit {result.returncode}):\n{result.stderr or result.stdout}"
        )

    if not output_path.exists():
        raise RuntimeError(
            f"yosys reported success but did not produce {output_path}:\n{result.stdout}"
        )

    logger.info(f"Synthesized netlist written to {output_path}")
    return output_path
