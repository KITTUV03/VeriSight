"""
Unit and integration tests for Agent 5 — Automated Fix Generator.

Tests cover:
  - RTL fix generation (with LLM monkeypatched)
  - TB fix generation
  - Low-confidence decline (threshold enforcement)
  - Black-box RTL handling
  - Malformed / empty LLM output
  - Multiple UVM errors (cascading detection)
  - Validation levels 1-3
  - Confidence breakdown computation
  - Orchestrator integration (Agent 5 called and fix_result attached to report)
  - CLI --no-fix and --min-confidence flag wiring
  - Agent 4 report rendering (Markdown, HTML, summary.txt) with fix section
  - Backward compatibility (fix=None when disabled)

No live LLM API is required.  LLM is monkeypatched throughout.
"""

import json
import pytest
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SPEC_PATH = str(EXAMPLES_DIR / "specs" / "alu_spec.md")
RTL_PATH = str(EXAMPLES_DIR / "rtl")
TB_PATH = str(EXAMPLES_DIR / "tb")
LOG_PATH = str(EXAMPLES_DIR / "logs" / "sim.log")
OUTPUT_DIR = str(Path(__file__).parent.parent / "output" / "test_fix")


# ─── Helpers ───────────────────────────────────────────────────────

def _make_knowledge(with_rtl=True, with_tb=True, with_spec=True, with_log=True):
    from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
    agent = KnowledgeExtractionAgent(knowledge_base=None)
    return agent.execute(
        spec_path=SPEC_PATH if with_spec else None,
        rtl_path=RTL_PATH if with_rtl else None,
        tb_path=TB_PATH if with_tb else None,
        log_path=LOG_PATH if with_log else None,
    )


def _make_rtl_classification(confidence=90):
    from verisight.schemas.classification import Classification
    return Classification(
        classification="RTL Bug",
        confidence=confidence,
        component="alu",
        reason="The result register is not initialized in the reset clause.",
        category="X Propagation",
        rtl_reference="examples/rtl/alu.sv:25",
        recommended_fix="Add reset clause for result register.",
    )


def _make_tb_classification(confidence=85):
    from verisight.schemas.classification import Classification
    return Classification(
        classification="TB Bug",
        confidence=confidence,
        component="alu_scoreboard",
        reason="Scoreboard uses == instead of !== for X comparison.",
        category="Scoreboard",
        tb_reference="examples/tb/alu_scoreboard.sv:44",
        recommended_fix="Change comparison operator.",
    )


def _make_good_rtl_llm_response():
    return json.dumps({
        "fix_available": True,
        "issue_type": "RTL",
        "fix_type": "code_patch",
        "rtl_available": True,
        "confidence_breakdown": {
            "spec_agreement": 0.95,
            "root_cause_certainty": 0.90,
            "code_evidence": 0.85,
            "uvm_log_evidence": 0.90,
            "fix_consistency": 0.80,
            "validation_evidence": 0.0,
        },
        "target_file": "examples/rtl/alu.sv",
        "target_module": "alu",
        "target_lines": "20-30",
        "root_cause_summary": "result register lacks reset.",
        "expected_behavior": "On rst_n=0 result should be 0.",
        "observed_behavior": "result is X after reset.",
        "reasoning": "Adding result <= 0 in reset clause clears X.",
        "patch": "- result <= result;\n+ result <= 0;",
        "corrected_code": (
            "always_ff @(posedge clk or negedge rst_n) begin\n"
            "    if (!rst_n) begin\n"
            "        result <= 0;\n"
            "    end\n"
            "end"
        ),
        "assumptions": ["No other reset source exists."],
        "limitations": [],
        "cascading_errors": ["UVM_ERROR: MISMATCH result=xx expected=5f"],
        "decline_reason": "",
    })


def _make_good_tb_llm_response():
    return json.dumps({
        "fix_available": True,
        "issue_type": "TB",
        "fix_type": "code_patch",
        "rtl_available": False,
        "confidence_breakdown": {
            "spec_agreement": 0.80,
            "root_cause_certainty": 0.85,
            "code_evidence": 0.75,
            "uvm_log_evidence": 0.80,
            "fix_consistency": 0.70,
            "validation_evidence": 0.0,
        },
        "target_file": "examples/tb/alu_scoreboard.sv",
        "target_module": "alu_scoreboard",
        "target_lines": "44-44",
        "root_cause_summary": "Scoreboard uses == which returns false for X values.",
        "expected_behavior": "X values should not pass equality check silently.",
        "observed_behavior": "X output passes silently when == is used.",
        "reasoning": "Using !== will correctly detect X values.",
        "patch": "- if (actual_data == expected_data)\n+ if (actual_data !== expected_data)",
        "corrected_code": "if (actual_data !== expected_data)\n    `uvm_error(...)",
        "assumptions": [],
        "limitations": [],
        "cascading_errors": [],
        "decline_reason": "",
    })


