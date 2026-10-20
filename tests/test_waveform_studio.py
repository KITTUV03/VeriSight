"""
Unit tests for VeriSight Silicon Waveform Studio (VCD / FSDB Trace Viewer).
"""

import unittest
from pathlib import Path

from verisight.reporter.waveform_studio import (
    load_sample_vcd,
    generate_waveform_studio_tab,
)
from verisight.parsers.vcd_parser import parse_vcd
from verisight.plan.schemas import (
    VerificationPlanReport,
    FeatureItem,
    CovergroupDef,
    CoveragePoint,
    CoverageBin,
    TraceabilityRow,
)
from verisight.plan.traceability import export_html


class TestWaveformStudio(unittest.TestCase):
    """Test suite for VCD Waveform Studio."""

    def test_vcd_parser_and_sample_loading(self):
        """Verify parsing of sample VCD files."""
        alu_vcd = Path("examples/waveforms/alu_failure_trace.vcd")
        self.assertTrue(alu_vcd.exists(), "Sample ALU VCD must exist")

        vcd_data = parse_vcd(str(alu_vcd))
        self.assertEqual(vcd_data.tool_status, "ok")
        self.assertGreater(len(vcd_data.signals), 0)

        # Verify key signals exist
        sig_names = [s.name for s in vcd_data.signals.values()]
        self.assertIn("clk", sig_names)
        self.assertTrue(any("op" in s for s in sig_names))
        self.assertTrue(any("result" in s for s in sig_names))
        self.assertIn("error", sig_names)

        # Test load_sample_vcd helper
        loaded = load_sample_vcd(str(alu_vcd))
        self.assertEqual(loaded["name"], "alu_failure_trace.vcd")
        self.assertGreater(len(loaded["signals"]), 0)

    def test_waveform_tab_html_generation(self):
        """Verify generated HTML/JS structure of Waveform Studio."""
        html = generate_waveform_studio_tab(
            vcd_path="examples/waveforms/alu_failure_trace.vcd",
            failure_timestamp_ns=65.0,
            failure_label="Assertion Failure: Overflow Corruption",
            tab_id="tab-waveform",
        )

        self.assertIn('id="tab-waveform"', html)
        self.assertIn('id="waveCanvas"', html)
        self.assertIn('id="waveRulerCanvas"', html)
        self.assertIn('id="waveSignalsPanel"', html)
        self.assertIn('id="waveCursorLine"', html)
        self.assertIn('id="waveErrorBand"', html)
        self.assertIn("parseClientVcd", html)
        self.assertIn("renderWaveforms", html)
        self.assertIn("jumpToFailure", html)
        self.assertIn("exportWaveformPng", html)
        self.assertIn("65.0", html)

    def test_verification_plan_html_waveform_integration(self):
        """Verify verification_plan.html exports with embedded waveform viewer."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "verification_plan.html"
            feat = FeatureItem(
                feature_id="FEAT-001",
                title="ALU 8-bit Addition",
                description="Perform addition",
                category="Functional",
                source_section="Sec 1",
                priority="Critical",
                actual_coverage=92.0,
                target_coverage=100.0,
            )
            report = VerificationPlanReport(
                plan_id="test_plan",
                design_name="ALU",
                timestamp="2026-10-20 12:00:00",
                spec_source="spec.md",
                features=[feat],
                covergroups=[],
                traceability_matrix=[
                    TraceabilityRow(
                        feature_id="FEAT-001",
                        feature_title="ALU 8-bit Addition",
                        actual_coverage=92.0,
                        status="Partial",
                    )
                ],
            )
            export_html(report, out_file)
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")

            # Check Waveform tab button & tab pane exist
            self.assertIn("Simulation Waveform Viewer", content)
            self.assertIn('id="tab-waveform"', content)
            self.assertIn('id="waveCanvas"', content)


if __name__ == "__main__":
    unittest.main()
