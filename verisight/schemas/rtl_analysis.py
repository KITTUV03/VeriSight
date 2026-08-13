"""
Pydantic schemas for RTL Root Cause Analysis (Agent 3 output).

Contains schemas for all 7 analysis sub-modules:
1. X-Tracer (xtrace.json)
2. Functional Analyzer (functional.json)
3. CDC Analyzer (cdc.json)
4. Lint Analyzer (lint.json)
5. Structural Analyzer (structure.json)
6. Protocol Compliance (protocol.json)
7. Misc Analyzer (misc.json)
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ─── Module 1: X-Tracer ────────────────────────────────────────────

class XPropagationPath(BaseModel):
    """A path of X propagation through the design."""
    origin_signal: str = Field(description="Signal where X originates")
    origin_module: str = Field(default="", description="Module containing origin")
    origin_cause: str = Field(
        default="",
        description="Cause: uninitialized/tristate/multi_driver/undefined_input"
    )
    propagation_chain: List[str] = Field(
        default_factory=list,
        description="Signals X propagates through, in order"
    )
    affected_outputs: List[str] = Field(
        default_factory=list,
        description="Output signals affected by this X"
    )
    line_number: int = Field(default=0, description="Line where X originates")
    file: str = Field(default="", description="Source file")


class XTracerTraceResult(BaseModel):
    """
    A single real x-tracer trace result: the backward cause tree for one
    (signal, time) query, run against an actual gate-level netlist + VCD
    (as opposed to the static heuristic analysis above).
    """
    query_signal: str = Field(description="Signal path queried (e.g. 'tb.dut.result[3]')")
    query_time_ps: int = Field(description="Query time in picoseconds")
    root_cause_type: str = Field(
        default="",
        description="x-tracer root cause classification: primary_input/uninit_ff/"
                    "x_injection/sequential_capture/clock_x/async_control_x/"
                    "multi_driver/x_propagation/unknown_cell"
    )
    summary: str = Field(default="", description="Human-readable summary of the trace")
    cause_tree: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw x-tracer JSON cause tree"
    )


class XTraceResult(BaseModel):
    """X-Tracer analysis results (xtrace.json)."""
    x_origins: List[XPropagationPath] = Field(
        default_factory=list,
        description="All identified X origins and propagation paths"
    )
    uninitialized_registers: List[str] = Field(
        default_factory=list,
        description="Registers without reset/initial values"
    )
    uninitialized_memories: List[str] = Field(
        default_factory=list,
        description="Memories without initialization"
    )
    tristate_signals: List[str] = Field(
        default_factory=list,
        description="Tri-state signals"
    )
    multi_driven_signals: List[str] = Field(
        default_factory=list,
        description="Signals with multiple drivers"
    )
    severity: str = Field(default="none", description="Overall severity: none/low/medium/high/critical")
    summary: str = Field(default="", description="Human-readable summary")
    real_traces: List[XTracerTraceResult] = Field(
        default_factory=list,
        description="Real x-tracer traces (netlist + VCD backed), when enabled"
    )
    vcd_evidence: List[str] = Field(
        default_factory=list,
        description="Lightweight VCD-derived evidence (signal=X/Z near a query time), "
                    "available even when the real x-tracer binary isn't installed"
    )
    tool_status: str = Field(
        default="disabled",
        description="Real x-tracer tool status: disabled/skipped_no_vcd/"
                    "skipped_not_installed/skipped_no_query/error/ok"
    )
    tool_message: str = Field(
        default="",
        description="Human-readable explanation of tool_status"
    )


# ─── Module 2: Functional Analyzer ─────────────────────────────────

class FunctionalIssue(BaseModel):
    """A functional discrepancy between spec and RTL."""
    issue_type: str = Field(
        description="Type: missing_state/wrong_condition/missing_default/"
                    "incorrect_arithmetic/wrong_priority/missing_reset/"
                    "illegal_transition/logic_error"
    )
    description: str = Field(description="Issue description")
    spec_requirement: str = Field(
        default="", description="Related spec requirement"
    )
    rtl_implementation: str = Field(
        default="", description="What RTL actually does"
    )
    module: str = Field(default="", description="Affected module")
    signal: str = Field(default="", description="Affected signal")
    file: str = Field(default="", description="Source file")
    line_number: int = Field(default=0, description="Line number")
    code_snippet: str = Field(default="", description="Relevant code snippet")
    severity: str = Field(default="medium", description="Severity: low/medium/high/critical")


class FunctionalResult(BaseModel):
    """Functional analysis results (functional.json)."""
    issues: List[FunctionalIssue] = Field(
        default_factory=list,
        description="All functional issues found"
    )
    spec_coverage: Dict[str, bool] = Field(
        default_factory=dict,
        description="Spec requirements → implemented (True/False)"
    )
    summary: str = Field(default="", description="Human-readable summary")


# ─── Module 3: CDC Analyzer ────────────────────────────────────────

class CDCIssue(BaseModel):
    """A clock domain crossing issue."""
    issue_type: str = Field(
        description="Type: unsynchronized_crossing/missing_synchronizer/"
                    "async_reset/metastability_risk/reconvergence"
    )
    description: str = Field(description="Issue description")
    source_domain: str = Field(default="", description="Source clock domain")
    destination_domain: str = Field(default="", description="Destination clock domain")
    signal: str = Field(default="", description="Signal crossing domains")
    module: str = Field(default="", description="Module name")
    file: str = Field(default="", description="Source file")
    line_number: int = Field(default=0)
    severity: str = Field(default="high")


class CDCResult(BaseModel):
    """CDC analysis results (cdc.json)."""
    clock_domains: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Identified clock domains [{name, clock, signals}]"
    )
    crossings: List[CDCIssue] = Field(
        default_factory=list,
        description="CDC issues found"
    )
    async_resets: List[str] = Field(
        default_factory=list,
        description="Asynchronous reset signals"
    )
    summary: str = Field(default="", description="Human-readable summary")


# ─── Module 4: Lint Analyzer ───────────────────────────────────────

class LintIssue(BaseModel):
    """A lint/coding style issue."""
    issue_type: str = Field(
        description="Type: inferred_latch/unused_variable/width_mismatch/"
                    "implicit_net/incomplete_case/blocking_nonblocking_misuse/"
                    "constant_condition/dead_code/undriven_signal/missing_sensitivity"
    )
    description: str = Field(description="Issue description")
    signal: str = Field(default="", description="Affected signal")
    module: str = Field(default="", description="Module name")
    file: str = Field(default="", description="Source file")
    line_number: int = Field(default=0)
    code_snippet: str = Field(default="", description="Relevant code")
    severity: str = Field(default="medium")


class LintResult(BaseModel):
    """Lint analysis results (lint.json)."""
    issues: List[LintIssue] = Field(
        default_factory=list,
        description="All lint issues found"
    )
    issue_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count per issue type"
    )
    summary: str = Field(default="", description="Human-readable summary")


# ─── Module 5: Structural Analyzer ─────────────────────────────────

class StructuralIssue(BaseModel):
    """A structural design issue."""
    issue_type: str = Field(
        description="Type: dead_state/unreachable_logic/combinational_loop/"
                    "multiple_drivers/floating_input/unconnected_output"
    )
    description: str = Field(description="Issue description")
    module: str = Field(default="", description="Module name")
    element: str = Field(default="", description="Affected element (state, signal, etc.)")
    file: str = Field(default="", description="Source file")
    line_number: int = Field(default=0)
    severity: str = Field(default="medium")


class StructuralResult(BaseModel):
    """Structural analysis results (structure.json)."""
    issues: List[StructuralIssue] = Field(
        default_factory=list,
        description="All structural issues found"
    )
    fsm_analysis: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="FSM analysis [{name, total_states, reachable_states, dead_states}]"
    )
    summary: str = Field(default="", description="Human-readable summary")


# ─── Module 6: Protocol Compliance ─────────────────────────────────

class ProtocolIssue(BaseModel):
    """A protocol compliance issue."""
    protocol: str = Field(description="Protocol: APB/AHB/AXI/Wishbone/Custom")
    rule: str = Field(description="Violated rule")
    description: str = Field(description="Issue description")
    signal: str = Field(default="", description="Signal involved")
    module: str = Field(default="", description="Module name")
    file: str = Field(default="", description="Source file")
    line_number: int = Field(default=0)
    severity: str = Field(default="high")


class ProtocolResult(BaseModel):
    """Protocol compliance results (protocol.json)."""
    detected_protocols: List[str] = Field(
        default_factory=list,
        description="Protocols detected in the design"
    )
    issues: List[ProtocolIssue] = Field(
        default_factory=list,
        description="Protocol violations found"
    )
    summary: str = Field(default="", description="Human-readable summary")


# ─── Module 7: Misc Analyzer ───────────────────────────────────────

class MiscIssue(BaseModel):
    """A miscellaneous design issue."""
    issue_type: str = Field(
        description="Type: timing_assumption/reset_sequencing/"
                    "initialization/race_condition/power_domain"
    )
    description: str = Field(description="Issue description")
    module: str = Field(default="", description="Module name")
    signal: str = Field(default="", description="Signal involved")
    file: str = Field(default="", description="Source file")
    line_number: int = Field(default=0)
    severity: str = Field(default="low")


class MiscResult(BaseModel):
    """Miscellaneous analysis results (misc.json)."""
    issues: List[MiscIssue] = Field(
        default_factory=list,
        description="Miscellaneous issues found"
    )
    summary: str = Field(default="", description="Human-readable summary")


# ─── Aggregated RTL Analysis ───────────────────────────────────────

class RTLAnalysis(BaseModel):
    """
    Aggregated RTL analysis across all 7 sub-modules.
    Combined output from Agent 3.
    """
    xtrace: XTraceResult = Field(
        default_factory=XTraceResult,
        description="X propagation analysis"
    )
    functional: FunctionalResult = Field(
        default_factory=FunctionalResult,
        description="Functional analysis"
    )
    cdc: CDCResult = Field(
        default_factory=CDCResult,
        description="CDC analysis"
    )
    lint: LintResult = Field(
        default_factory=LintResult,
        description="Lint analysis"
    )
    structural: StructuralResult = Field(
        default_factory=StructuralResult,
        description="Structural analysis"
    )
    protocol: ProtocolResult = Field(
        default_factory=ProtocolResult,
        description="Protocol compliance"
    )
    misc: MiscResult = Field(
        default_factory=MiscResult,
        description="Miscellaneous analysis"
    )
    primary_root_cause: str = Field(
        default="",
        description="Primary root cause identified across all modules"
    )
    primary_category: str = Field(
        default="",
        description="Category of primary root cause"
    )
    confidence: int = Field(
        default=0, ge=0, le=100,
        description="Overall confidence in analysis"
    )
