"""
Integration tests for VeriSight pipeline orchestrator.

Tests the full pipeline execution on the ALU example using
deterministic (no-LLM) mode.
"""

import pytest
import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SPEC_PATH = str(EXAMPLES_DIR / "specs" / "alu_spec.md")
RTL_PATH = str(EXAMPLES_DIR / "rtl")
TB_PATH = str(EXAMPLES_DIR / "tb")
LOG_PATH = str(EXAMPLES_DIR / "logs" / "sim.log")
OUTPUT_DIR = str(Path(__file__).parent.parent / "output" / "test_run")


class TestPipelineIntegration:
    """Integration tests for the full VeriSight pipeline."""

    def _run_pipeline(self):
        """Helper to run the full pipeline."""
        from verisight.config import VeriSightConfig, LLMConfig, PipelineConfig
        from verisight.orchestrator import VeriSightPipeline

        config = VeriSightConfig(
            llm=LLMConfig(api_key=""),  # No LLM — forces fallback
            pipeline=PipelineConfig(
                save_intermediates=True,
                enable_rag=False,  # Disable RAG for tests
                output_dir=OUTPUT_DIR,
            ),
        )

        pipeline = VeriSightPipeline(config=config)
        return pipeline.run(
            spec_path=SPEC_PATH,
            rtl_path=RTL_PATH,
            tb_path=TB_PATH,
            log_path=LOG_PATH,
        )

    def test_pipeline_produces_report(self):
        """Pipeline should produce a final ErrorReport."""
        report = self._run_pipeline()
        assert report is not None
        assert report.classification in ("RTL Bug", "TB Bug", "Spec Bug", "Unknown")
        assert report.confidence > 0
        assert report.root_cause != ""

    def test_pipeline_classifies_alu_as_rtl_bug(self):
        """ALU example should be classified as RTL Bug."""
        report = self._run_pipeline()
        assert report.classification == "RTL Bug", \
            f"Expected 'RTL Bug', got '{report.classification}'"

    def test_pipeline_identifies_x_propagation(self):
        """Pipeline should identify X propagation as the category."""
        report = self._run_pipeline()
        assert "X" in report.category or "Propagation" in report.category, \
            f"Expected X Propagation category, got '{report.category}'"

    def test_pipeline_generates_output_files(self):
        """Pipeline should generate all output files."""
        self._run_pipeline()
        output = Path(OUTPUT_DIR)
        assert (output / "error.json").exists(), "Missing error.json"
        assert (output / "summary.json").exists(), "Missing summary.json"
        assert (output / "report.md").exists(), "Missing report.md"
        assert (output / "report.html").exists(), "Missing report.html"
        assert (output / "summary.txt").exists(), "Missing summary.txt"

    def test_pipeline_generates_intermediate_jsons(self):
        """Pipeline should save intermediate JSON artifacts."""
        self._run_pipeline()
        output = Path(OUTPUT_DIR)
        assert (output / "spec.json").exists(), "Missing spec.json"
        assert (output / "rtl.json").exists(), "Missing rtl.json"
        assert (output / "tb.json").exists(), "Missing tb.json"
        assert (output / "log.json").exists(), "Missing log.json"
        assert (output / "knowledge.json").exists(), "Missing knowledge.json"

    def test_error_json_valid(self):
        """error.json should be valid and contain required fields."""
        self._run_pipeline()
        error_path = Path(OUTPUT_DIR) / "error.json"
        with open(error_path) as f:
            data = json.load(f)

        assert "classification" in data
        assert "confidence" in data
        assert "root_cause" in data
        assert "recommended_fixes" in data
        assert isinstance(data["recommended_fixes"], list)
        assert data["confidence"] > 0

    def test_report_mentions_result_signal(self):
        """Report should mention the 'result' signal as affected."""
        report = self._run_pipeline()
        assert "result" in report.affected_signals, \
            f"Should identify 'result' as affected, found: {report.affected_signals}"

    def test_report_has_evidence(self):
        """Report should include evidence chain."""
        report = self._run_pipeline()
        assert len(report.evidence) > 0, "Report should have evidence"

    def test_report_has_fixes(self):
        """Report should include recommended fixes."""
        report = self._run_pipeline()
        assert len(report.recommended_fixes) > 0, "Report should have fixes"

    def test_analysis_jsons_generated(self):
        """RTL analysis sub-module JSONs should be generated."""
        self._run_pipeline()
        analysis_dir = Path(OUTPUT_DIR) / "analysis"
        assert (analysis_dir / "xtrace.json").exists(), "Missing xtrace.json"
        assert (analysis_dir / "functional.json").exists(), "Missing functional.json"
        assert (analysis_dir / "lint.json").exists(), "Missing lint.json"
