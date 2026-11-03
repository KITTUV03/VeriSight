"""
Pydantic schemas for UPF (Unified Power Format - IEEE 1801) Power Intent.

Captures structured power architecture knowledge extracted from .upf files,
including power domains, supply nets/ports, power switches, isolation strategies,
level shifters, retention registers, and power state tables (PST).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SupplyPort(BaseModel):
    """A supply port declaration."""
    name: str = Field(description="Port name")
    direction: str = Field(default="in", description="Port direction (in/out)")
    domain: Optional[str] = Field(default=None, description="Power domain")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class SupplyNet(BaseModel):
    """A supply net declaration."""
    name: str = Field(description="Net name")
    domain: Optional[str] = Field(default=None, description="Power domain")
    is_reuse: bool = Field(default=False, description="Whether net is reused across scopes")
    connected_ports: List[str] = Field(default_factory=list, description="Ports connected to this net")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class SupplySet(BaseModel):
    """A supply set combining power and ground nets."""
    name: str = Field(description="Supply set name")
    power_net: str = Field(default="", description="Power net reference")
    ground_net: str = Field(default="", description="Ground net reference")
    domain: Optional[str] = Field(default=None, description="Power domain")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class PowerSwitch(BaseModel):
    """A power switch gating a power domain."""
    name: str = Field(description="Power switch instance name")
    domain: str = Field(description="Target power domain being gated")
    input_supply_port: str = Field(default="", description="Input unswitched supply net/port")
    output_supply_port: str = Field(default="", description="Output switched supply net/port")
    control_port: str = Field(default="", description="Switch control signal from power management")
    ack_port: str = Field(default="", description="Acknowledge port for power switch handshake")
    on_state: str = Field(default="", description="On-state specification (e.g., 'ON in {!ctrl}')")
    off_state: str = Field(default="", description="Off-state specification")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class IsolationStrategy(BaseModel):
    """An isolation strategy between power domains."""
    name: str = Field(description="Strategy name")
    domain: str = Field(description="Power domain where isolation applies")
    applies_to: str = Field(default="outputs", description="applies_to: inputs, outputs, both")
    clamp_value: str = Field(default="0", description="Clamp value: '0', '1', 'latch'")
    isolation_signal: str = Field(default="", description="Isolation enable control signal")
    isolation_sense: str = Field(default="high", description="Active sense: 'high' or 'low'")
    location: str = Field(default="self", description="Location: 'self', 'parent', 'fanout'")
    elements: List[str] = Field(default_factory=list, description="Specific signals/ports isolated")
    isolation_power_net: str = Field(default="", description="Always-on isolation supply net")
    isolation_ground_net: str = Field(default="", description="Isolation ground net")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class LevelShifterStrategy(BaseModel):
    """A level shifter strategy across voltage domains."""
    name: str = Field(description="Strategy name")
    domain: str = Field(description="Power domain")
    applies_to: str = Field(default="inputs", description="applies_to: inputs, outputs, both")
    rule: str = Field(default="both", description="Voltage rule: 'low_to_high', 'high_to_low', 'both'")
    location: str = Field(default="self", description="Location: 'self', 'parent'")
    elements: List[str] = Field(default_factory=list, description="Specific signals shifted")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class RetentionStrategy(BaseModel):
    """A retention strategy for sequential elements."""
    name: str = Field(description="Strategy name")
    domain: str = Field(description="Power domain")
    retention_power_net: str = Field(default="", description="Always-on retention power net")
    retention_ground_net: str = Field(default="", description="Retention ground net")
    save_signal: str = Field(default="", description="Retention save trigger signal")
    restore_signal: str = Field(default="", description="Retention restore trigger signal")
    elements: List[str] = Field(default_factory=list, description="Target sequential elements")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class PowerStateTable(BaseModel):
    """Power State Table (PST) defining valid concurrent supply states."""
    name: str = Field(description="PST table name")
    supplies: List[str] = Field(default_factory=list, description="Ordered list of supply nets")
    states: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="State name -> list of states per supply (e.g. {'ACTIVE': ['ON', 'ON', 'GND']})"
    )
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class PowerState(BaseModel):
    """An individual power state specification."""
    name: str = Field(description="Power state name")
    domain_or_pst: str = Field(default="", description="Associated domain or PST table")
    states: Dict[str, str] = Field(default_factory=dict, description="Supply net/port -> state")
    is_off: bool = Field(default=False, description="Whether this state shuts down the domain")
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class PowerDomain(BaseModel):
    """A power domain grouping design elements."""
    name: str = Field(description="Domain name (e.g. 'TOP', 'PD_CORE')")
    scope: str = Field(default="", description="Hierarchical scope")
    elements: List[str] = Field(default_factory=list, description="Instance paths in domain (e.g. ['u_core'])")
    is_top: bool = Field(default=False, description="Whether this is the root top-level domain")
    include_scope: bool = Field(default=False, description="Whether domain includes its definition scope")
    primary_power_net: str = Field(default="", description="Primary VDD supply net")
    primary_ground_net: str = Field(default="", description="Primary VSS ground net")
    associated_modules: List[str] = Field(
        default_factory=list,
        description="Resolved RTL module names mapped to this domain"
    )
    file: str = Field(default="", description="Source UPF file")
    line_number: int = Field(default=0, description="Line number in UPF file")


class UPFDiagnostic(BaseModel):
    """A syntax, consistency, or hierarchy diagnostic produced during UPF analysis."""
    severity: str = Field(default="error", description="Severity: error, warning, note")
    message: str = Field(description="Diagnostic message")
    line_number: int = Field(default=0, description="Line number in UPF file")
    file: str = Field(default="", description="UPF file path")
    code: str = Field(default="UPF", description="Diagnostic category code")


class UPFKnowledge(BaseModel):
    """
    Complete power intent extracted from one or more UPF files and
    resolved against the RTL hierarchy.
    """
    file_paths: List[str] = Field(default_factory=list, description="Paths to parsed UPF files")
    power_domains: List[PowerDomain] = Field(default_factory=list, description="Defined power domains")
    supply_ports: List[SupplyPort] = Field(default_factory=list, description="Supply ports")
    supply_nets: List[SupplyNet] = Field(default_factory=list, description="Supply nets")
    supply_sets: List[SupplySet] = Field(default_factory=list, description="Supply sets")
    power_switches: List[PowerSwitch] = Field(default_factory=list, description="Power switches")
    isolation_strategies: List[IsolationStrategy] = Field(default_factory=list, description="Isolation strategies")
    level_shifters: List[LevelShifterStrategy] = Field(default_factory=list, description="Level shifter strategies")
    retention_strategies: List[RetentionStrategy] = Field(default_factory=list, description="Retention strategies")
    power_state_tables: List[PowerStateTable] = Field(default_factory=list, description="Power state tables")
    power_states: List[PowerState] = Field(default_factory=list, description="Power states")
    diagnostics: List[UPFDiagnostic] = Field(default_factory=list, description="UPF diagnostics & hierarchy warnings")
    is_valid: bool = Field(default=True, description="Whether UPF is syntactically and architecturally valid")
    resolved_hierarchy: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of RTL instance/module path -> Power domain name"
    )

