"""
Agent 1 — Knowledge Extraction Engine.

Reads all available inputs and converts them into structured knowledge.
Orchestrates parsers for spec, RTL, UVM, log, and coverage files,
then uses LLM to enrich parser output with semantic understanding.
Builds the UnifiedKnowledge (knowledge.json) passed to Agent 2.
"""

from pathlib import Path
from typing import Optional, List
from datetime import datetime

from verisight.agents.base_agent import BaseAgent
from verisight.parsers.spec_parser import parse_spec
from verisight.parsers.rtl_parser import parse_rtl
from verisight.parsers.uvm_parser import parse_uvm
from verisight.parsers.log_parser import parse_log
from verisight.parsers.coverage_parser import parse_coverage
from verisight.parsers.vcd_parser import parse_vcd
from verisight.schemas.knowledge_schema import UnifiedKnowledge, RAGContext
from verisight.rag.knowledge_base import KnowledgeBase
from verisight.rag.retriever import Retriever
from verisight.utils.logger import get_logger

logger = get_logger("agent1_knowledge")

SYSTEM_PROMPT = """You are a Principal ASIC Verification Engineer with 30+ years of experience.
Your role is to analyze the parsed knowledge from design specifications, RTL, UVM testbenches,
and simulation logs to identify:

1. Implicit requirements not explicitly stated in the spec
2. Design intent from RTL implementation patterns
3. Correlations between log errors and specific TB/RTL components
4. Missing or weak verification coverage

You enhance the parsed data with your deep domain expertise, adding semantic understanding
that goes beyond what regex-based parsers can extract.

CRITICAL RULES:
- Every observation must be evidence-based
- Cite specific files, lines, and timestamps
- Do not speculate without supporting data
- Prioritize semantic understanding over keyword matching
"""


