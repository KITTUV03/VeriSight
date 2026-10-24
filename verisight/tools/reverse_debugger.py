"""
Hardware Reverse-Debugger & Backward Cycle-Stepping Engine.

Inspired by:
1. hgdb: Hardware Generator Debugger with reverse-debugging & trace replay
   https://github.com/Kuree/hgdb
2. veridebugger: VCD backward signal dependency tracer
   https://github.com/hernantech/veridebugger
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from verisight.schemas.vcd_schema import VCDData, VCDSignalWave, VCDTransition
from verisight.utils.logger import get_logger

logger = get_logger("reverse_debugger")


class BackwardStep(BaseModel):
    """A single cycle or transition stepped backward from the failure."""
    cycle_index: int
    time_ps: int
    signal_name: str
    previous_value: str
    current_value: str
    is_corruption_edge: bool = False
    notes: str = ""


class ReverseTraceResult(BaseModel):
    """Result of backward trace execution from a failure timestamp."""
    tool_status: str = "ok"
    target_signal: str
    failure_time_ps: int
    corruption_time_ps: Optional[int] = None
    backward_steps: List[BackwardStep] = Field(default_factory=list)
    root_cause_summary: str = ""


def trace_backward_from_failure(
    vcd_data: Optional[VCDData],
    target_signal: str,
    failure_time_ps: int,
    max_steps: int = 20,
) -> ReverseTraceResult:
    """
    Steps backward in time from a failure timestamp to isolate the transition of origin.

    Args:
        vcd_data: Parsed waveform data.
        target_signal: Signal whose corruption is under investigation.
        failure_time_ps: Time when mismatch/error was detected.
        max_steps: Maximum backward transitions to inspect.

    Returns:
        ReverseTraceResult documenting the corruption origin.
    """
    if not vcd_data or not vcd_data.signals:
        return ReverseTraceResult(
            tool_status="no_waveform",
            target_signal=target_signal,
            failure_time_ps=failure_time_ps,
            root_cause_summary="Waveform data not available for backward trace.",
        )

    # Locate the signal in VCD hierarchy
    matched_wave: Optional[VCDSignalWave] = None
    matched_key: str = target_signal

    for k, wave in vcd_data.signals.items():
        if k == target_signal or k.endswith(f".{target_signal}") or target_signal in k:
            matched_wave = wave
            matched_key = k
            break

    if not matched_wave or not matched_wave.transitions:
        return ReverseTraceResult(
            tool_status="signal_not_found",
            target_signal=target_signal,
            failure_time_ps=failure_time_ps,
            root_cause_summary=f"Signal '{target_signal}' not found in waveform transitions.",
        )

    # Filter transitions at or before failure_time_ps
    prior_transitions = [tr for tr in matched_wave.transitions if tr.time_ps <= failure_time_ps]
    if not prior_transitions:
        return ReverseTraceResult(
            tool_status="no_prior_transitions",
            target_signal=matched_key,
            failure_time_ps=failure_time_ps,
            root_cause_summary="No transitions observed prior to failure timestamp.",
        )

    steps: List[BackwardStep] = []
    corruption_ps = None
    step_idx = 0

    # Step backward through transitions
    for i in range(len(prior_transitions) - 1, max(-1, len(prior_transitions) - 1 - max_steps), -1):
        curr_tr = prior_transitions[i]
        prev_val = prior_transitions[i - 1].value if i > 0 else "initial"

        is_corrupt = False
        notes = []
        if "x" in curr_tr.value.lower() and "x" not in prev_val.lower():
            is_corrupt = True
            notes.append("Signal transitioned to X state (uninitialized / contention)")
        elif i == len(prior_transitions) - 1:
            notes.append("Failure observation point")

        if is_corrupt and corruption_ps is None:
            corruption_ps = curr_tr.time_ps

        steps.append(BackwardStep(
            cycle_index=step_idx,
            time_ps=curr_tr.time_ps,
            signal_name=matched_key,
            previous_value=prev_val,
            current_value=curr_tr.value,
            is_corruption_edge=is_corrupt,
            notes="; ".join(notes),
        ))
        step_idx += 1

    summary = (
        f"Reverse trace isolated corruption on '{matched_key}' back to {corruption_ps} ps."
        if corruption_ps is not None
        else f"Reverse trace inspected {len(steps)} transitions prior to failure timestamp {failure_time_ps} ps."
    )

    return ReverseTraceResult(
        tool_status="ok",
        target_signal=matched_key,
        failure_time_ps=failure_time_ps,
        corruption_time_ps=corruption_ps,
        backward_steps=steps,
        root_cause_summary=summary,
    )
