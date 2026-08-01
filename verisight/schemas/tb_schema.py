"""
Pydantic schema for UVM Testbench knowledge (tb.json).

Captures structured information extracted from UVM testbench source files,
including component hierarchy, transaction flow, TLM connections, factory
overrides, config DB usage, and coverage models.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TransactionField(BaseModel):
    """A field in a UVM transaction/sequence_item."""
    name: str = Field(description="Field name")
    field_type: str = Field(default="", description="Data type")
    constraint: str = Field(default="", description="Constraint expression if any")
    is_rand: bool = Field(default=False, description="Whether field is rand/randc")


class Transaction(BaseModel):
    """A UVM sequence item / transaction."""
    name: str = Field(description="Transaction class name")
    file: str = Field(default="", description="Source file")
    fields: List[TransactionField] = Field(
        default_factory=list, description="Transaction fields"
    )
    constraints: List[str] = Field(
        default_factory=list, description="Constraint blocks"
    )
    parent_class: str = Field(
        default="uvm_sequence_item", description="Parent class"
    )


class SequenceInfo(BaseModel):
    """A UVM sequence."""
    name: str = Field(description="Sequence class name")
    file: str = Field(default="", description="Source file")
    body_summary: str = Field(default="", description="Summary of body task")
    transaction_type: str = Field(default="", description="Transaction type used")
    parent_class: str = Field(default="uvm_sequence", description="Parent class")
    has_pre_body: bool = Field(default=False)
    has_post_body: bool = Field(default=False)


class DriverInfo(BaseModel):
    """A UVM driver."""
    name: str = Field(description="Driver class name")
    file: str = Field(default="", description="Source file")
    transaction_type: str = Field(default="", description="Transaction type driven")
    interface_signals: List[str] = Field(
        default_factory=list, description="Interface signals driven"
    )
    drive_logic_summary: str = Field(
        default="", description="Summary of driving logic"
    )
    raw_run_phase: str = Field(default="", description="Raw run_phase code")


class MonitorInfo(BaseModel):
    """A UVM monitor."""
    name: str = Field(description="Monitor class name")
    file: str = Field(default="", description="Source file")
    transaction_type: str = Field(default="", description="Transaction type sampled")
    interface_signals: List[str] = Field(
        default_factory=list, description="Interface signals sampled"
    )
    sampling_logic_summary: str = Field(
        default="", description="Summary of sampling logic"
    )
    analysis_port: str = Field(default="", description="Analysis port name")
    raw_run_phase: str = Field(default="", description="Raw run_phase code")


class ScoreboardInfo(BaseModel):
    """A UVM scoreboard."""
    name: str = Field(description="Scoreboard class name")
    file: str = Field(default="", description="Source file")
    prediction_logic: str = Field(
        default="", description="How expected values are computed"
    )
    comparison_logic: str = Field(
        default="", description="How actual vs expected are compared"
    )
    analysis_exports: List[str] = Field(
        default_factory=list, description="Analysis exports/imps"
    )
    raw_code: str = Field(default="", description="Raw scoreboard code")


class CoverageInfo(BaseModel):
    """A UVM coverage collector."""
    name: str = Field(description="Coverage class name")
    file: str = Field(default="", description="Source file")
    covergroups: List[str] = Field(
        default_factory=list, description="Covergroup names"
    )
    coverpoints: List[str] = Field(
        default_factory=list, description="Coverpoint names"
    )
    crosses: List[str] = Field(
        default_factory=list, description="Cross coverage names"
    )


class TLMConnection(BaseModel):
    """A TLM port connection."""
    source_component: str = Field(description="Source component")
    source_port: str = Field(description="Source port name")
    target_component: str = Field(description="Target component")
    target_port: str = Field(description="Target port/export name")


class FactoryOverride(BaseModel):
    """A UVM factory override."""
    original_type: str = Field(description="Original type being overridden")
    override_type: str = Field(description="Replacement type")
    override_scope: str = Field(
        default="type", description="Override scope: type/instance"
    )


class ConfigDBEntry(BaseModel):
    """A UVM config_db set/get."""
    operation: str = Field(description="Operation: set/get")
    field_name: str = Field(description="Config field name")
    value_type: str = Field(default="", description="Value type")
    scope: str = Field(default="", description="Hierarchical scope")
    component: str = Field(default="", description="Component doing set/get")


class UVMComponentInfo(BaseModel):
    """Generic UVM component information."""
    name: str = Field(description="Component class name")
    component_type: str = Field(
        description="Type: agent/env/test/sequencer/virtual_sequencer/virtual_sequence/config/package"
    )
    file: str = Field(default="", description="Source file")
    parent_class: str = Field(default="", description="Parent class")
    children: List[str] = Field(
        default_factory=list, description="Child components"
    )
    phase_methods: List[str] = Field(
        default_factory=list,
        description="Implemented phases (build_phase, connect_phase, etc.)"
    )


class AssertionInfo(BaseModel):
    """Assertion defined in testbench."""
    name: str = Field(default="", description="Assertion name/label")
    expression: str = Field(description="Assertion expression")
    assertion_type: str = Field(
        default="assert", description="Type: assert/assume/cover"
    )
    file: str = Field(default="", description="Source file")
    line_number: int = Field(default=0)


class InterfaceInfo(BaseModel):
    """A SystemVerilog interface."""
    name: str = Field(description="Interface name")
    file: str = Field(default="", description="Source file")
    signals: List[str] = Field(
        default_factory=list, description="Signal names declared"
    )
    clocking_blocks: List[str] = Field(
        default_factory=list, description="Clocking block names"
    )
    modports: List[str] = Field(
        default_factory=list, description="Modport names"
    )


class TBKnowledge(BaseModel):
    """
    Complete UVM testbench knowledge. Output schema for tb.json.
    """
    transactions: List[Transaction] = Field(
        default_factory=list, description="UVM transactions/sequence items"
    )
    sequences: List[SequenceInfo] = Field(
        default_factory=list, description="UVM sequences"
    )
    drivers: List[DriverInfo] = Field(
        default_factory=list, description="UVM drivers"
    )
    monitors: List[MonitorInfo] = Field(
        default_factory=list, description="UVM monitors"
    )
    scoreboards: List[ScoreboardInfo] = Field(
        default_factory=list, description="UVM scoreboards"
    )
    coverage: List[CoverageInfo] = Field(
        default_factory=list, description="Coverage collectors"
    )
    tlm_connections: List[TLMConnection] = Field(
        default_factory=list, description="TLM port connections"
    )
    factory_overrides: List[FactoryOverride] = Field(
        default_factory=list, description="Factory overrides"
    )
    config_db_entries: List[ConfigDBEntry] = Field(
        default_factory=list, description="Config DB entries"
    )
    components: List[UVMComponentInfo] = Field(
        default_factory=list, description="Other UVM components"
    )
    assertions: List[AssertionInfo] = Field(
        default_factory=list, description="TB-level assertions"
    )
    interfaces: List[InterfaceInfo] = Field(
        default_factory=list, description="SystemVerilog interfaces"
    )
    file_list: List[str] = Field(
        default_factory=list, description="All TB source files"
    )
    packages: List[str] = Field(
        default_factory=list, description="Package names"
    )
