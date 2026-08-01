"""
Pydantic schema for Root Cause Classification (summary.json).

Agent 2 output: classifies the root cause as TB Bug, RTL Bug,
Specification Ambiguity, or Unknown with a confidence score
and structured evidence.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class BugClassification(str, Enum):
    TB_BUG = "TB Bug"
    RTL_BUG = "RTL Bug"
    SPEC_BUG = "Spec Bug"
    UNKNOWN = "Unknown"


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting a classification."""
    source: str = Field(
        description="Evidence source: spec/rtl/tb/log/coverage"
    )
    reference: str = Field(
        description="Specific reference (file:line, section, timestamp)"
    )
    description: str = Field(
        description="What this evidence shows"
    )
    snippet: str = Field(
        default="", description="Code or log snippet"
    )


class ClassificationReasoning(BaseModel):
    """Chain-of-thought reasoning for the classification decision."""
    step: int = Field(description="Reasoning step number")
    observation: str = Field(description="What was observed")
    inference: str = Field(description="What was inferred")
    source: str = Field(
        default="", description="Source of observation"
    )


class Classification(BaseModel):
    """
    Root cause classification result from Agent 2.
    Output schema for summary.json.
    """
    classification: str = Field(
        description="Classification: TB Bug / RTL Bug / Spec Bug / Unknown"
    )
    confidence: int = Field(
        ge=0, le=100,
        description="Confidence score (0-100%)"
    )
    component: str = Field(
        default="",
        description="Responsible component (e.g., 'Scoreboard', 'ALU', 'Driver')"
    )
    reason: str = Field(
        description="Human-readable root cause explanation"
    )
    category: str = Field(
        default="",
        description="Bug category (e.g., 'X Propagation', 'Functional', 'Protocol')"
    )
    spec_reference: str = Field(
        default="",
        description="Relevant specification section"
    )
    log_reference: str = Field(
        default="",
        description="Relevant log entry reference"
    )
    rtl_reference: str = Field(
        default="",
        description="Relevant RTL file and line"
    )
    tb_reference: str = Field(
        default="",
        description="Relevant testbench file and line"
    )
    recommended_fix: str = Field(
        default="",
        description="Recommended fix"
    )
    evidence: List[EvidenceItem] = Field(
        default_factory=list,
        description="Supporting evidence chain"
    )
    reasoning_chain: List[ClassificationReasoning] = Field(
        default_factory=list,
        description="Step-by-step reasoning"
    )
    missing_artifacts: List[str] = Field(
        default_factory=list,
        description="Artifacts that would improve classification (for Unknown)"
    )
    alternative_hypotheses: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Alternative classifications considered [{classification, confidence, reason}]"
    )
