"""
Pydantic schema for Automated Fix Generation (Agent 5 output).

Represents a concrete, evidence-grounded source-code fix proposal
for RTL or Testbench issues identified by the analysis pipeline.

fix.json is saved alongside error.json in the output directory.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ConfidenceBreakdown(BaseModel):
    """Evidence-weighted breakdown of how fix confidence was calculated."""
    spec_agreement: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Spec directly supports the fix (weight 0.25)"
    )
    root_cause_certainty: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Agent 2/3 classification confidence (weight 0.25)"
    )
    code_evidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Exact file/line found in RTL or TB (weight 0.20)"
    )
    uvm_log_evidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Error messages directly match the fix (weight 0.15)"
    )
    fix_consistency: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Fix does not break other signals or interfaces (weight 0.10)"
    )
    validation_evidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Syntax/structural validation passed (weight 0.05)"
    )

    def compute_total(self) -> float:
        """
        Compute weighted confidence score.

        Weights:
            spec_agreement        0.25
            root_cause_certainty  0.25
            code_evidence         0.20
            uvm_log_evidence      0.15
            fix_consistency       0.10
            validation_evidence   0.05
        """
        return (
            self.spec_agreement        * 0.25 +
            self.root_cause_certainty  * 0.25 +
            self.code_evidence         * 0.20 +
            self.uvm_log_evidence      * 0.15 +
            self.fix_consistency       * 0.10 +
            self.validation_evidence   * 0.05
        )


class ValidationResult(BaseModel):
    """Results of fix validation at each available level."""
    syntax: str = Field(
        default="NOT_RUN",
        description="Level 1 syntax check: PASS / FAIL / NOT_RUN"
    )
    syntax_notes: str = Field(
        default="",
        description="Details of syntax check result"
    )
    structural: str = Field(
        default="NOT_RUN",
        description="Level 2 structural check (signal names, ports): PASS / FAIL / NOT_RUN"
    )
    structural_notes: str = Field(
        default="",
        description="Details of structural check result"
    )
    specification: str = Field(
        default="NOT_RUN",
        description="Level 3 specification consistency: PASS / FAIL / NOT_RUN"
    )
    specification_notes: str = Field(
        default="",
        description="Details of specification check result"
    )
    simulation: str = Field(
        default="NOT_AVAILABLE",
        description="Level 4 simulation run: PASS / FAIL / NOT_AVAILABLE"
    )
    regression: str = Field(
        default="NOT_AVAILABLE",
        description="Level 5 regression: PASS / FAIL / NOT_RUN / NOT_AVAILABLE"
    )

    def overall_status(self) -> str:
        """
        Determine the highest validated level.

        Returns one of:
            'Regression Validated'
            'Simulation Validated'
            'Specification Validated'
            'Syntax Validated'
            'Not Validated'
        """
        if self.regression == "PASS":
            return "Regression Validated"
        if self.simulation == "PASS":
            return "Simulation Validated"
        if self.specification == "PASS":
            return "Specification Validated"
        if self.syntax == "PASS":
            return "Syntax Validated"
        return "Not Validated"


class FixResult(BaseModel):
    """
    Automated fix proposal from Agent 5.

    Represents a complete, evidence-grounded fix for one root cause.
    This is the output schema for fix.json.

    fix_available=False means Agent 5 declined to generate a fix —
    either because confidence is below threshold, RTL is unavailable,
    or evidence is insufficient.
    """

    # ─── Status ──────────────────────────────────────────────────
    fix_available: bool = Field(
        default=False,
        description="True if a fix was generated with sufficient confidence"
    )
    issue_type: str = Field(
        default="none",
        description="Type of issue fixed: RTL / TB / none"
    )
    fix_type: str = Field(
        default="no_fix",
        description=(
            "no_fix / code_patch / specification_based — "
            "specification_based means RTL was unavailable/black-box"
        )
    )
    rtl_available: bool = Field(
        default=False,
        description="Whether RTL source was available for direct analysis"
    )

    # ─── Confidence ─────────────────────────────────────────────
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Overall fix confidence (0.0–1.0, evidence-weighted)"
    )
    confidence_breakdown: ConfidenceBreakdown = Field(
        default_factory=ConfidenceBreakdown,
        description="Per-factor confidence breakdown"
    )
    confidence_threshold_used: float = Field(
        default=0.70,
        description="Configured minimum confidence threshold for fix generation"
    )

    # ─── Target ─────────────────────────────────────────────────
    target_file: str = Field(
        default="",
        description="Source file containing the bug"
    )
    target_module: str = Field(
        default="",
        description="Module name containing the bug"
    )
    target_lines: str = Field(
        default="",
        description="Approximate line range of the buggy code (e.g. '42-49')"
    )

    # ─── Root Cause ─────────────────────────────────────────────
    root_cause_summary: str = Field(
        default="",
        description="Concise root cause the fix addresses"
    )
    expected_behavior: str = Field(
        default="",
        description="What the design should do according to the specification"
    )
    observed_behavior: str = Field(
        default="",
        description="What the design actually does (observed failure)"
    )
    reasoning: str = Field(
        default="",
        description="Why this modification fixes the observed failure"
    )

    # ─── The Fix ────────────────────────────────────────────────
    patch: str = Field(
        default="",
        description="Unified diff patch (- old / + new format)"
    )
    corrected_code: str = Field(
        default="",
        description=(
            "Complete corrected code snippet (always block, module, etc.) "
            "showing the fixed implementation"
        )
    )

    # ─── Validation ─────────────────────────────────────────────
    validation: ValidationResult = Field(
        default_factory=ValidationResult,
        description="Validation results at each available level"
    )
    validation_status: str = Field(
        default="Not Validated",
        description="Human-readable highest validation level achieved"
    )

    # ─── Cascading Errors ────────────────────────────────────────
    cascading_errors: List[str] = Field(
        default_factory=list,
        description=(
            "UVM error messages that share this root cause. "
            "A single fix addresses all of them."
        )
    )

    # ─── Transparency ────────────────────────────────────────────
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions made when generating this fix"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Known limitations or caveats of this fix"
    )
    decline_reason: str = Field(
        default="",
        description=(
            "If fix_available=False, explains why no fix was generated. "
            "E.g. 'Confidence 0.45 below threshold 0.70'"
        )
    )
