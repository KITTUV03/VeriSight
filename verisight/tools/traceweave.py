"""
TraceWeave Evidence-Driven Debugging Engine for VeriSight.

Inspired by and compatible with the concepts of:
gokeshenzhen/TraceWeave (https://github.com/gokeshenzhen/TraceWeave)
An evidence-driven Model Context Protocol (MCP) server for RTL/UVM simulation debugging.

Correlates:
1. Simulation Log events (UVM_ERROR, mismatches, SVA assertion failures, fatal errors).
2. Waveform states (VCD/FSDB) at failure timestamps.
3. RTL AST and hierarchical driver definitions (identifying driving logic).
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from verisight.schemas.log_schema import LogKnowledge, LogEntry
from verisight.schemas.vcd_schema import VCDData, VCDSignalWave, VCDTransition
from verisight.schemas.rtl_schema import RTLKnowledge
from verisight.utils.logger import get_logger

logger = get_logger("traceweave")


class WaveformSnapshot(BaseModel):
    """Snapshot of related signals at a specific simulation timestamp."""
    time_ps: int
    signal_values: Dict[str, str] = Field(default_factory=dict)
    active_x_signals: List[str] = Field(default_factory=list)


class CorrelatedFailure(BaseModel):
    """A simulation failure correlated with waveform and RTL source evidence."""
    error_index: int
    message: str
    timestamp_ps: Optional[int] = None
    suspect_signals: List[str] = Field(default_factory=list)
    rtl_driver_locations: List[Dict[str, Any]] = Field(default_factory=list)
    waveform_snapshot: Optional[WaveformSnapshot] = None
    correlation_confidence: float = 0.0
    evidence_notes: List[str] = Field(default_factory=list)


class TraceWeaveReport(BaseModel):
    """Aggregated evidence-driven debugging report from TraceWeave."""
    tool_status: str = "ok"
    failures_analyzed: int = 0
    correlated_failures: List[CorrelatedFailure] = Field(default_factory=list)
    key_culprit_signals: List[str] = Field(default_factory=list)
    summary: str = ""


def correlate_failure_evidence(
    log_data: Optional[LogKnowledge],
    vcd_data: Optional[VCDData],
    rtl_data: Optional[RTLKnowledge],
    time_window_ps: int = 50_000,
) -> TraceWeaveReport:
    """
    Correlates simulation log errors with waveform transitions and RTL drivers.

    Args:
        log_data: Parsed simulation log containing errors and timestamps.
        vcd_data: Parsed waveform data (via pywellen or vcdvcd).
        rtl_data: Parsed RTL knowledge with AST, ports, and always blocks.
        time_window_ps: Search window around failure timestamp (default 50ns).

    Returns:
        TraceWeaveReport with correlated root-cause evidence.
    """
    if not log_data or not log_data.errors:
        return TraceWeaveReport(
            tool_status="no_errors",
            summary="No simulation errors found in log for TraceWeave correlation.",
        )

    correlated: List[CorrelatedFailure] = []
    culprit_counts: Dict[str, int] = {}

    for idx, err in enumerate(log_data.errors[:10]):  # Analyze top 10 errors
        t_ps = getattr(err, "timestamp_ps", None)
        if t_ps is None and hasattr(err, "timestamp") and err.timestamp:
            try:
                # Handle nanoseconds timestamp in log
                t_ps = int(err.timestamp) * 1_000
            except (ValueError, TypeError):
                t_ps = None

        suspects: List[str] = []
        msg = err.message or ""

        # Extract signal candidates mentioned in error or mismatch
        if vcd_data and vcd_data.signals:
            for sig_name in vcd_data.signals.keys():
                leaf = sig_name.rsplit(".", 1)[-1]
                if leaf in msg and len(leaf) > 2:
                    if sig_name not in suspects:
                        suspects.append(sig_name)

        # Snapshot waveform values around t_ps
        snapshot = None
        if vcd_data and vcd_data.signals and t_ps is not None:
            sig_vals: Dict[str, str] = {}
            x_sigs: List[str] = []

            for s_name, s_wave in vcd_data.signals.items():
                if suspects and s_name not in suspects and not any(sus in s_name for sus in suspects):
                    continue
                # Find value at t_ps
                val = "x"
                for tr in s_wave.transitions:
                    if tr.time_ps <= t_ps:
                        val = tr.value
                    else:
                        break
                sig_vals[s_name] = val
                if "x" in val.lower():
                    x_sigs.append(s_name)

            snapshot = WaveformSnapshot(
                time_ps=t_ps,
                signal_values=sig_vals,
                active_x_signals=x_sigs,
            )

        # Correlate with RTL AST drivers
        driver_locs: List[Dict[str, Any]] = []
        if rtl_data and rtl_data.modules:
            for mod in rtl_data.modules:
                for block in getattr(mod, "always_blocks", []):
                    block_vars = (
                        getattr(block, "signals_written", [])
                        or getattr(block, "signals_read", [])
                        or getattr(block, "assigned_signals", [])
                        or getattr(block, "signals", [])
                    )
                    for sus in suspects:
                        leaf = sus.rsplit(".", 1)[-1]
                        if leaf in block_vars:
                            driver_locs.append({
                                "module": mod.name,
                                "signal": leaf,
                                "line": getattr(block, "line_number", 0),
                                "block_type": getattr(block, "block_type", "always"),
                            })

        # Calculate confidence
        notes = []
        conf = 0.5
        if t_ps is not None:
            conf += 0.2
            notes.append(f"Precise simulation failure timestamp located at {t_ps} ps.")
        if snapshot and snapshot.active_x_signals:
            conf += 0.2
            notes.append(f"Observed X-state on signals: {', '.join(snapshot.active_x_signals[:3])}")
        if driver_locs:
            conf += 0.1
            notes.append(f"Linked to {len(driver_locs)} RTL always-block drivers.")

        for s in suspects:
            culprit_counts[s] = culprit_counts.get(s, 0) + 1

        correlated.append(CorrelatedFailure(
            error_index=idx,
            message=msg,
            timestamp_ps=t_ps,
            suspect_signals=suspects,
            rtl_driver_locations=driver_locs,
            waveform_snapshot=snapshot,
            correlation_confidence=min(1.0, conf),
            evidence_notes=notes,
        ))

    top_culprits = sorted(culprit_counts.keys(), key=lambda k: culprit_counts[k], reverse=True)[:5]
    summary_msg = f"TraceWeave correlated {len(correlated)} error events across waveforms and RTL AST."

    return TraceWeaveReport(
        tool_status="ok",
        failures_analyzed=len(correlated),
        correlated_failures=correlated,
        key_culprit_signals=top_culprits,
        summary=summary_msg,
    )
