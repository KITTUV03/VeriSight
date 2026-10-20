"""
Unit tests for VeriSight Plan Dynamic Coverage Closure Ingestion.

Validates:
1. Simulator Coverage DB Ingestion (Questa UCDB, Synopsys vDB, JSON)
2. Planned vs. Actual Coverage Correlation per Feature
3. Unhit coverage holes identification
4. Targeted directed sequence synthesis
5. Live Coverage Cockpit HTML rendering
"""

import unittest
import tempfile
from pathlib import Path

from verisight.plan.schemas import (
    FeatureItem,
    TestScenario,
    CovergroupDef,
    CoveragePoint,
    CoverageBin,
    VerificationPlanReport,
)
from verisight.plan.coverage_ingest import CoverageIngester
from verisight.plan.coverage_correlator import CoverageCorrelator
from verisight.plan.traceability import (
    build_traceability_matrix,
    export_csv,
    export_markdown,
    export_html,
)


class TestCoverageCockpit(unittest.TestCase):
    """Test suite for Coverage Cockpit and Ingestion engine."""

    def test_coverage_ingester_ucdb(self):
        """Test ingestion of Questa UCDB text coverage report."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            ucdb_content = """
            Covergroup /tb/cg_alu_operations
              Coverpoint cp_opcode
                bin_add : 120 hits [COVERED]
                bin_sub : 85 hits [COVERED]
                bin_overflow : 0 hits [UNCOVERED]
            """
            report_file = tmp_path / "questa_ucdb.txt"
            report_file.write_text(ucdb_content)

            ingester = CoverageIngester()
            db = ingester.ingest(str(report_file))

            self.assertIn(db.simulator_format, ("Questa_UCDB", "Generic_EDA_Text"))
            self.assertEqual(db.total_bins, 3)
            self.assertEqual(db.hit_bins, 2)
            self.assertEqual(db.unhit_bins_count, 1)
            self.assertEqual(db.overall_coverage_pct, round((2 / 3) * 100, 2))

    def test_coverage_ingester_json(self):
        """Test ingestion of JSON coverage dump."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            json_content = """
            {
              "simulator": "Questa",
              "covergroups": [
                {
                  "group_name": "cg_alu",
                  "coverpoints": [
                    {
                      "name": "cp_op",
                      "bins": [
                        {"name": "bin_add", "hits": 50, "status": "Covered"},
                        {"name": "bin_overflow", "hits": 0, "status": "Unhit", "condition": "cout == 1"}
                      ]
                    }
                  ]
                }
              ]
            }
            """
            json_file = tmp_path / "coverage.json"
            json_file.write_text(json_content)

            ingester = CoverageIngester()
            db = ingester.ingest(str(json_file))

            self.assertEqual(db.simulator_format, "JSON")
            self.assertEqual(db.total_bins, 2)
            self.assertEqual(db.hit_bins, 1)
            self.assertEqual(db.unhit_bins_count, 1)

    def test_coverage_correlator_planned_vs_actual(self):
        """Test correlation of planned features with simulator coverage DB."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            feat1 = FeatureItem(
                feature_id="FEAT-001",
                title="32-bit ALU Addition & Overflow",
                description="Handles add and overflow detection",
            )
            feat2 = FeatureItem(
                feature_id="FEAT-002",
                title="Logical Operations",
                description="AND, OR, XOR operations",
            )

            cp1 = CoveragePoint(
                coverage_id="COV-001",
                feature_ids=["FEAT-001"],
                name="cp_add_ops",
                target_signal="op_result",
                bins=[
                    CoverageBin(bin_name="bin_add_normal", condition="cout == 0"),
                    CoverageBin(bin_name="bin_add_overflow", condition="cout == 1 && cin == 1"),
                ],
                description="Addition coverage",
            )
            cp2 = CoveragePoint(
                coverage_id="COV-002",
                feature_ids=["FEAT-002"],
                name="cp_logic_ops",
                target_signal="op_logic",
                bins=[
                    CoverageBin(bin_name="bin_and", condition="op == AND"),
                    CoverageBin(bin_name="bin_or", condition="op == OR"),
                ],
                description="Logic coverage",
            )

            cg = CovergroupDef(
                group_name="cg_alu",
                sample_trigger="@(posedge clk)",
                coverpoints=[cp1, cp2],
                description="ALU covergroup",
            )

            matrix = build_traceability_matrix(
                features=[feat1, feat2],
                tests=[],
                covergroups=[cg],
                assertions=[],
            )

            report = VerificationPlanReport(
                plan_id="plan-123",
                design_name="ALU",
                timestamp="2026-10-20 10:00:00",
                spec_source="alu_spec.md",
                features=[feat1, feat2],
                covergroups=[cg],
                traceability_matrix=matrix,
            )

            cov_text = """
            Covergroup /tb/cg_alu
              Coverpoint cp_add_ops
                bin_add_normal : 45 hits [COVERED]
                bin_add_overflow : 0 hits [UNCOVERED]
              Coverpoint cp_logic_ops
                bin_and : 30 hits [COVERED]
                bin_or : 28 hits [COVERED]
            """
            cov_file = tmp_path / "sim_cov.txt"
            cov_file.write_text(cov_text)

            correlator = CoverageCorrelator()
            updated_report = correlator.correlate(report, coverage_path=str(cov_file))

            # FEAT-001 has 1 hit out of 2 bins => 50.0%
            self.assertEqual(updated_report.features[0].actual_coverage, 50.0)
            self.assertEqual(len(updated_report.features[0].unhit_bins), 1)
            self.assertEqual(updated_report.features[0].unhit_bins[0]["bin_name"], "bin_add_overflow")
            self.assertIsNotNone(updated_report.features[0].directed_stimulus_hint)
            self.assertIn("directed_closure_seq", updated_report.features[0].directed_stimulus_hint)

            # FEAT-002 has 2 hits out of 2 bins => 100.0%
            self.assertEqual(updated_report.features[1].actual_coverage, 100.0)
            self.assertEqual(len(updated_report.features[1].unhit_bins), 0)

            # Overall coverage
            self.assertEqual(updated_report.total_bins, 4)
            self.assertEqual(updated_report.hit_bins, 3)
            self.assertEqual(updated_report.actual_coverage_overall, 75.0)

            # Export and verify HTML Cockpit rendering
            html_out = tmp_path / "verification_plan.html"
            export_html(updated_report, html_out)

            html_text = html_out.read_text()
            self.assertIn("Live Coverage Cockpit", html_text)
            self.assertIn("50.0% Hit", html_text)
            self.assertIn("bin_add_overflow", html_text)
            self.assertIn("Generate directed sequence to hit remaining", html_text)
            self.assertIn("directedModal", html_text)


if __name__ == "__main__":
    unittest.main()
