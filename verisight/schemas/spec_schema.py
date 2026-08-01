"""
Pydantic schema for Design Specification knowledge (spec.json).

Captures all structured information extracted from a design specification
document, including functional requirements, timing, reset behavior,
protocol rules, register maps, state machines, and corner cases.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """A single functional or design requirement."""
    id: str = Field(description="Requirement identifier (e.g., REQ-001)")
    description: str = Field(description="Requirement description")
    section: str = Field(default="", description="Specification section reference")
    priority: str = Field(default="normal", description="Priority: critical/high/normal/low")
    category: str = Field(default="functional", description="Category: functional/timing/reset/protocol")


class TimingRequirement(BaseModel):
    """Timing constraint from the specification."""
    signal: str = Field(description="Signal or interface name")
    constraint: str = Field(description="Timing constraint description")
    value: str = Field(default="", description="Numeric value if applicable")
    unit: str = Field(default="ns", description="Time unit")
    section: str = Field(default="", description="Spec section reference")


class ResetBehavior(BaseModel):
    """Reset behavior specification."""
    reset_signal: str = Field(description="Reset signal name")
    active_level: str = Field(default="low", description="Active level: high/low")
    type: str = Field(default="synchronous", description="Reset type: synchronous/asynchronous")
    affected_signals: List[str] = Field(default_factory=list, description="Signals affected by reset")
    reset_values: Dict[str, str] = Field(default_factory=dict, description="Signal → reset value mapping")
    section: str = Field(default="", description="Spec section reference")


class ProtocolRule(BaseModel):
    """Protocol compliance rule."""
    protocol: str = Field(description="Protocol name (APB, AHB, AXI, etc.)")
    rule_id: str = Field(default="", description="Rule identifier")
    description: str = Field(description="Rule description")
    signal_conditions: List[str] = Field(default_factory=list, description="Signal conditions that must hold")
    section: str = Field(default="", description="Spec section reference")


class RegisterField(BaseModel):
    """A field within a register."""
    name: str = Field(description="Field name")
    bits: str = Field(description="Bit range (e.g., '7:0')")
    access: str = Field(default="RW", description="Access type: RW/RO/WO/W1C/etc.")
    reset_value: str = Field(default="0x0", description="Reset value")
    description: str = Field(default="", description="Field description")


class RegisterDescription(BaseModel):
    """Register description from the specification."""
    name: str = Field(description="Register name")
    address: str = Field(default="", description="Register address")
    width: int = Field(default=32, description="Register width in bits")
    fields: List[RegisterField] = Field(default_factory=list, description="Register fields")
    description: str = Field(default="", description="Register description")
    section: str = Field(default="", description="Spec section reference")


class StateTransition(BaseModel):
    """A single state transition in an FSM."""
    from_state: str = Field(description="Source state")
    to_state: str = Field(description="Destination state")
    condition: str = Field(description="Transition condition")
    actions: List[str] = Field(default_factory=list, description="Actions on transition")


class StateMachineSpec(BaseModel):
    """State machine specification."""
    name: str = Field(description="FSM name")
    states: List[str] = Field(default_factory=list, description="List of states")
    initial_state: str = Field(default="", description="Initial/reset state")
    transitions: List[StateTransition] = Field(default_factory=list, description="State transitions")
    section: str = Field(default="", description="Spec section reference")


class CornerCase(BaseModel):
    """Corner case or boundary condition."""
    description: str = Field(description="Corner case description")
    expected_behavior: str = Field(default="", description="Expected behavior")
    section: str = Field(default="", description="Spec section reference")


class IllegalCondition(BaseModel):
    """Illegal or forbidden condition."""
    description: str = Field(description="Illegal condition description")
    expected_response: str = Field(default="", description="How design should respond")
    section: str = Field(default="", description="Spec section reference")


class SpecKnowledge(BaseModel):
    """
    Complete structured knowledge extracted from a design specification.
    This is the output schema for spec.json.
    """
    title: str = Field(default="", description="Specification title")
    version: str = Field(default="", description="Specification version")
    raw_sections: Dict[str, str] = Field(
        default_factory=dict,
        description="Raw section text keyed by heading"
    )
    functional_requirements: List[Requirement] = Field(
        default_factory=list,
        description="Functional requirements"
    )
    timing_requirements: List[TimingRequirement] = Field(
        default_factory=list,
        description="Timing requirements"
    )
    reset_behavior: List[ResetBehavior] = Field(
        default_factory=list,
        description="Reset behavior specifications"
    )
    protocol_rules: List[ProtocolRule] = Field(
        default_factory=list,
        description="Protocol compliance rules"
    )
    address_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Address map"
    )
    register_descriptions: List[RegisterDescription] = Field(
        default_factory=list,
        description="Register descriptions"
    )
    state_machines: List[StateMachineSpec] = Field(
        default_factory=list,
        description="State machine specifications"
    )
    corner_cases: List[CornerCase] = Field(
        default_factory=list,
        description="Corner cases and boundary conditions"
    )
    illegal_conditions: List[IllegalCondition] = Field(
        default_factory=list,
        description="Illegal/forbidden conditions"
    )