def _make_low_confidence_llm_response():
    return json.dumps({
        "fix_available": True,
        "issue_type": "RTL",
        "fix_type": "code_patch",
        "rtl_available": True,
        "confidence_breakdown": {
            "spec_agreement": 0.1,
            "root_cause_certainty": 0.1,
            "code_evidence": 0.1,
            "uvm_log_evidence": 0.1,
            "fix_consistency": 0.1,
            "validation_evidence": 0.0,
        },
        "target_file": "examples/rtl/alu.sv",
        "target_module": "alu",
        "target_lines": "",
        "root_cause_summary": "Uncertain.",
        "expected_behavior": "",
        "observed_behavior": "",
        "reasoning": "",
        "patch": "",
        "corrected_code": "",
        "assumptions": [],
        "limitations": ["Low confidence."],
        "cascading_errors": [],
        "decline_reason": "",
    })


def _make_decline_llm_response():
    return json.dumps({
        "fix_available": False,
        "issue_type": "RTL",
        "fix_type": "no_fix",
        "rtl_available": False,
        "confidence_breakdown": {
            "spec_agreement": 0.0, "root_cause_certainty": 0.0,
            "code_evidence": 0.0, "uvm_log_evidence": 0.0,
            "fix_consistency": 0.0, "validation_evidence": 0.0,
        },
        "target_file": "",
        "target_module": "",
        "target_lines": "",
        "root_cause_summary": "",
        "expected_behavior": "",
        "observed_behavior": "",
        "reasoning": "",
        "patch": "",
        "corrected_code": "",
        "assumptions": [],
        "limitations": [],
        "cascading_errors": [],
        "decline_reason": "RTL source unavailable.",
    })


# ─── Schema / Confidence Tests ──────────────────────────────────────

class TestConfidenceBreakdown:
    def test_full_confidence(self):
        from verisight.schemas.fix_schema import ConfidenceBreakdown
        cbd = ConfidenceBreakdown(
            spec_agreement=1.0, root_cause_certainty=1.0,
            code_evidence=1.0, uvm_log_evidence=1.0,
            fix_consistency=1.0, validation_evidence=1.0,
        )
        assert abs(cbd.compute_total() - 1.0) < 1e-9

    def test_zero_confidence(self):
        from verisight.schemas.fix_schema import ConfidenceBreakdown
        assert ConfidenceBreakdown().compute_total() == 0.0

    def test_spec_agreement_weight(self):
        from verisight.schemas.fix_schema import ConfidenceBreakdown
        cbd = ConfidenceBreakdown(spec_agreement=1.0)
        assert abs(cbd.compute_total() - 0.25) < 1e-9


class TestValidationResult:
    def test_not_validated(self):
        from verisight.schemas.fix_schema import ValidationResult
        assert ValidationResult().overall_status() == "Not Validated"

    def test_syntax_validated(self):
        from verisight.schemas.fix_schema import ValidationResult
        assert ValidationResult(syntax="PASS").overall_status() == "Syntax Validated"

    def test_spec_validated(self):
        from verisight.schemas.fix_schema import ValidationResult
        val = ValidationResult(syntax="PASS", structural="PASS", specification="PASS")
        assert val.overall_status() == "Specification Validated"

    def test_simulation_validated(self):
        from verisight.schemas.fix_schema import ValidationResult
        val = ValidationResult(syntax="PASS", specification="PASS", simulation="PASS")
        assert val.overall_status() == "Simulation Validated"


# ─── RTL Fix Tests ──────────────────────────────────────────────────

