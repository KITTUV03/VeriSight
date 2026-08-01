"""
Pydantic schema for RTL knowledge (rtl.json).

Captures structured information extracted from SystemVerilog RTL source
files, including module hierarchy, ports, always blocks, FSMs, clock
domains, reset logic, and inline assertions.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class PortDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"


class SignalType(str, Enum):
    WIRE = "wire"
    REG = "reg"
    LOGIC = "logic"
    INTEGER = "integer"
    PARAMETER = "parameter"
    LOCALPARAM = "localparam"


class Port(BaseModel):
    """A module port."""
    name: str = Field(description="Port name")
    direction: str = Field(description="Port direction: input/output/inout")
    width: str = Field(default="1", description="Port width (e.g., '8', '[7:0]')")
    signal_type: str = Field(default="logic", description="Signal type: wire/reg/logic")
    description: str = Field(default="", description="Port description from comments")


class Parameter(BaseModel):
    """A module parameter or localparam."""
    name: str = Field(description="Parameter name")
    value: str = Field(default="", description="Default value")
    param_type: str = Field(default="parameter", description="parameter/localparam")
    data_type: str = Field(default="", description="Data type if specified")


class AlwaysBlock(BaseModel):
    """An always block extracted from RTL."""
    block_type: str = Field(
        description="Block type: combinational/sequential/latch"
    )
    sensitivity_list: str = Field(
        default="", description="Sensitivity list (e.g., 'posedge clk')"
    )
    clock_signal: str = Field(default="", description="Clock signal if sequential")
    reset_signal: str = Field(default="", description="Reset signal if present")
    reset_active: str = Field(default="", description="Reset active level: high/low")
    signals_written: List[str] = Field(
        default_factory=list, description="Signals assigned in this block"
    )
    signals_read: List[str] = Field(
        default_factory=list, description="Signals read in this block"
    )
    has_reset: bool = Field(default=False, description="Whether block has reset logic")
    line_start: int = Field(default=0, description="Starting line number")
    line_end: int = Field(default=0, description="Ending line number")
    raw_code: str = Field(default="", description="Raw source code of the block")
    issues: List[str] = Field(
        default_factory=list,
        description="Detected issues (latch, missing default, etc.)"
    )


class FSMState(BaseModel):
    """An FSM state."""
    name: str = Field(description="State name")
    encoding: str = Field(default="", description="State encoding value")


class FSMTransition(BaseModel):
    """An FSM transition."""
    from_state: str = Field(description="Source state")
    to_state: str = Field(description="Destination state")
    condition: str = Field(default="", description="Transition condition")
    line_number: int = Field(default=0, description="Line number in source")


class FSM(BaseModel):
    """A finite state machine extracted from RTL."""
    name: str = Field(default="", description="FSM name (state variable name)")
    state_variable: str = Field(description="State register name")
    next_state_variable: str = Field(default="", description="Next-state variable name")
    states: List[FSMState] = Field(default_factory=list, description="FSM states")
    transitions: List[FSMTransition] = Field(default_factory=list, description="Transitions")
    has_default: bool = Field(default=False, description="Whether case has default")
    reset_state: str = Field(default="", description="Reset/initial state")


class ClockDomain(BaseModel):
    """A clock domain in the design."""
    clock_signal: str = Field(description="Clock signal name")
    signals: List[str] = Field(
        default_factory=list, description="Signals in this clock domain"
    )
    reset_signal: str = Field(default="", description="Associated reset signal")


class RTLAssertion(BaseModel):
    """An inline assertion in the RTL."""
    assertion_type: str = Field(
        description="Type: assert/assume/cover/restrict"
    )
    name: str = Field(default="", description="Assertion label")
    expression: str = Field(description="Assertion expression")
    line_number: int = Field(default=0, description="Line number in source")
    file: str = Field(default="", description="Source file")


class RTLModule(BaseModel):
    """
    Complete knowledge extracted from a single RTL module.
    """
    name: str = Field(description="Module name")
    file: str = Field(default="", description="Source file path")
    ports: List[Port] = Field(default_factory=list, description="Module ports")
    parameters: List[Parameter] = Field(default_factory=list, description="Parameters")
    always_blocks: List[AlwaysBlock] = Field(
        default_factory=list, description="Always blocks"
    )
    fsms: List[FSM] = Field(default_factory=list, description="Finite state machines")
    clock_domains: List[ClockDomain] = Field(
        default_factory=list, description="Clock domains"
    )
    assignments: List[str] = Field(
        default_factory=list, description="Continuous assignments"
    )
    instantiations: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Module instantiations [{module, instance, file}]"
    )
    assertions: List[RTLAssertion] = Field(
        default_factory=list, description="Inline assertions"
    )
    raw_source: str = Field(default="", description="Complete module source code")
    line_count: int = Field(default=0, description="Total lines in source file")


class RTLKnowledge(BaseModel):
    """
    Complete RTL knowledge across all modules. Output schema for rtl.json.
    """
    modules: List[RTLModule] = Field(
        default_factory=list, description="All parsed RTL modules"
    )
    top_module: str = Field(default="", description="Top-level module name")
    file_list: List[str] = Field(
        default_factory=list, description="List of all RTL source files"
    )
    total_lines: int = Field(default=0, description="Total lines across all files")
    global_issues: List[str] = Field(
        default_factory=list,
        description="Issues detected across the entire RTL codebase"
    )
