"""
Pydantic schema for parsed VCD waveform data (vcd_summary.json).

This is VeriSight's own post-processed view of a VCD file — distinct from
the raw VCD handed to x-tracer's subprocess. It exists to give Agent 2 and
Agent 3 a compact, queryable summary of signal activity (especially X/Z
values) without requiring the real x-tracer tool to be installed.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class VCDTransition(BaseModel):
    """A single value change on a signal."""
    time_ps: int = Field(description="Transition time, normalized to picoseconds")
    value: str = Field(description="New value as a binary/hex string, e.g. '1010', 'x', 'z'")


class VCDSignalWave(BaseModel):
    """Post-processed transition history for one signal."""
    name: str = Field(description="Short (leaf) signal name")
    hierarchy: str = Field(description="Full hierarchical path, e.g. 'tb.dut.fifo_count'")
    width: int = Field(default=1, description="Signal bit width")
    transitions: List[VCDTransition] = Field(default_factory=list)
    has_x: bool = Field(default=False, description="Signal takes an X value at least once")
    has_z: bool = Field(default=False, description="Signal takes a Z value at least once")
    truncated: bool = Field(
        default=False,
        description="True if transitions were capped (see VCDData.truncated_signals)"
    )

    def value_at(self, time_ps: int) -> Optional[str]:
        """Value of this signal at time_ps (the value of the last transition <= time_ps)."""
        value = None
        for t in self.transitions:
            if t.time_ps > time_ps:
                break
            value = t.value
        return value

    def transitions_near(self, time_ps: int, window_ps: int) -> List[VCDTransition]:
        """Transitions within [time_ps - window_ps, time_ps + window_ps]."""
        lo, hi = time_ps - window_ps, time_ps + window_ps
        return [t for t in self.transitions if lo <= t.time_ps <= hi]


class VCDData(BaseModel):
    """Post-processed VCD waveform, keyed by full hierarchical signal path."""
    source_file: str = Field(default="")
    timescale: str = Field(default="", description="Raw timescale string from the VCD, e.g. '1ns'")
    time_unit_ps: int = Field(
        default=1000,
        description="Multiplier to convert the VCD's native time units to picoseconds"
    )
    signals: Dict[str, VCDSignalWave] = Field(default_factory=dict)
    signal_count: int = Field(default=0, description="Total signals found before any truncation")
    truncated_signals: List[str] = Field(
        default_factory=list,
        description="Signal paths dropped/capped to bound memory — never silently ignored"
    )
    parser_backend: str = Field(default="", description="'pywellen' | 'vcdvcd' | 'unavailable'")
    tool_status: str = Field(
        default="ok",
        description="ok/skipped_no_vcd/skipped_not_installed/error"
    )
    tool_message: str = Field(default="")

    def value_at(self, signal_path: str, time_ps: int) -> Optional[str]:
        sig = self.signals.get(signal_path)
        return sig.value_at(time_ps) if sig else None

    def transitions_near(self, signal_path: str, time_ps: int, window_ps: int = 5000) -> List[VCDTransition]:
        sig = self.signals.get(signal_path)
        return sig.transitions_near(time_ps, window_ps) if sig else []

    def find_matching_signals(self, name_fragment: str) -> List[str]:
        """Hierarchical paths whose leaf name or path contains name_fragment (case-insensitive)."""
        frag = name_fragment.lower()
        return [
            path for path, sig in self.signals.items()
            if frag in sig.name.lower() or frag in path.lower()
        ]

    def evidence_near_mismatches(
        self, field_names: List[str], time_ps_list: List[int], window_ps: int = 5000
    ) -> List[str]:
        """
        Human-readable evidence lines for Agent 2/3: for each (field, time) pair,
        report any matching signal that carries an X/Z value within the window.
        Used to corroborate log-derived scoreboard mismatches with real waveform data.
        """
        evidence: List[str] = []
        if self.tool_status != "ok":
            return evidence

        for field, time_ps in zip(field_names, time_ps_list):
            for path in self.find_matching_signals(field):
                sig = self.signals[path]
                for t in sig.transitions_near(time_ps, window_ps):
                    if "x" in t.value.lower() or "z" in t.value.lower():
                        evidence.append(
                            f"VCD confirms signal '{path}' = {t.value} at {t.time_ps}ps "
                            f"(within {window_ps}ps of mismatch @ {time_ps}ps)"
                        )
        return evidence
