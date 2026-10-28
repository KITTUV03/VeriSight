"""
Pydantic Schemas for Spec-Driven Testbench Generation Agent.

Defines structured data contracts for:
- Traceable Requirement Items (REQ-001, etc.)
- Design Mental Model (architecture, interfaces, state models, protocol)
- Intent vs. Implementation Comparison (Consistent / Potential Mismatch / Unresolved)
- Static and Dynamic Validation Results
- Unified Generation Result
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class RequirementItem(BaseModel):
    """Atomic, traceable specification requirement."""
    req_id: str = Field(description="Unique requirement ID (e.g., REQ-001)")
    title: str = Field(description="Short descriptive title")
    description: str = Field(description="Full requirement text or faithful summary")
    category: str = Field(default="Functional", description="Category: Functional/Interface/Reset/Timing/Protocol/Boundary/Register")
    source_section: str = Field(default="", description="Section in specification document")
    rtl_mapping: str = Field(default="", description="Mapped RTL port, signal, or logic")
    expected_behavior: str = Field(description="Authoritative expected behavior from specification")
    verification_strategy: str = Field(description="Stimulus and checking strategy")
    test_sequence: str = Field(description="Test or sequence name exercising this requirement")
    checker_assertion: str = Field(description="Scoreboard check or SVA assertion verifying this requirement")
    coverage_objective: str = Field(description="Coverpoint or cross coverage verifying this requirement")
    priority: str = Field(default="High", description="Priority: Critical/High/Medium/Low")
    status: str = Field(default="IMPLEMENTED", description="Status: IMPLEMENTED/VALIDATED/FAILED/PARTIAL/UNRESOLVED/NOT_TESTED")


class IntentComparisonItem(BaseModel):
    """Specification intent vs. RTL implementation comparison."""
    req_id: str = Field(description="Associated requirement ID")
    requirement_summary: str = Field(description="Summary of specified functional requirement")
    rtl_construct: str = Field(description="Observed RTL signal, expression, or always-block")
    classification: str = Field(description="Consistent | Potential Mismatch | Unresolved | Unobservable")
    evidence: str = Field(description="Source file, line, and code evidence")
    impact_on_reference_model: str = Field(description="Directive ensuring reference model follows spec, not RTL defect")


class MentalModel(BaseModel):
    """Comprehensive design mental model constructed from Spec + RTL."""
    design_name: str
    top_module: str
    spec_title: str
    ports: List[Dict[str, Any]] = Field(default_factory=list)
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    clock_domains: List[Dict[str, Any]] = Field(default_factory=list)
    clock_signal: str = "clk"
    reset_signal: str = "rst_n"
    reset_type: str = "synchronous"
    reset_active_level: str = "low"
    protocol: str = "custom"
    functional_behaviors: List[str] = Field(default_factory=list)
    state_machines: List[Dict[str, Any]] = Field(default_factory=list)
    timing_ordering_constraints: List[str] = Field(default_factory=list)
    corner_cases: List[str] = Field(default_factory=list)
    intent_vs_implementation: List[IntentComparisonItem] = Field(default_factory=list)
    unresolved_ambiguities: List[str] = Field(default_factory=list)


class UVMComponentInfo(BaseModel):
    """Metadata describing a synthesized UVM component."""
    file_name: str
    class_name: str
    role: str
    description: str


class StaticValidationResult(BaseModel):
    """Static analysis and syntax elaboration status."""
    syntax_clean: bool = True
    parser_used: str = "pyslang (IEEE 1800-2023)"
    files_checked: int = 0
    diagnostics: List[str] = Field(default_factory=list)


class SimulationValidationResult(BaseModel):
    """Dynamic simulation execution and defect exposure status."""
    simulator_name: Optional[str] = None
    compiled: bool = False
    simulated: bool = False
    pass_status: bool = False
    mismatches_detected: int = 0
    errors_logged: int = 0
    log_summary: str = ""
    detected_rtl_bugs: List[str] = Field(default_factory=list)


class SpecDrivenTBResult(BaseModel):
    """Complete deliverable of the Spec-Driven Testbench Generation Agent."""
    design_name: str
    output_dir: str
    mental_model: MentalModel
    requirements: List[RequirementItem] = Field(default_factory=list)
    uvm_components: List[UVMComponentInfo] = Field(default_factory=list)
    files_generated: List[str] = Field(default_factory=list)
    static_validation: StaticValidationResult = Field(default_factory=StaticValidationResult)
    simulation_validation: Optional[SimulationValidationResult] = None
    validation_status: str = "STATIC_VALIDATED"
    traceability_matrix_file: Optional[str] = None
    mental_model_file: Optional[str] = None
    vplan_file: Optional[str] = None
    report_file: Optional[str] = None
