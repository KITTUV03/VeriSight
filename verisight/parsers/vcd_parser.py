"""
VCD waveform parser.

Post-processes a simulation VCD (user-supplied, or produced internally by
--simulate via sim_runner.py) into a compact VCDData summary that Agent 2
and Agent 3 can query directly — no need for the real x-tracer tool to be
installed to get *some* waveform-backed evidence.

Backend priority: pywellen (fast, Rust-backed, handles large industrial
VCD/FST files with low memory) > vcdvcd (pure Python, always pip-installable,
used as a reliable fallback). Neither is a hard dependency — if both are
missing, parse_vcd() degrades to a clear tool_status rather than raising,
matching the house style of yosys_runner.py / xtracer_runner.py.
"""

import re
from pathlib import Path
from typing import List, Optional

from verisight.schemas.vcd_schema import VCDData, VCDSignalWave, VCDTransition
from verisight.utils.logger import get_logger

logger = get_logger("vcd_parser")

MAX_SIGNALS = 300
MAX_TRANSITIONS_PER_SIGNAL = 2000

VCD_PARSER_INSTALL_HINT = (
    "No VCD parser backend is installed. Install one of:\n"
    "  pip install pywellen   # fast, recommended\n"
    "  pip install vcdvcd     # pure-Python fallback\n"
    "VeriSight will continue without waveform-based evidence."
)

_TIME_UNIT_TO_PS = {
    "fs": 0,  # sub-picosecond, effectively rounds to 0 — not expected in practice
    "ps": 1,
    "ns": 1_000,
    "us": 1_000_000,
    "ms": 1_000_000_000,
    "s": 1_000_000_000_000,
}


def _timescale_to_ps_multiplier(timescale: str) -> int:
    """Parse a VCD timescale string like '1ns' or '10 ps' into a ps multiplier."""
    match = re.search(r"(\d+)\s*(fs|ps|ns|us|ms|s)", timescale or "", re.IGNORECASE)
    if not match:
        return 1000  # assume 1ns default, VeriSight's most common case
    magnitude = int(match.group(1))
    unit = match.group(2).lower()
    return max(1, magnitude * _TIME_UNIT_TO_PS.get(unit, 1000))


def parse_vcd(vcd_path: str, signal_filter: Optional[List[str]] = None) -> VCDData:
    """
    Parse a VCD file into a VCDData summary.

    Args:
        vcd_path: Path to the .vcd file.
        signal_filter: Optional list of hierarchical path substrings — when
            given, only matching signals are kept (bounds memory for huge VCDs).

    Returns:
        VCDData. Never raises — tool_status/tool_message report degradation.
    """
    path = Path(vcd_path)
    if not path.exists():
        return VCDData(
            source_file=str(path),
            tool_status="skipped_no_vcd",
            tool_message=f"VCD file not found: {path}",
        )

    try:
        return _parse_with_pywellen(path, signal_filter)
    except ImportError:
        logger.info("pywellen not installed — trying vcdvcd fallback")
    except Exception as e:
        logger.warning(f"pywellen failed to parse {path} ({e}) — trying vcdvcd fallback")

    try:
        return _parse_with_vcdvcd(path, signal_filter)
    except ImportError:
        logger.warning(VCD_PARSER_INSTALL_HINT)
        return VCDData(
            source_file=str(path),
            parser_backend="unavailable",
            tool_status="skipped_not_installed",
            tool_message=VCD_PARSER_INSTALL_HINT,
        )
    except Exception as e:
        logger.warning(f"vcdvcd failed to parse {path}: {e}")
        return VCDData(
            source_file=str(path),
            parser_backend="vcdvcd",
            tool_status="error",
            tool_message=f"VCD parsing failed: {e}",
        )


def _keep_signal(path: str, signal_filter: Optional[List[str]]) -> bool:
    if not signal_filter:
        return True
    return any(frag in path for frag in signal_filter)


