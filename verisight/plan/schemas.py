"""
Pydantic Schemas for VeriSight Plan (Verification & Architecture Planning).

Defines structured data models for:
- Features (decomposed requirements, modes, registers, interfaces)
- Test Scenarios (directed, random, corner cases, error injection)
- Functional Coverage Items & SystemVerilog Covergroups
- SystemVerilog Assertions (SVA properties & sequences)
- Bi-directional Traceability Matrix
- Unified Verification Plan
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FeatureItem(BaseModel):
    """Decomposed functional requirement or feature."""
    feature_id: str = Field(description="Unique ID e.g. FEAT-001")
    title: str = Field(description="Short descriptive title")
    description: str = Field(description="Full functional requirement description")
    category: str = Field(default="Functional", description="Functional, Interface, Register, CornerCase, Protocol, Performance")
    source_section: Optional[str] = Field(default=None, description="Section in spec document")
    priority: str = Field(default="High", description="Critical, High, Medium, Low")
    rtl_cross_check: Optional[str] = Field(default=None, description="Correlation status with RTL: Confirmed, Missing_In_RTL, Undocumented_In_Spec")


class TestScenario(BaseModel):
    """Specific test case scenario defined in the Test Plan."""
    test_id: str = Field(description="Unique Test ID e.g. TEST-001")
    feature_ids: List[str] = Field(default_factory=list, description="Mapped Feature IDs")
    title: str = Field(description="Test scenario title")
    test_type: str = Field(description="Directed, Constrained_Random, Corner_Case, Error_Injection, Stress, Performance")
    description: str = Field(description="Detailed stimulus and test objective")
    stimulus: str = Field(description="Configuration and input stimulus sequence")
    expected_response: str = Field(description="Expected DUT output and scoreboard checking logic")
    priority: str = Field(default="High", description="Critical, High, Medium, Low")


class CoverageBin(BaseModel):
    """Individual coverage bin definition."""
    bin_name: str
    bin_type: str = "bins"  # bins, illegal_bins, ignore_bins
    condition: str
    description: Optional[str] = None


class CoveragePoint(BaseModel):
    """Functional coverage point or cross coverage item."""
    coverage_id: str = Field(description="Unique Coverage ID e.g. COV-001")
    feature_ids: List[str] = Field(default_factory=list, description="Mapped Feature IDs")
    name: str = Field(description="Coverpoint or Cross name e.g. cp_opcode, cr_op_vs_carry")
    target_signal: str = Field(description="Target signal or expression sampled")
    sample_event: str = Field(default="@(posedge clk)", description="Sampling event or clock edge")
    bins: List[CoverageBin] = Field(default_factory=list, description="Defined bins")
    description: str = Field(description="Verification intent of this coverage point")


class CovergroupDef(BaseModel):
    """SystemVerilog Covergroup definition."""
    group_name: str = Field(description="Covergroup name e.g. cg_alu_operations")
    sample_trigger: str = Field(description="Trigger e.g. @(posedge clk iff !rst_n)")
    coverpoints: List[CoveragePoint] = Field(default_factory=list)
    crosses: List[str] = Field(default_factory=list, description="Cross coverage expressions")
    description: str = Field(description="Scope and purpose of this covergroup")


class SVAProperty(BaseModel):
    """SystemVerilog Assertion definition."""
    assertion_id: str = Field(description="Unique SVA ID e.g. SVA-001")
    feature_ids: List[str] = Field(default_factory=list, description="Mapped Feature IDs")
    name: str = Field(description="Property name e.g. prop_reset_clears_result")
    property_type: str = Field(default="assert", description="assert, assume, cover")
    clock_expr: str = Field(default="posedge clk", description="Clocking event")
    disable_expr: Optional[str] = Field(default="!rst_n", description="Disable condition e.g. !rst_n")
    expression: str = Field(description="Formal SVA sequence/property expression")
    failure_message: str = Field(description="UVM_ERROR message on assertion violation")
    description: str = Field(description="Formal verification or simulation intent")


class TraceabilityRow(BaseModel):
    """Single row in the bi-directional traceability matrix."""
    feature_id: str
    feature_title: str
    test_ids: List[str] = Field(default_factory=list)
    coverage_ids: List[str] = Field(default_factory=list)
    assertion_ids: List[str] = Field(default_factory=list)
    status: str = Field(default="Covered", description="Covered, Partial, Uncovered")


class VerificationPlanReport(BaseModel):
    """Complete Verification Plan unified artifact."""
    plan_id: str
    design_name: str
    timestamp: str
    spec_source: str
    rtl_source: Optional[str] = None
    total_features: int = 0
    total_tests: int = 0
    total_coverage_points: int = 0
    total_assertions: int = 0
    features: List[FeatureItem] = Field(default_factory=list)
    test_scenarios: List[TestScenario] = Field(default_factory=list)
    covergroups: List[CovergroupDef] = Field(default_factory=list)
    assertions: List[SVAProperty] = Field(default_factory=list)
    traceability_matrix: List[TraceabilityRow] = Field(default_factory=list)
    rag_cached: bool = False
    sv_coverage_code: Optional[str] = None
    sv_assertion_code: Optional[str] = None
