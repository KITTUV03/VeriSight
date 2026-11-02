"""
Pydantic schema for UPF (Unified Power Format) Power-Intent Knowledge.

Captures structured power-intent information from IEEE 1801 UPF files:
- Power domains
- Supply ports and nets
- Supply sets
- Power switches
- Isolation strategies
- Level shifter strategies
- Retention strategies
- Power states and Power State Tables (PST)
- Cross-domain signal crossings and hierarchy resolution
- Validation diagnostics
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class PowerDomain(BaseModel):
    """UPF Power Domain declaration."""
    name: str = Field(description="Power domain name (e.g. 'PD_TOP', 'PD_CORE')")
    scope: str = Field(default="", description="Scope where domain is defined (e.g. '.')")
    elements: List[str] = Field(
        default_factory=list,
        description="Hierarchical instances or modules bound to this domain"
    )
    primary_power_net: str = Field(default="", description="Primary power supply net (VDD)")
    primary_ground_net: str = Field(default="", description="Primary ground supply net (VSS)")
    supply_sets: List[str] = Field(
        default_factory=list,
        description="Supply sets associated with this domain"
    )
    is_default: bool = Field(default=False, description="Whether this is the top/default domain")


class SupplyPort(BaseModel):
    """UPF Supply Port."""
    name: str = Field(description="Port name")
    direction: str = Field(default="in", description="Port direction: in/out")
    domain: str = Field(default="", description="Associated power domain")


class SupplyNet(BaseModel):
    """UPF Supply Net."""
    name: str = Field(description="Net name (e.g. 'VDD', 'VSS')")
    domain: str = Field(default="", description="Associated power domain")
    is_ground: bool = Field(default=False, description="Whether net is ground")
    is_power: bool = Field(default=False, description="Whether net is power")
    resolved_type: str = Field(default="unresolved", description="parallel/unresolved")


class SupplySet(BaseModel):
    """UPF Supply Set."""
    name: str = Field(description="Supply set name")
    power_net: str = Field(default="", description="Power function supply net")
    ground_net: str = Field(default="", description="Ground function supply net")
    pwell: str = Field(default="", description="P-well supply net")
    nwell: str = Field(default="", description="N-well supply net")


class PowerSwitch(BaseModel):
    """UPF Power Switch (header/footer switch for domain power gating)."""
    name: str = Field(description="Power switch instance/strategy name")
    domain: str = Field(description="Power domain being switched")
    in_port: str = Field(default="", description="Input supply port/net (always-on)")
    out_port: str = Field(default="", description="Output supply port/net (switched)")
    control_port: str = Field(default="", description="Enable / sleep control signal")
    ack_port: str = Field(default="", description="Acknowledge signal if present")
    on_state: str = Field(default="", description="On state condition (e.g. '!sleep')")


class IsolationStrategy(BaseModel):
    """UPF Isolation Strategy for domain boundary signals."""
    name: str = Field(description="Strategy name")
    domain: str = Field(description="Power domain where isolation applies")
    isolation_signal: str = Field(default="", description="Isolation control enable signal")
    isolation_sense: str = Field(default="high", description="Active high or low")
    clamp_value: str = Field(default="0", description="Clamp output: 0, 1, or latch")
    elements: List[str] = Field(
        default_factory=list,
        description="Specific signal elements or interfaces to isolate"
    )
    applies_to: str = Field(default="outputs", description="inputs, outputs, or both")
    location: str = Field(default="from", description="from (source domain) or to (dest domain)")


class LevelShifterStrategy(BaseModel):
    """UPF Level Shifter Strategy for voltage domain boundary signals."""
    name: str = Field(description="Level shifter strategy name")
    domain: str = Field(description="Power domain")
    rule: str = Field(default="both", description="low_to_high, high_to_low, or both")
    applies_to: str = Field(default="both", description="inputs, outputs, or both")
    elements: List[str] = Field(
        default_factory=list,
        description="Specific signal elements requiring level shifting"
    )
    threshold: str = Field(default="", description="Voltage threshold difference")


class RetentionStrategy(BaseModel):
    """UPF State Retention Strategy for registers during power-down."""
    name: str = Field(description="Retention strategy name")
    domain: str = Field(description="Power domain containing retained registers")
    save_signal: str = Field(default="", description="Signal to trigger retention save")
    restore_signal: str = Field(default="", description="Signal to trigger retention restore")
    retention_power_net: str = Field(default="", description="Always-on power net for retention")
    retention_ground_net: str = Field(default="", description="Ground net for retention")
    elements: List[str] = Field(
        default_factory=list,
        description="Target registers or memory elements for retention"
    )


class PowerState(BaseModel):
    """UPF Power State for a domain, supply, or system."""
    name: str = Field(description="State name (e.g. 'ON', 'OFF', 'SLEEP')")
    object_ref: str = Field(description="Power domain or supply set reference")
    logic_expression: str = Field(default="", description="Logic condition for this state")
    simstate: str = Field(default="NORMAL", description="NORMAL, CORRUPT, or OFF")


class PowerStateTable(BaseModel):
    """UPF Power State Table (PST) defining legal operational state combinations."""
    name: str = Field(description="PST name")
    supplies: List[str] = Field(
        default_factory=list,
        description="List of supply nets or supply sets tracked by PST"
    )
    states: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Matrix of state rows: [{state_name: ..., supply1: ON, supply2: OFF}]"
    )


class DomainCrossing(BaseModel):
    """Signal crossing between two different power domains."""
    signal: str = Field(description="Signal name")
    width: str = Field(default="1", description="Signal bit width")
    source_domain: str = Field(description="Source power domain name")
    dest_domain: str = Field(description="Destination power domain name")
    source_module: str = Field(default="", description="Source module/instance")
    dest_module: str = Field(default="", description="Destination module/instance")
    has_isolation: bool = Field(default=False, description="Whether signal has isolation strategy")
    isolation_strategy: str = Field(default="", description="Isolation strategy name if present")
    has_level_shifter: bool = Field(default=False, description="Whether signal has level shifter")
    level_shifter_strategy: str = Field(default="", description="Level shifter strategy name")
    issues: List[str] = Field(default_factory=list, description="Issues detected on this crossing")


class UPFValidationIssue(BaseModel):
    """Diagnostic validation issue found in UPF or RTL-UPF cross-check."""
    severity: str = Field(description="error, warning, or info")
    issue_type: str = Field(
        default="diagnostic",
        description="syntax_error, missing_element, unmapped_domain, missing_isolation, "
                    "missing_level_shifter, retention_hazard, pst_violation"
    )
    category: str = Field(default="", description="Category of UPF diagnostic")
    description: str = Field(description="Human-readable diagnostic description")
    file: str = Field(default="", description="File where issue was found (.upf or .sv)")
    line_number: int = Field(default=0, description="Line number if identifiable")
    element: str = Field(default="", description="Affected element, domain, or signal")

    def model_post_init(self, __context: Any) -> None:
        if not self.category and self.issue_type:
            self.category = self.issue_type.replace("_", " ").title()
        elif not self.issue_type and self.category:
            self.issue_type = self.category.lower().replace(" ", "_")


class UPFKnowledge(BaseModel):
    """Complete structured power-intent knowledge extracted from UPF."""
    file_list: List[str] = Field(
        default_factory=list,
        description="List of parsed UPF files"
    )
    power_domains: List[PowerDomain] = Field(
        default_factory=list,
        description="Defined power domains"
    )
    supply_ports: List[SupplyPort] = Field(
        default_factory=list,
        description="Defined supply ports"
    )
    supply_nets: List[SupplyNet] = Field(
        default_factory=list,
        description="Defined supply nets"
    )
    supply_sets: List[SupplySet] = Field(
        default_factory=list,
        description="Defined supply sets"
    )
    power_switches: List[PowerSwitch] = Field(
        default_factory=list,
        description="Power gating switches"
    )
    isolation_strategies: List[IsolationStrategy] = Field(
        default_factory=list,
        description="Isolation strategies"
    )
    level_shifter_strategies: List[LevelShifterStrategy] = Field(
        default_factory=list,
        description="Level shifter strategies"
    )
    retention_strategies: List[RetentionStrategy] = Field(
        default_factory=list,
        description="Retention strategies"
    )
    power_states: List[PowerState] = Field(
        default_factory=list,
        description="Power states"
    )
    power_state_tables: List[PowerStateTable] = Field(
        default_factory=list,
        description="Power state tables (PST)"
    )
    resolved_hierarchy: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of RTL instance/module path -> Power Domain name"
    )
    domain_crossings: List[DomainCrossing] = Field(
        default_factory=list,
        description="All signals crossing power domain boundaries"
    )
    validation_issues: List[UPFValidationIssue] = Field(
        default_factory=list,
        description="Diagnostics and validation issues found in UPF or RTL-UPF alignment"
    )
    summary: str = Field(default="", description="Executive summary of power intent")
    is_valid: bool = Field(default=True, description="Whether power intent is syntactically & structurally valid")
