"""
VeriSight Pipeline Orchestrator.

Manages the sequential execution of all 5 agents:
  Agent 1 → Agent 2 → (conditional) Agent 3 → Agent 5 → Agent 4

  Agent 5 (Fix Generator) runs after Agent 2 (TB Bug path) or after
  Agent 3 (RTL Bug path). It degrades gracefully when confidence is
  below threshold, RTL/TB source is unavailable, or the LLM fails.

Handles early termination (TB Bug at Agent 2), intermediate artifact
persistence, error handling, and graceful degradation.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime

from verisight.config import get_config, VeriSightConfig
from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
from verisight.agents.agent2_classifier import RootCauseClassifierAgent
from verisight.agents.agent3_rtl_analyzer import RTLRootCauseAnalyzer
from verisight.agents.agent4_reporter import ReportGeneratorAgent
from verisight.agents.agent5_fix_generator import FixGeneratorAgent
from verisight.rag.knowledge_base import KnowledgeBase
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.schemas.classification import Classification
from verisight.schemas.rtl_analysis import RTLAnalysis
from verisight.schemas.report_schema import ErrorReport
from verisight.schemas.fix_schema import FixResult
from verisight.utils.file_utils import save_json
from verisight.utils.logger import get_logger, setup_logging

logger = get_logger("orchestrator")


class VeriSightPipeline:
    """
    Main pipeline orchestrator for the VeriSight debugging framework.

    Executes agents sequentially:
    1. Knowledge Extraction → knowledge.json
    2. Root Cause Classification → summary.json
    3. RTL Analysis (if RTL Bug) → xtrace.json, functional.json, etc.
    4. Report Generation → error.json, report.md, report.html, summary.txt
    """

    def __init__(self, config: Optional[VeriSightConfig] = None):
        """
        Initialize the pipeline.

        Args:
            config: Optional configuration override.
        """
        if config:
            from verisight.config import set_config
            set_config(config)

        self.config = get_config()
        self.kb: Optional[KnowledgeBase] = None

        # Initialize RAG if enabled
        if self.config.pipeline.enable_rag:
            self.kb = KnowledgeBase()
            try:
                self.kb.initialize_collections()
            except Exception as e:
                logger.warning(f"RAG initialization failed, continuing without RAG: {e}")
                self.kb = None

        # Initialize agents
        self.agent1 = KnowledgeExtractionAgent(knowledge_base=self.kb)
        self.agent2 = RootCauseClassifierAgent()
        self.agent3 = RTLRootCauseAnalyzer(output_dir=self.config.pipeline.output_dir)
        self.agent4 = ReportGeneratorAgent(
            output_dir=self.config.pipeline.output_dir,
            knowledge_base=self.kb,
        )
        self.agent5 = FixGeneratorAgent(
            output_dir=self.config.pipeline.output_dir,
            fix_subdir=self.config.fix.fix_output_subdir,
        )

        # Pipeline state
        self.knowledge: Optional[UnifiedKnowledge] = None
        self.classification: Optional[Classification] = None
        self.rtl_analysis: Optional[RTLAnalysis] = None
        self.fix_result: Optional[FixResult] = None
        self.report: Optional[ErrorReport] = None

    def run(
        self,
        spec_path: Optional[str] = None,
        rtl_path: Optional[str] = None,
        tb_path: Optional[str] = None,
        log_path: Optional[str] = None,
        coverage_path: Optional[str] = None,
    ) -> ErrorReport:
        """
        Execute the full debugging pipeline.

        Args:
            spec_path: Path to design specification (.md).
            rtl_path: Path to RTL source file(s) or directory.
            tb_path: Path to UVM testbench file(s) or directory.
            log_path: Path to simulation log file.
            coverage_path: Optional path to coverage report.

        Returns:
            ErrorReport — the final debugging report.
        """
        setup_logging(level=self.config.log_level)

        logger.info("╔" + "═" * 58 + "╗")
        logger.info("║     VeriSight — AI-Powered RTL/UVM Debugging Framework    ║")
        logger.info("║                    Pipeline Starting                       ║")
        logger.info("╚" + "═" * 58 + "╝")
        logger.info("")

        output_dir = Path(self.config.pipeline.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # ═══════════════════════════════════════════════════════════
        # AGENT 1: Knowledge Extraction
        # ═══════════════════════════════════════════════════════════
        try:
            self.knowledge = self.agent1.execute(
                spec_path=spec_path,
                rtl_path=rtl_path,
                tb_path=tb_path,
                log_path=log_path,
                coverage_path=coverage_path,
            )

            if self.config.pipeline.save_intermediates:
                save_json(self.knowledge.spec, output_dir / "spec.json")
                save_json(self.knowledge.rtl, output_dir / "rtl.json")
                save_json(self.knowledge.tb, output_dir / "tb.json")
                save_json(self.knowledge.logs, output_dir / "log.json")
                save_json(self.knowledge, output_dir / "knowledge.json")

        except Exception as e:
            logger.error(f"Agent 1 failed: {e}")
            raise RuntimeError(f"Knowledge extraction failed: {e}")

        # ═══════════════════════════════════════════════════════════
        # AGENT 2: Root Cause Classification
        # ═══════════════════════════════════════════════════════════
        try:
            self.classification = self.agent2.execute(self.knowledge)

            if self.config.pipeline.save_intermediates:
                save_json(self.classification, output_dir / "summary.json")

        except Exception as e:
            logger.error(f"Agent 2 failed: {e}")
            # Create fallback classification
            self.classification = Classification(
                classification="Unknown",
                confidence=0,
                reason=f"Classification failed: {e}",
                missing_artifacts=["Agent 2 execution"],
            )

        # ═══════════════════════════════════════════════════════════
        # CONDITIONAL: Agent 3 (only for RTL Bug or Unknown)
        # ═══════════════════════════════════════════════════════════
        if self.classification.classification == "TB Bug":
            logger.info("")
            logger.info("┌─ TB Bug detected — skipping RTL analysis (Agent 3)")
            logger.info("└─ Proceeding to Fix Generator (Agent 5) then Report Generator (Agent 4)")
            logger.info("")
        elif self.classification.classification in ("RTL Bug", "Unknown"):
            try:
                self.rtl_analysis = self.agent3.execute(
                    self.knowledge, self.classification
                )
            except Exception as e:
                logger.error(f"Agent 3 failed: {e}")
                self.rtl_analysis = None
        else:
            logger.info(f"Classification: {self.classification.classification} — skipping Agent 3")

        # ═══════════════════════════════════════════════════════════
        # AGENT 5: Automated Fix Generator
        # ═══════════════════════════════════════════════════════════
        if self.config.fix.enabled and self.classification.classification in ("TB Bug", "RTL Bug"):
            try:
                self.fix_result = self.agent5.execute(
                    self.knowledge,
                    self.classification,
                    self.rtl_analysis,
                )

                if self.config.pipeline.save_intermediates:
                    save_json(self.fix_result, output_dir / "fix.json")

            except Exception as e:
                logger.warning(f"Agent 5 (Fix Generator) failed: {e} — continuing without fix")
                self.fix_result = FixResult(
                    fix_available=False,
                    issue_type="none",
                    fix_type="no_fix",
                    decline_reason=f"Fix generation failed unexpectedly: {e}",
                    limitations=["Unexpected exception during fix generation; see pipeline logs."],
                )
        else:
            if not self.config.fix.enabled:
                logger.info("Fix generation disabled (VERISIGHT_FIX_ENABLED=false)")
            else:
                logger.info(
                    f"Classification '{self.classification.classification}' does not "
                    "require fix generation — skipping Agent 5"
                )

        # ═══════════════════════════════════════════════════════════
        # AGENT 4: Report Generation
        # ═══════════════════════════════════════════════════════════
        try:
            self.report = self.agent4.execute(
                self.knowledge,
                self.classification,
                self.rtl_analysis,
                self.fix_result,
            )
        except Exception as e:
            logger.error(f"Agent 4 failed: {e}")
            raise RuntimeError(f"Report generation failed: {e}")

        # ═══════════════════════════════════════════════════════════
        # Pipeline Complete
        # ═══════════════════════════════════════════════════════════
        logger.info("")
        logger.info("╔" + "═" * 58 + "╗")
        logger.info("║              VeriSight Pipeline Complete                   ║")
        logger.info("╚" + "═" * 58 + "╝")
        logger.info(f"  Classification: {self.report.classification}")
        logger.info(f"  Confidence:     {self.report.confidence}%")
        logger.info(f"  Root Cause:     {self.report.root_cause[:80]}")
        logger.info(f"  Output:         {output_dir}/")
        logger.info("")

        return self.report
