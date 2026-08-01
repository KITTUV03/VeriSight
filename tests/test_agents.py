"""
Unit tests for VeriSight agents.

Tests Agent 1 (Knowledge Extraction) and Agent 2 (Classification)
deterministic functionality. Agent 2 LLM reasoning is tested via
the fallback path (no API key needed).
"""

import pytest
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SPEC_PATH = str(EXAMPLES_DIR / "specs" / "alu_spec.md")
RTL_PATH = str(EXAMPLES_DIR / "rtl")
TB_PATH = str(EXAMPLES_DIR / "tb")
LOG_PATH = str(EXAMPLES_DIR / "logs" / "sim.log")


class TestAgent1Knowledge:
    """Tests for Agent 1: Knowledge Extraction."""

    def test_agent1_creates_unified_knowledge(self):
        from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
        agent = KnowledgeExtractionAgent(knowledge_base=None)
        knowledge = agent.execute(
            spec_path=SPEC_PATH,
            rtl_path=RTL_PATH,
            tb_path=TB_PATH,
            log_path=LOG_PATH,
        )
        assert knowledge is not None
        assert len(knowledge.spec.functional_requirements) > 0
        assert len(knowledge.rtl.modules) > 0
        assert len(knowledge.tb.drivers) > 0
        assert len(knowledge.logs.errors) > 0

    def test_agent1_partial_inputs(self):
        """Agent 1 should work with partial inputs."""
        from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
        agent = KnowledgeExtractionAgent(knowledge_base=None)
        knowledge = agent.execute(
            rtl_path=RTL_PATH,
            log_path=LOG_PATH,
        )
        assert knowledge is not None
        assert len(knowledge.rtl.modules) > 0
        assert len(knowledge.logs.errors) > 0
        # Spec and TB should be empty but not None
        assert knowledge.spec is not None
        assert knowledge.tb is not None

    def test_agent1_log_only(self):
        """Agent 1 should work with just a log file."""
        from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
        agent = KnowledgeExtractionAgent(knowledge_base=None)
        knowledge = agent.execute(log_path=LOG_PATH)
        assert knowledge.logs.summary.pass_fail == "FAIL"


class TestAgent2Classifier:
    """Tests for Agent 2: Root Cause Classifier (deterministic fallback)."""

    def _get_knowledge(self):
        """Helper to get unified knowledge for testing."""
        from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
        agent = KnowledgeExtractionAgent(knowledge_base=None)
        return agent.execute(
            spec_path=SPEC_PATH,
            rtl_path=RTL_PATH,
            tb_path=TB_PATH,
            log_path=LOG_PATH,
        )

    def test_agent2_pre_analysis_detects_x(self):
        """Pre-analysis should detect X values in simulation output."""
        from verisight.agents.agent2_classifier import RootCauseClassifierAgent
        knowledge = self._get_knowledge()
        agent = RootCauseClassifierAgent()
        pre_analysis = agent._pre_analyze(knowledge)
        assert pre_analysis["x_detected"] is True, "Should detect X values"

    def test_agent2_pre_analysis_detects_reset_issues(self):
        """Pre-analysis should detect missing reset."""
        from verisight.agents.agent2_classifier import RootCauseClassifierAgent
        knowledge = self._get_knowledge()
        agent = RootCauseClassifierAgent()
        pre_analysis = agent._pre_analyze(knowledge)
        assert len(pre_analysis["reset_issues"]) > 0, "Should detect reset issues"

    def test_agent2_fallback_classifies_rtl_bug(self):
        """Fallback classification should identify RTL bug for ALU example."""
        from verisight.agents.agent2_classifier import RootCauseClassifierAgent
        knowledge = self._get_knowledge()
        agent = RootCauseClassifierAgent()
        pre_analysis = agent._pre_analyze(knowledge)
        classification = agent._fallback_classification(knowledge, pre_analysis)
        assert classification.classification == "RTL Bug"
        assert classification.confidence >= 80
        assert "X" in classification.reason or "reset" in classification.reason.lower()


class TestAgent3RTLAnalyzer:
    """Tests for Agent 3: RTL Root Cause Analyzer."""

    def _get_knowledge_and_classification(self):
        from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
        from verisight.agents.agent2_classifier import RootCauseClassifierAgent
        a1 = KnowledgeExtractionAgent(knowledge_base=None)
        knowledge = a1.execute(
            spec_path=SPEC_PATH, rtl_path=RTL_PATH,
            tb_path=TB_PATH, log_path=LOG_PATH,
        )
        a2 = RootCauseClassifierAgent()
        pre = a2._pre_analyze(knowledge)
        classification = a2._fallback_classification(knowledge, pre)
        return knowledge, classification

    def test_agent3_x_tracer(self):
        """X-Tracer should find uninitialized result register."""
        from verisight.agents.agent3_rtl_analyzer import RTLRootCauseAnalyzer
        knowledge, classification = self._get_knowledge_and_classification()
        agent = RTLRootCauseAnalyzer()
        analysis = agent.execute(knowledge, classification)

        assert len(analysis.xtrace.x_origins) > 0, "Should find X origins"
        # Check that 'result' is identified as uninitialized
        uninit = [x.origin_signal for x in analysis.xtrace.x_origins]
        assert "result" in uninit, f"Should find 'result' uninitialized, found: {uninit}"

    def test_agent3_functional_analyzer(self):
        """Functional analyzer should find missing reset violation."""
        from verisight.agents.agent3_rtl_analyzer import RTLRootCauseAnalyzer
        knowledge, classification = self._get_knowledge_and_classification()
        agent = RTLRootCauseAnalyzer()
        analysis = agent.execute(knowledge, classification)

        # Check functional issues mention reset
        has_reset_issue = any(
            "reset" in i.issue_type.lower() or "reset" in i.description.lower()
            for i in analysis.functional.issues
        )
        assert has_reset_issue, "Should detect missing reset functional issue"

    def test_agent3_primary_root_cause(self):
        """Primary root cause should be X Propagation."""
        from verisight.agents.agent3_rtl_analyzer import RTLRootCauseAnalyzer
        knowledge, classification = self._get_knowledge_and_classification()
        agent = RTLRootCauseAnalyzer()
        analysis = agent.execute(knowledge, classification)

        assert analysis.primary_category == "X Propagation"
        assert analysis.confidence >= 80
