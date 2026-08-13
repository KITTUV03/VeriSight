"""
Pydantic schema for Unified Knowledge (knowledge.json).

Merges spec, RTL, testbench, and log knowledge into a single
structure that is passed between agents in the pipeline.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from verisight.schemas.spec_schema import SpecKnowledge
from verisight.schemas.rtl_schema import RTLKnowledge
from verisight.schemas.tb_schema import TBKnowledge
from verisight.schemas.log_schema import LogKnowledge
from verisight.schemas.vcd_schema import VCDData


class CoverageData(BaseModel):
    """Optional coverage report data."""
    code_coverage: Dict[str, float] = Field(
        default_factory=dict,
        description="Code coverage metrics (line, branch, toggle, etc.)"
    )
    functional_coverage: Dict[str, float] = Field(
        default_factory=dict,
        description="Functional coverage metrics"
    )
    assertion_coverage: Dict[str, float] = Field(
        default_factory=dict,
        description="Assertion coverage metrics"
    )
    uncovered_bins: List[str] = Field(
        default_factory=list,
        description="List of uncovered bins"
    )
    raw_report: str = Field(
        default="", description="Raw coverage report text"
    )


class RAGContext(BaseModel):
    """Context retrieved from RAG knowledge base for similar past failures."""
    similar_failures: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Similar past failures with their solutions"
    )
    relevant_patterns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Relevant debugging patterns"
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence that RAG context is relevant (0-1)"
    )


class UnifiedKnowledge(BaseModel):
    """
    Unified knowledge graph merging all input sources.
    This is the central data structure passed from Agent 1 to Agent 2.
    Output schema for knowledge.json.
    """
    spec: SpecKnowledge = Field(
        default_factory=SpecKnowledge,
        description="Design specification knowledge"
    )
    rtl: RTLKnowledge = Field(
        default_factory=RTLKnowledge,
        description="RTL design knowledge"
    )
    tb: TBKnowledge = Field(
        default_factory=TBKnowledge,
        description="UVM testbench knowledge"
    )
    logs: LogKnowledge = Field(
        default_factory=LogKnowledge,
        description="Simulation log knowledge"
    )
    coverage: Optional[CoverageData] = Field(
        default=None,
        description="Optional coverage data"
    )
    vcd: Optional[VCDData] = Field(
        default=None,
        description="Post-processed VCD waveform data (user-supplied or --simulate-generated)"
    )
    rag_context: Optional[RAGContext] = Field(
        default=None,
        description="Context from RAG knowledge base"
    )
    input_files: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapping of input category → file paths"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Session metadata (timestamp, version, etc.)"
    )