def _parse_with_pywellen(path: Path, signal_filter: Optional[List[str]]) -> VCDData:
    import pywellen  # optional dependency

    wave = pywellen.Waveform(str(path))
    hierarchy = wave.hierarchy

    timescale_str = ""
    try:
        ts = hierarchy.timescale()
        timescale_str = f"{ts[0]}{ts[1]}" if isinstance(ts, (tuple, list)) else str(ts)
    except Exception:
        pass
    time_unit_ps = _timescale_to_ps_multiplier(timescale_str)

    all_vars = list(hierarchy.all_vars())
    signal_count = len(all_vars)

    signals = {}
    truncated_signals: List[str] = []

    for var in all_vars:
        full_name = var.full_name(hierarchy)
        if not _keep_signal(full_name, signal_filter):
            continue
        if len(signals) >= MAX_SIGNALS:
            truncated_signals.append(full_name)
            continue

        sig_handle = wave.get_signal(var)
        transitions = []
        has_x = has_z = False
        changes = list(sig_handle.all_changes())
        truncated = len(changes) > MAX_TRANSITIONS_PER_SIGNAL
        for time_idx, value in changes[:MAX_TRANSITIONS_PER_SIGNAL]:
            value_str = str(value)
            if "x" in value_str.lower():
                has_x = True
            if "z" in value_str.lower():
                has_z = True
            transitions.append(VCDTransition(
                time_ps=int(time_idx) * time_unit_ps, value=value_str,
            ))

        signals[full_name] = VCDSignalWave(
            name=full_name.rsplit(".", 1)[-1],
            hierarchy=full_name,
            width=getattr(var, "width", lambda: 1)() if callable(getattr(var, "width", None)) else 1,
            transitions=transitions,
            has_x=has_x,
            has_z=has_z,
            truncated=truncated,
        )

    return VCDData(
        source_file=str(path),
        timescale=timescale_str,
        time_unit_ps=time_unit_ps,
        signals=signals,
        signal_count=signal_count,
        truncated_signals=truncated_signals,
        parser_backend="pywellen",
        tool_status="ok",
    )


def _parse_with_vcdvcd(path: Path, signal_filter: Optional[List[str]]) -> VCDData:
    from vcdvcd import VCDVCD  # optional dependency

    vcd = VCDVCD(str(path))

    timescale_str = ""
    raw_timescale = getattr(vcd, "timescale", None)
    if isinstance(raw_timescale, dict):
        timescale_str = str(raw_timescale.get("timescale") or raw_timescale.get("unittime") or "")
    elif raw_timescale:
        timescale_str = str(raw_timescale)
    time_unit_ps = _timescale_to_ps_multiplier(timescale_str)

    all_names = list(vcd.signals)
    signal_count = len(all_names)

    signals = {}
    truncated_signals: List[str] = []

    for full_name in all_names:
        if not _keep_signal(full_name, signal_filter):
            continue
        if len(signals) >= MAX_SIGNALS:
            truncated_signals.append(full_name)
            continue

        ref = vcd[full_name]
        tv_pairs = list(getattr(ref, "tv", []))
        truncated = len(tv_pairs) > MAX_TRANSITIONS_PER_SIGNAL
        transitions = []
        has_x = has_z = False
        for time_val, value in tv_pairs[:MAX_TRANSITIONS_PER_SIGNAL]:
            value_str = str(value)
            if "x" in value_str.lower():
                has_x = True
            if "z" in value_str.lower():
                has_z = True
            transitions.append(VCDTransition(
                time_ps=int(time_val) * time_unit_ps, value=value_str,
            ))

        width = 1
        try:
            width = int(getattr(ref, "size", 1))
        except (TypeError, ValueError):
            pass

        signals[full_name] = VCDSignalWave(
            name=full_name.rsplit(".", 1)[-1],
            hierarchy=full_name,
            width=width,
            transitions=transitions,
            has_x=has_x,
            has_z=has_z,
            truncated=truncated,
        )

    return VCDData(
        source_file=str(path),
        timescale=timescale_str,
        time_unit_ps=time_unit_ps,
        signals=signals,
        signal_count=signal_count,
        truncated_signals=truncated_signals,
        parser_backend="vcdvcd",
        tool_status="ok",
    )
