"""
Pydantic schema for Simulation Log knowledge (log.json).

Captures structured information extracted from UVM simulation log files,
including categorized log entries, assertion failures, timeouts,
scoreboard mismatches, and other simulation events.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "UVM_INFO"
    WARNING = "UVM_WARNING"
    ERROR = "UVM_ERROR"
    FATAL = "UVM_FATAL"
    ASSERTION_FAILURE = "ASSERTION_FAILURE"
    SYSTEM = "SYSTEM"
    UNKNOWN = "UNKNOWN"


class LogEntry(BaseModel):
    """A single log entry from the simulation log."""
    severity: str = Field(description="Severity: UVM_INFO/UVM_WARNING/UVM_ERROR/UVM_FATAL/ASSERTION_FAILURE/SYSTEM")
    timestamp: str = Field(default="", description="Simulation timestamp (e.g., '120 ns')")
    component: str = Field(default="", description="UVM component path")
    message: str = Field(description="Log message text")
    message_id: str = Field(default="", description="UVM message [ID] tag, e.g. 'SCB' (simulator-independent dedup key)")
    file: str = Field(default="", description="Source file reference")
    line: int = Field(default=0, description="Source line number")
    phase: str = Field(default="runtime", description="Failure stage: compile/elaboration/runtime")
    raw_line: str = Field(default="", description="Original raw log line")
    line_number_in_log: int = Field(default=0, description="Line number in the log file")


class ToolError(BaseModel):
    """A simulator-native compile/elaboration error (no UVM severity token)."""
    line_no: int = Field(default=0, description="1-based line number in the log")
    text: str = Field(default="", description="The error line text")
    stage: str = Field(default="compile", description="compile/elaboration")
    tool: str = Field(default="", description="Detected simulator (verilator/vcs/questa/xcelium/iverilog/generic)")


class FailureEvent(BaseModel):
    """A causally-ordered failure event (primary root anchor or cascade symptom)."""
    kind: str = Field(default="", description="compile_error/elaboration_error/fatal/error/assertion/mismatch")
    stage: str = Field(default="runtime", description="compile/elaboration/runtime")
    timestamp: str = Field(default="", description="Simulation timestamp string")
    time_ns: Optional[float] = Field(default=None, description="Timestamp normalised to nanoseconds (unit-aware)")
    message: str = Field(default="", description="Event message")
    file: str = Field(default="", description="Source file if known")
    line: int = Field(default=0, description="Source line if known")
    severity: str = Field(default="", description="Severity/kind token")
    log_line: int = Field(default=0, description="1-based line number in the log")
    rationale: str = Field(default="", description="Why this event was selected (primary only)")


class AssertionFailure(BaseModel):
    """An assertion failure event."""
    assertion_name: str = Field(default="", description="Assertion name/label")
    expression: str = Field(default="", description="Failed assertion expression")
    timestamp: str = Field(default="", description="Simulation timestamp")
    module: str = Field(default="", description="Module where assertion failed")
    file: str = Field(default="", description="Source file")
    line: int = Field(default=0, description="Line number")
    message: str = Field(default="", description="Failure message")


class ScoreboardMismatch(BaseModel):
    """A scoreboard comparison mismatch."""
    timestamp: str = Field(default="", description="Simulation timestamp")
    expected: str = Field(default="", description="Expected value")
    actual: str = Field(default="", description="Actual value")
    field: str = Field(default="", description="Field that mismatched")
    component: str = Field(default="", description="Scoreboard component path")
    message: str = Field(default="", description="Full mismatch message")
    transaction_id: str = Field(default="", description="Transaction ID if available")


class Timeout(BaseModel):
    """A simulation timeout event."""
    timestamp: str = Field(default="", description="Timestamp when timeout occurred")
    message: str = Field(default="", description="Timeout message")
    component: str = Field(default="", description="Component that timed out")
    phase: str = Field(default="", description="UVM phase at timeout")


class ConstraintFailure(BaseModel):
    """A constraint randomization failure."""
    timestamp: str = Field(default="", description="Simulation timestamp")
    class_name: str = Field(default="", description="Class with failed constraint")
    constraint_name: str = Field(default="", description="Constraint name")
    message: str = Field(default="", description="Failure message")


class NullPointer(BaseModel):
    """A null object access error."""
    timestamp: str = Field(default="", description="Simulation timestamp")
    variable: str = Field(default="", description="Null variable name")
    component: str = Field(default="", description="Component path")
    message: str = Field(default="", description="Error message")


class FactoryError(BaseModel):
    """A UVM factory error."""
    timestamp: str = Field(default="", description="Simulation timestamp")
    type_name: str = Field(default="", description="Type that caused error")
    message: str = Field(default="", description="Error message")


class ConfigDBFailure(BaseModel):
    """A config_db get failure."""
    timestamp: str = Field(default="", description="Simulation timestamp")
    field_name: str = Field(default="", description="Config field name")
    component: str = Field(default="", description="Component path")
    message: str = Field(default="", description="Error message")


class TLMFailure(BaseModel):
    """A TLM connection or communication failure."""
    timestamp: str = Field(default="", description="Simulation timestamp")
    port: str = Field(default="", description="Port name")
    component: str = Field(default="", description="Component path")
    message: str = Field(default="", description="Error message")


class PhaseDeadlock(BaseModel):
    """A UVM phase deadlock event."""
    phase: str = Field(default="", description="Phase name")
    components: List[str] = Field(
        default_factory=list, description="Components involved"
    )
    message: str = Field(default="", description="Deadlock message")


class ProtocolViolation(BaseModel):
    """A protocol violation detected during simulation."""
    timestamp: str = Field(default="", description="Simulation timestamp")
    protocol: str = Field(default="", description="Protocol name")
    rule: str = Field(default="", description="Violated rule")
    signal: str = Field(default="", description="Signal involved")
    message: str = Field(default="", description="Violation message")


class SimulationSummary(BaseModel):
    """Simulation result summary."""
    total_info: int = Field(default=0, description="Total UVM_INFO count")
    total_warnings: int = Field(default=0, description="Total UVM_WARNING count")
    total_errors: int = Field(default=0, description="Total UVM_ERROR count")
    total_fatals: int = Field(default=0, description="Total UVM_FATAL count")
    simulation_time: str = Field(default="", description="Total simulation time")
    pass_fail: str = Field(default="UNKNOWN", description="Overall PASS/FAIL status")
    failure_stage: str = Field(default="none", description="Earliest stage that failed: compile/elaboration/runtime/none")
    seed: str = Field(default="", description="Random seed used")


class LogKnowledge(BaseModel):
    """
    Complete simulation log knowledge. Output schema for log.json.
    """
    entries: List[LogEntry] = Field(
        default_factory=list, description="All parsed log entries"
    )
    errors: List[LogEntry] = Field(
        default_factory=list, description="UVM_ERROR entries"
    )
    fatals: List[LogEntry] = Field(
        default_factory=list, description="UVM_FATAL entries"
    )
    warnings: List[LogEntry] = Field(
        default_factory=list, description="UVM_WARNING entries"
    )
    assertion_failures: List[AssertionFailure] = Field(
        default_factory=list, description="Assertion failure events"
    )
    scoreboard_mismatches: List[ScoreboardMismatch] = Field(
        default_factory=list, description="Scoreboard mismatch events"
    )
    timeouts: List[Timeout] = Field(
        default_factory=list, description="Timeout events"
    )
    constraint_failures: List[ConstraintFailure] = Field(
        default_factory=list, description="Constraint randomization failures"
    )
    null_pointers: List[NullPointer] = Field(
        default_factory=list, description="Null pointer access errors"
    )
    factory_errors: List[FactoryError] = Field(
        default_factory=list, description="UVM factory errors"
    )
    config_db_failures: List[ConfigDBFailure] = Field(
        default_factory=list, description="Config DB failures"
    )
    tlm_failures: List[TLMFailure] = Field(
        default_factory=list, description="TLM failures"
    )
    phase_deadlocks: List[PhaseDeadlock] = Field(
        default_factory=list, description="Phase deadlocks"
    )
    protocol_violations: List[ProtocolViolation] = Field(
        default_factory=list, description="Protocol violations"
    )
    summary: SimulationSummary = Field(
        default_factory=SimulationSummary,
        description="Overall simulation summary"
    )
    tool_errors: List[ToolError] = Field(
        default_factory=list,
        description="Simulator-native compile/elaboration errors (non-UVM)"
    )
    primary_event: Optional[FailureEvent] = Field(
        default=None,
        description="Earliest causally-relevant failure — the root-cause anchor"
    )
    cascade_events: List[FailureEvent] = Field(
        default_factory=list,
        description="Later events that are candidate downstream symptoms of the primary"
    )
    log_file: str = Field(default="", description="Source log file path")
    total_lines: int = Field(default=0, description="Total lines in log file")