class TestFixGeneratorRTL:
    def _get_agent(self, tmp_path):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        return FixGeneratorAgent(str(tmp_path), "fix")

    def test_rtl_fix_generated(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda prompt, system: _make_good_rtl_llm_response())
        result = agent.execute(_make_knowledge(), _make_rtl_classification())
        assert result.fix_available is True
        assert result.issue_type == "RTL"
        assert result.confidence > 0.70
        assert result.patch != ""

    def test_rtl_fix_saves_artifacts(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda prompt, system: _make_good_rtl_llm_response())
        agent.execute(_make_knowledge(), _make_rtl_classification())
        assert (tmp_path / "fix" / "fix.json").exists()
        assert (tmp_path / "fix" / "proposed.patch").exists()
        assert (tmp_path / "fix" / "corrected_snippet.sv").exists()

    def test_rtl_fix_validation_runs(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda prompt, system: _make_good_rtl_llm_response())
        result = agent.execute(_make_knowledge(), _make_rtl_classification())
        assert result.validation.syntax in ("PASS", "FAIL")
        assert result.validation_status != ""


# ─── TB Fix Tests ───────────────────────────────────────────────────

class TestFixGeneratorTB:
    def _get_agent(self, tmp_path):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        return FixGeneratorAgent(str(tmp_path), "fix")

    def test_tb_fix_generated(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda prompt, system: _make_good_tb_llm_response())
        result = agent.execute(_make_knowledge(), _make_tb_classification())
        assert result.fix_available is True
        assert result.issue_type == "TB"
        assert result.rtl_available is False


# ─── Decline Tests ──────────────────────────────────────────────────

class TestFixGeneratorDecline:
    def _get_agent(self, tmp_path, min_conf=0.70):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        from verisight.config import VeriSightConfig, FixConfig, set_config
        set_config(VeriSightConfig(fix=FixConfig(enabled=True, min_confidence=min_conf)))
        return FixGeneratorAgent(str(tmp_path), "fix")

    def test_low_confidence_declined(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path, min_conf=0.70)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda prompt, system: _make_low_confidence_llm_response())
        result = agent.execute(_make_knowledge(), _make_rtl_classification())
        assert result.fix_available is False
        assert result.decline_reason != ""

    def test_llm_explicit_decline(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda prompt, system: _make_decline_llm_response())
        result = agent.execute(_make_knowledge(), _make_rtl_classification())
        assert result.fix_available is False

    def test_unknown_classification_declined(self, tmp_path):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        from verisight.schemas.classification import Classification
        agent = FixGeneratorAgent(str(tmp_path), "fix")
        c = Classification(classification="Unknown", confidence=50, reason="Insufficient.")
        result = agent.execute(_make_knowledge(), c)
        assert result.fix_available is False

    def test_spec_bug_declined(self, tmp_path):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        from verisight.schemas.classification import Classification
        agent = FixGeneratorAgent(str(tmp_path), "fix")
        c = Classification(classification="Spec Bug", confidence=80, reason="Ambiguous spec.")
        result = agent.execute(_make_knowledge(), c)
        assert result.fix_available is False


# ─── Black-box RTL Tests ────────────────────────────────────────────

class TestFixGeneratorBlackBox:
    def _spec_based_response(self):
        data = json.loads(_make_good_rtl_llm_response())
        data["rtl_available"] = False
        data["fix_type"] = "specification_based"
        return json.dumps(data)

    def test_blackbox_sets_spec_based_type(self, monkeypatch, tmp_path):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        from verisight.schemas.classification import Classification
        agent = FixGeneratorAgent(str(tmp_path), "fix")
        monkeypatch.setattr(agent.llm, "generate",
                            lambda *a, **kw: self._spec_based_response())
        # Use a classification that references a non-existent file
        # so _load_source returns rtl_available=False (black-box path)
        classification = Classification(
            classification="RTL Bug",
            confidence=90,
            reason="Missing reset.",
            category="X Propagation",
            rtl_reference="/nonexistent/blackbox_module.sv:25",
        )
        result = agent.execute(_make_knowledge(with_rtl=False), classification)
        assert result.fix_type == "specification_based"
        assert result.rtl_available is False


# ─── Malformed LLM Output Tests ─────────────────────────────────────