class KnowledgeExtractionAgent(BaseAgent):
    """
    Agent 1: Knowledge Extraction Engine.

    Orchestrates all parsers and builds unified knowledge graph.
    """

    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None):
        super().__init__("knowledge_extraction")
        self.kb = knowledge_base

    def execute(
        self,
        spec_path: Optional[str] = None,
        rtl_path: Optional[str] = None,
        tb_path: Optional[str] = None,
        log_path: Optional[str] = None,
        coverage_path: Optional[str] = None,
        vcd_path: Optional[str] = None,
    ) -> UnifiedKnowledge:
        """
        Execute knowledge extraction from all available inputs.

        Args:
            spec_path: Path to design specification (.md).
            rtl_path: Path to RTL source file(s) or directory.
            tb_path: Path to UVM testbench file(s) or directory.
            log_path: Path to simulation log file.
            coverage_path: Optional path to coverage report.
            vcd_path: Optional path to a simulation waveform (VCD), either
                user-supplied or produced internally by --simulate.

        Returns:
            UnifiedKnowledge containing all parsed and enriched knowledge.
        """
        self.logger.info("=" * 60)
        self.logger.info("Agent 1: Knowledge Extraction Engine — Starting")
        self.logger.info("=" * 60)

        knowledge = UnifiedKnowledge(
            metadata={
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            },
            input_files={},
        )

        # ─── Step 1: Parse Specification ──────────────────────────
        if spec_path:
            self.logger.info(f"Step 1: Parsing specification: {spec_path}")
            knowledge.spec = parse_spec(spec_path)
            knowledge.input_files["spec"] = [spec_path]
            self.logger.info(
                f"  → {len(knowledge.spec.functional_requirements)} requirements, "
                f"{len(knowledge.spec.register_descriptions)} registers, "
                f"{len(knowledge.spec.state_machines)} FSMs"
            )
        else:
            self.logger.warning("No specification provided")

        # ─── Step 2: Parse RTL ────────────────────────────────────
        if rtl_path:
            self.logger.info(f"Step 2: Parsing RTL: {rtl_path}")
            knowledge.rtl = parse_rtl(rtl_path)
            knowledge.input_files["rtl"] = knowledge.rtl.file_list
            self.logger.info(
                f"  → {len(knowledge.rtl.modules)} modules, "
                f"{knowledge.rtl.total_lines} lines, "
                f"top={knowledge.rtl.top_module}"
            )
        else:
            self.logger.warning("No RTL provided")

        # ─── Step 3: Parse UVM Testbench ──────────────────────────
        if tb_path:
            self.logger.info(f"Step 3: Parsing UVM testbench: {tb_path}")
            knowledge.tb = parse_uvm(tb_path)
            knowledge.input_files["tb"] = knowledge.tb.file_list
            self.logger.info(
                f"  → {len(knowledge.tb.drivers)} drivers, "
                f"{len(knowledge.tb.monitors)} monitors, "
                f"{len(knowledge.tb.scoreboards)} scoreboards"
            )
        else:
            self.logger.warning("No UVM testbench provided")

        # ─── Step 4: Parse Simulation Log ─────────────────────────
        if log_path:
            self.logger.info(f"Step 4: Parsing simulation log: {log_path}")
            knowledge.logs = parse_log(log_path)
            knowledge.input_files["log"] = [log_path]
            self.logger.info(
                f"  → {knowledge.logs.summary.total_errors} errors, "
                f"{knowledge.logs.summary.total_fatals} fatals, "
                f"status={knowledge.logs.summary.pass_fail}"
            )
        else:
            self.logger.warning("No simulation log provided")

        # ─── Step 5: Parse Coverage (Optional) ────────────────────
        if coverage_path:
            self.logger.info(f"Step 5: Parsing coverage: {coverage_path}")
            knowledge.coverage = parse_coverage(coverage_path)
            knowledge.input_files["coverage"] = [coverage_path]
        else:
            self.logger.info("Step 5: No coverage report provided (optional)")

        # ─── Step 6: Parse VCD Waveform (Optional) ────────────────
        if vcd_path:
            self.logger.info(f"Step 6: Parsing VCD waveform: {vcd_path}")
            knowledge.vcd = parse_vcd(vcd_path)
            knowledge.input_files["vcd"] = [vcd_path]
            if knowledge.vcd.tool_status == "ok":
                x_signals = sum(1 for s in knowledge.vcd.signals.values() if s.has_x)
                self.logger.info(
                    f"  → {len(knowledge.vcd.signals)} signals parsed "
                    f"({knowledge.vcd.parser_backend}), {x_signals} with X values"
                )
            else:
                self.logger.warning(f"  → VCD parsing skipped: {knowledge.vcd.tool_message}")
        else:
            self.logger.info("Step 6: No VCD waveform provided (optional)")

        # ─── Step 7: RAG Context Retrieval ────────────────────────
        if self.kb:
            self.logger.info("Step 7: Querying RAG knowledge base")
            knowledge.rag_context = self._retrieve_rag_context(knowledge)
        else:
            self.logger.info("Step 7: RAG disabled")

        # ─── Summary ─────────────────────────────────────────────
        self.logger.info("=" * 60)
        self.logger.info("Agent 1: Knowledge Extraction Complete")
        self.logger.info(f"  Spec requirements: {len(knowledge.spec.functional_requirements)}")
        self.logger.info(f"  RTL modules: {len(knowledge.rtl.modules)}")
        self.logger.info(f"  TB drivers: {len(knowledge.tb.drivers)}")
        self.logger.info(f"  Log errors: {knowledge.logs.summary.total_errors}")
        self.logger.info(f"  Simulation: {knowledge.logs.summary.pass_fail}")
        self.logger.info("=" * 60)

        return knowledge

    def _retrieve_rag_context(self, knowledge: UnifiedKnowledge) -> RAGContext:
        """Query RAG knowledge base for similar past failures."""
        try:
            retriever = Retriever(self.kb)

            # Build problem description from log errors
            error_messages = [
                e.message for e in knowledge.logs.errors
            ]
            problem = "; ".join(error_messages[:5]) if error_messages else ""

            if not problem:
                return RAGContext()

            context = retriever.retrieve_context(
                problem_description=problem,
                error_messages=error_messages,
            )

            if context.similar_failures:
                self.logger.info(
                    f"RAG found {len(context.similar_failures)} similar failures "
                    f"(confidence: {context.confidence:.2f})"
                )

            return context

        except Exception as e:
            self.logger.warning(f"RAG retrieval failed: {e}")
            return RAGContext()
