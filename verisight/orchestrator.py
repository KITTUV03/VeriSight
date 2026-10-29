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
from verisight.schemas.classification import Classification, EvidenceItem
from verisight.schemas.rtl_analysis import RTLAnalysis
from verisight.schemas.report_schema import ErrorReport
from verisight.schemas.fix_schema import FixResult
from verisight.utils.file_utils import save_json
from verisight.utils.logger import get_logger, setup_logging

logger = get_logger("orchestrator")


def consensus_arbiter(
    initial: Classification,
    rtl_analysis: Optional[RTLAnalysis],
    knowledge: UnifiedKnowledge,
) -> Classification:
    """
    Consensus Arbiter: Reassesses Agent 2's initial diagnosis and confidence
    using Agent 3's deterministic tool evidence.

    Prioritizes reproducible tool evidence (X-trace, CDC, FSM deadlocks, lint)
    over unsupported LLM claims. Does NOT force false agreement when agents disagree.
    Preserves explicit RTL_BUG, TB_BUG, SPEC_BUG, or UNKNOWN/inconclusive outcomes.
    """
    if rtl_analysis is None:
        return initial

    has_concrete_rtl_evidence = (
        len(rtl_analysis.xtrace.real_traces) > 0
        or (len(rtl_analysis.xtrace.uninitialized_registers) > 0 and rtl_analysis.xtrace.severity in ("critical", "high"))
        or (len(rtl_analysis.cdc.crossings) > 0 and rtl_analysis.cdc.severity == "high")
        or any(iss.severity in ("high", "critical") for iss in rtl_analysis.functional.issues)
        or any(iss.severity in ("high", "critical") for iss in rtl_analysis.protocol.issues)
        or (rtl_analysis.confidence >= 70 and bool(rtl_analysis.primary_root_cause))
    )

    arbiter_evidence = list(initial.evidence)

    if has_concrete_rtl_evidence:
        # Definitive tool evidence for RTL bug
        if initial.classification == "TB Bug":
            logger.warning(
                "Consensus Arbiter: Reassessing initial 'TB Bug' classification. "
                "Agent 3 deterministic analysis revealed concrete RTL defect: %s",
                rtl_analysis.primary_root_cause,
            )
            arbiter_evidence.append(EvidenceItem(
                source="rtl_analysis",
                reference="Agent 3 deterministic evidence",
                description=f"Tool evidence overrides TB hypothesis: {rtl_analysis.primary_root_cause}",
                snippet=rtl_analysis.xtrace.summary or rtl_analysis.primary_root_cause,
            ))
            return Classification(
                classification="RTL Bug",
                confidence=max(initial.confidence, rtl_analysis.confidence, 80),
                component=rtl_analysis.primary_category or initial.component or "RTL",
                category=rtl_analysis.primary_category or "RTL Defect",
                reason=(
                    f"Consensus Arbiter overridden: Agent 3 deterministic analysis identified "
                    f"concrete RTL root cause: {rtl_analysis.primary_root_cause} (prioritizing reproducible tool evidence)."
                ),
                evidence=arbiter_evidence,
                recommended_fix=initial.recommended_fix or f"Fix RTL defect in {rtl_analysis.primary_category}",
            )
        elif initial.classification == "RTL Bug":
            return Classification(
                classification="RTL Bug",
                confidence=min(100, max(initial.confidence, rtl_analysis.confidence) + 5),
                component=initial.component or rtl_analysis.primary_category,
                category=initial.category or rtl_analysis.primary_category,
                reason=f"{initial.reason} [Corroborated by Agent 3 tool evidence: {rtl_analysis.primary_root_cause}]",
                evidence=arbiter_evidence,
                recommended_fix=initial.recommended_fix,
            )
        else:
            return Classification(
                classification="RTL Bug",
                confidence=max(initial.confidence, rtl_analysis.confidence, 75),
                component=rtl_analysis.primary_category or "RTL",
                category=rtl_analysis.primary_category,
                reason=f"Agent 3 identified concrete RTL defect: {rtl_analysis.primary_root_cause}",
                evidence=arbiter_evidence,
                recommended_fix=initial.recommended_fix,
            )

    # If no concrete RTL evidence found:
    if initial.classification == "TB Bug":
        return Classification(
            classification="TB Bug",
            confidence=min(100, initial.confidence + 5),
            component=initial.component or "Testbench",
            category=initial.category or "TB Defect",
            reason=f"{initial.reason} [Agent 3 deterministic checks confirmed no RTL defects]",
            evidence=arbiter_evidence,
            recommended_fix=initial.recommended_fix,
        )
    elif initial.classification == "Spec Bug":
        return initial
    elif initial.classification == "RTL Bug":
        logger.warning(
            "Consensus Arbiter: Agent 2 hypothesized 'RTL Bug' but Agent 3 found NO corroborating RTL evidence. "
            "Marking outcome as inconclusive/Unknown to avoid forcing false consensus."
        )
        return Classification(
            classification="Unknown",
            confidence=max(20, initial.confidence - 30),
            component=initial.component,
            category="Inconclusive",
            reason=(
                "Inconclusive: Agent 2 hypothesized RTL Bug, but deterministic tool checks (X-tracer, CDC, lint) "
                "found no supporting RTL defect. Evidence is insufficient or contradictory."
            ),
            evidence=arbiter_evidence,
            recommended_fix="Investigate waveform and testbench stimulus around failure time.",
        )
    else:
        return Classification(
            classification="Unknown",
            confidence=initial.confidence,
            component=initial.component,
            category="Inconclusive",
            reason="Inconclusive evidence: neither RTL analysis nor simulation logs established a definitive root cause.",
            evidence=arbiter_evidence,
            recommended_fix=initial.recommended_fix,
        )


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
        vcd_path: Optional[str] = None,
    ) -> ErrorReport:
        """
        Execute the full debugging pipeline.

        Args:
            spec_path: Path to design specification (.md).
            rtl_path: Path to RTL source file(s) or directory.
            tb_path: Path to UVM testbench file(s) or directory.
            log_path: Path to simulation log file.
            coverage_path: Optional path to coverage report.
            vcd_path: Optional path to a simulation waveform (VCD), parsed
                into knowledge.vcd for Agent 2/3 to use as debugging evidence,
                independent of whether real x-tracer analysis is enabled.

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
                vcd_path=vcd_path,
            )

            if self.config.pipeline.save_intermediates:
                save_json(self.knowledge.spec, output_dir / "spec.json")
                save_json(self.knowledge.rtl, output_dir / "rtl.json")
                save_json(self.knowledge.tb, output_dir / "tb.json")
                save_json(self.knowledge.logs, output_dir / "log.json")
                if self.knowledge.vcd:
                    save_json(self.knowledge.vcd, output_dir / "vcd_summary.json")
                save_json(self.knowledge, output_dir / "knowledge.json")

        except Exception as e:
            logger.error(f"Agent 1 failed: {e}")
            raise RuntimeError(f"Knowledge extraction failed: {e}")

        # ═══════════════════════════════════════════════════════════
        # 2. AGENT 2: Root Cause Classification (Initial Diagnosis)
        # ═══════════════════════════════════════════════════════════
        try:
            initial_classification = self.agent2.execute(self.knowledge)
        except Exception as e:
            logger.error(f"Agent 2 failed: {e}")
            initial_classification = Classification(
                classification="Unknown",
                confidence=0,
                reason=f"Classification failed: {e}",
                missing_artifacts=["Agent 2 execution"],
            )

        # ═══════════════════════════════════════════════════════════
        # 3. AGENT 3: Deterministic Analysis (RTL, X-Tracer, CDC, Lint)
        # ═══════════════════════════════════════════════════════════
        try:
            logger.info("Agent 3: Running deterministic RTL & verification analysis")
            self.rtl_analysis = self.agent3.execute(
                self.knowledge, initial_classification
            )
        except Exception as e:
            logger.error(f"Agent 3 failed: {e}")
            self.rtl_analysis = None

        # ═══════════════════════════════════════════════════════════
        # 4. CONSENSUS ARBITER
        # ═══════════════════════════════════════════════════════════
        self.classification = consensus_arbiter(
            initial_classification, self.rtl_analysis, self.knowledge
        )
        logger.info(
            f"Consensus Arbiter Finalized: {self.classification.classification} "
            f"({self.classification.confidence}%) — {self.classification.reason[:100]}"
        )
        if self.config.pipeline.save_intermediates:
            save_json(self.classification, output_dir / "summary.json")

        # ═══════════════════════════════════════════════════════════
        # 5. AGENT 4: Report Generation (Evidence-Backed Report)
        # ═══════════════════════════════════════════════════════════
        try:
            self.report = self.agent4.execute(
                self.knowledge,
                self.classification,
                self.rtl_analysis,
                None,
            )
        except Exception as e:
            logger.error(f"Agent 4 failed: {e}")
            raise RuntimeError(f"Report generation failed: {e}")

        # ═══════════════════════════════════════════════════════════
        # 6. AGENT 5: Automated Fix Generator (Using Finalized Diagnosis)
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

                # Attach fix to report and update final report files
                if self.report and self.fix_result:
                    self.report.fix = self.fix_result
                    self.agent4.execute(
                        self.knowledge,
                        self.classification,
                        self.rtl_analysis,
                        self.fix_result,
                    )

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
        # Pipeline Complete
        # ═══════════════════════════════════════════════════════════
        logger.info("")
        logger.info("╔" + "═" * 58 + "╗")
        logger.info("║              VeriSight Pipeline Complete                   ║")
        logger.info("╚" + "═" * 58 + "╝")
        logger.info(f"  Classification: {self.report.classification}")
        logger.info(f"  Root Cause:     {self.report.root_cause[:80]}")
        logger.info(f"  Output:         {output_dir}/")
        logger.info("")

        return self.report