class TestMalformedLLM:
    def _get_agent(self, tmp_path):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        return FixGeneratorAgent(str(tmp_path), "fix")

    def test_empty_response_declines(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate", lambda *a, **kw: "")
        result = agent.execute(_make_knowledge(), _make_rtl_classification())
        assert result.fix_available is False

    def test_plain_text_declines(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda *a, **kw: "I cannot generate a fix.")
        result = agent.execute(_make_knowledge(), _make_rtl_classification())
        assert result.fix_available is False

    def test_llm_exception_declines_gracefully(self, monkeypatch, tmp_path):
        agent = self._get_agent(tmp_path)
        monkeypatch.setattr(agent.llm, "generate",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Network error")))
        result = agent.execute(_make_knowledge(), _make_rtl_classification())
        assert result.fix_available is False
        assert result.decline_reason != ""


# ─── Cascading Error Tests ──────────────────────────────────────────

class TestCascadingErrors:
    def _knowledge_with_errors(self, msgs):
        from verisight.schemas.log_schema import LogKnowledge, LogEntry
        from verisight.schemas.knowledge_schema import UnifiedKnowledge
        from verisight.schemas.spec_schema import SpecKnowledge
        from verisight.schemas.rtl_schema import RTLKnowledge
        from verisight.schemas.tb_schema import TBKnowledge
        log = LogKnowledge(errors=[
            LogEntry(severity="UVM_ERROR", message=m, timestamp="10 ns")
            for m in msgs
        ])
        return UnifiedKnowledge(spec=SpecKnowledge(), rtl=RTLKnowledge(),
                                tb=TBKnowledge(), logs=log)

    def test_single_error_returned(self):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        k = self._knowledge_with_errors(["MISMATCH result=5f expected=ff"])
        agent = FixGeneratorAgent()
        assert len(agent._detect_cascading_errors(k)) == 1

    def test_repeated_pattern_detected(self):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        msgs = [
            "MISMATCH result=xx expected=5f",
            "MISMATCH result=xx expected=3c",
            "MISMATCH result=xx expected=ff",
        ]
        k = self._knowledge_with_errors(msgs)
        agent = FixGeneratorAgent()
        cascading = agent._detect_cascading_errors(k)
        assert len(cascading) == 3


# ─── Syntax Validation Tests ────────────────────────────────────────

class TestSyntaxValidation:
    def _agent(self):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        return FixGeneratorAgent()

    def test_balanced_begin_end_passes(self):
        ok, _ = self._agent()._validate_syntax(
            "always_ff @(posedge clk) begin\n    result <= 0;\nend\n")
        assert ok is True

    def test_unbalanced_begin_fails(self):
        ok, notes = self._agent()._validate_syntax(
            "always_ff @(posedge clk) begin\n    result <= 0;\n")
        assert ok is False

    def test_placeholder_fails(self):
        ok, notes = self._agent()._validate_syntax("assign out = your_signal_here;")
        assert ok is False
        assert "placeholder" in notes.lower()

    def test_empty_code_fails(self):
        ok, _ = self._agent()._validate_syntax("")
        assert ok is False

    def test_unbalanced_parens_fails(self):
        ok, _ = self._agent()._validate_syntax("assign out = (a + b;")
        assert ok is False


# ─── Orchestrator Integration ───────────────────────────────────────

class TestOrchestratorIntegration:
    def _run(self, tmp_path, fix_enabled=True, min_conf=0.70):
        from verisight.config import VeriSightConfig, LLMConfig, PipelineConfig, FixConfig, set_config
        from verisight.orchestrator import VeriSightPipeline

        config = VeriSightConfig(
            llm=LLMConfig(api_key=""),
            pipeline=PipelineConfig(save_intermediates=True, enable_rag=False,
                                    output_dir=str(tmp_path)),
            fix=FixConfig(enabled=fix_enabled, min_confidence=min_conf),
        )
        set_config(config)
        pipeline = VeriSightPipeline(config=config)
        return pipeline.run(spec_path=SPEC_PATH, rtl_path=RTL_PATH,
                            tb_path=TB_PATH, log_path=LOG_PATH)

    def test_pipeline_completes_with_fix_enabled(self, tmp_path):
        report = self._run(tmp_path, fix_enabled=True)
        assert report is not None
        assert report.classification in ("RTL Bug", "TB Bug", "Unknown")

    def test_pipeline_completes_with_fix_disabled(self, tmp_path):
        report = self._run(tmp_path, fix_enabled=False)
        assert report is not None
        assert report.fix is None

    def test_fix_json_saved_when_enabled(self, tmp_path):
        self._run(tmp_path, fix_enabled=True)
        assert (tmp_path / "fix.json").exists()

    def test_no_fix_json_when_disabled(self, tmp_path):
        self._run(tmp_path, fix_enabled=False)
        assert not (tmp_path / "fix.json").exists()


# ─── Agent 4 Report Rendering ───────────────────────────────────────

class TestAgent4FixReporting:
    def _build(self, fix_result):
        from verisight.agents.agent1_knowledge import KnowledgeExtractionAgent
        from verisight.agents.agent2_classifier import RootCauseClassifierAgent
        from verisight.agents.agent4_reporter import ReportGeneratorAgent
        import uuid
        from datetime import datetime

        a1 = KnowledgeExtractionAgent(knowledge_base=None)
        knowledge = a1.execute(spec_path=SPEC_PATH, rtl_path=RTL_PATH,
                               tb_path=TB_PATH, log_path=LOG_PATH)
        a2 = RootCauseClassifierAgent()
        pre = a2._pre_analyze(knowledge)
        classification = a2._fallback_classification(knowledge, pre)

        agent4 = ReportGeneratorAgent(output_dir=OUTPUT_DIR, knowledge_base=None)
        report = agent4._build_error_report(
            knowledge, classification, None, fix_result,
            str(uuid.uuid4())[:8], datetime.now().isoformat()
        )
        ctx = agent4._build_report_context(knowledge, classification, None, report, fix_result)
        return agent4, ctx

    def test_markdown_has_fix_section_when_available(self):
        from verisight.schemas.fix_schema import FixResult, ValidationResult
        fix = FixResult(
            fix_available=True, issue_type="RTL", fix_type="code_patch",
            rtl_available=True, confidence=0.88,
            target_file="examples/rtl/alu.sv", target_module="alu",
            root_cause_summary="Missing reset.",
            patch="- x\n+ y",
            corrected_code="always_ff begin\nend",
            validation=ValidationResult(syntax="PASS"),
            validation_status="Syntax Validated",
        )
        agent4, ctx = self._build(fix)
        md = agent4._generate_markdown_report(ctx)
        assert "Agent 5" in md
        assert "```diff" in md
        assert "Validation Results" in md

    def test_markdown_shows_decline_reason(self):
        from verisight.schemas.fix_schema import FixResult
        fix = FixResult(fix_available=False, decline_reason="Confidence below threshold.",
                        confidence_threshold_used=0.70)
        agent4, ctx = self._build(fix)
        md = agent4._generate_markdown_report(ctx)
        assert "Fix generation declined" in md
        assert "Confidence below threshold" in md

    def test_markdown_no_fix_section_when_none(self):
        agent4, ctx = self._build(fix_result=None)
        md = agent4._generate_markdown_report(ctx)
        assert "Agent 5" not in md

    def test_html_has_fix_section_when_available(self):
        from verisight.schemas.fix_schema import FixResult, ValidationResult
        fix = FixResult(
            fix_available=True, issue_type="RTL", fix_type="code_patch",
            rtl_available=True, confidence=0.80,
            root_cause_summary="Missing reset.", patch="- x\n+ y",
            corrected_code="always_ff begin end",
            validation=ValidationResult(syntax="PASS"),
            validation_status="Syntax Validated",
        )
        agent4, ctx = self._build(fix)
        html = agent4._generate_html_report(ctx)
        assert "fix-recommendation" in html
        assert "Fix Recommendation (Agent 5)" in html

    def test_html_no_fix_section_when_none(self):
        agent4, ctx = self._build(fix_result=None)
        html = agent4._generate_html_report(ctx)
        assert "fix-recommendation" not in html

    def test_error_json_has_fix_field(self):
        from verisight.schemas.fix_schema import FixResult
        fix = FixResult(fix_available=False, decline_reason="Test.",
                        confidence_threshold_used=0.70)
        agent4, ctx = self._build(fix)
        data = ctx["report"].model_dump()
        assert "fix" in data
        assert data["fix"]["fix_available"] is False

    def test_error_json_fix_none_when_no_fix(self):
        agent4, ctx = self._build(fix_result=None)
        data = ctx["report"].model_dump()
        assert data.get("fix") is None


# ─── CLI Flag Tests ─────────────────────────────────────────────────

class TestCLIFlags:
    def _parse(self, extra_args):
        import sys, importlib
        from unittest.mock import patch
        test_args = ["verisight", "--log", LOG_PATH] + extra_args
        with patch.object(sys, "argv", test_args):
            import main as m
            importlib.reload(m)
            return m.parse_args()

    def test_no_fix_flag_parsed(self):
        args = self._parse(["--no-fix"])
        assert args.no_fix is True

    def test_min_confidence_parsed(self):
        args = self._parse(["--min-confidence", "0.85"])
        assert abs(args.min_confidence - 0.85) < 1e-9

    def test_default_no_fix_false(self):
        args = self._parse([])
        assert args.no_fix is False

    def test_default_min_confidence_none(self):
        args = self._parse([])
        assert args.min_confidence is None
