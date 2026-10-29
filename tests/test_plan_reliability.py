"""
Unit and integration tests for VeriSight Plan reliability improvements.

Tests:
1. Feature extraction with tables, lists, and full document context (no 12k char cutoff).
2. Functional coverage model generation with RTL port grounding and valid SystemVerilog syntax.
3. SVA assertion suite generation with complete port declarations and Slang AST compilation verification.
4. Coverage correlator hierarchical path normalization (stripping tb/dut scopes).
5. End-to-end VeriSightPlanner execution validating clean SV syntax.
"""

import unittest
import tempfile
from pathlib import Path

from verisight.plan.schemas import FeatureItem, VerificationPlanReport
from verisight.plan.feature_extractor import FeatureExtractor
from verisight.plan.coverage_architect import CoverageArchitect
from verisight.plan.assertion_architect import AssertionArchitect
from verisight.plan.test_planner import TestPlanner
from verisight.plan.coverage_correlator import CoverageCorrelator
from verisight.plan.coverage_ingest import CoverageIngester, SimulatorCoverageDB
from verisight.plan.planner_orchestrator import VeriSightPlanner
from verisight.parsers.sv_frontend import compile_text


class TestPlanReliability(unittest.TestCase):
    """Test suite ensuring 100% efficiency and reliability of VeriSight Plan."""

    def test_feature_extractor_tables_and_lists(self):
        """Verify feature extractor parses markdown tables and bullet lists correctly."""
        spec_text = """
# Arithmetic Logic Unit Specification

## Operation Encodings
| Opcode | Mnemonic | Description |
| :--- | :--- | :--- |
| 4'b0000 | ADD | Add operand_a and operand_b |
| 4'b0001 | SUB | Subtract operand_b from operand_a |
| 4'b0010 | AND | Bitwise AND of operands |

## Control Interface
- Reset: Active-low asynchronous reset rst_n initializes result to 0
- Handshake: Valid-ready protocol on bus interface
- Status: Carry and Zero flags asserted on boundary conditions
"""
        extractor = FeatureExtractor()
        features = extractor._deterministic_extract(spec_text, rtl_data=None)

        self.assertGreaterEqual(len(features), 5)
        titles = [f.title for f in features]
        # Verify table extraction
        self.assertTrue(any("4'b0000" in t for t in titles))
        self.assertTrue(any("4'b0001" in t for t in titles))
        # Verify bullet list extraction
        self.assertTrue(any("Reset" in t for t in titles))
        self.assertTrue(any("Handshake" in t for t in titles))

    def test_coverage_architect_grounding_and_sv_syntax(self):
        """Verify covergroups use real RTL ports, proper bit widths, and compile cleanly in Slang."""
        features = [
            FeatureItem(feature_id="FEAT-001", title="Addition Operation", description="Add operands"),
            FeatureItem(feature_id="FEAT-002", title="Carry Flag Generation", description="Carry flag for overflow"),
            FeatureItem(feature_id="FEAT-003", title="Zero Flag Output", description="Zero flag when result is zero"),
        ]
        rtl_info = {
            "ports": [
                {"name": "clk", "dir": "input", "width": 1},
                {"name": "rst_n", "dir": "input", "width": 1},
                {"name": "operand_a", "dir": "input", "width": "[7:0]"},
                {"name": "operand_b", "dir": "input", "width": 8},
                {"name": "op_sel", "dir": "input", "width": 4},
                {"name": "result", "dir": "output", "width": 8},
                {"name": "carry", "dir": "output", "width": 1},
                {"name": "zero", "dir": "output", "width": 1},
            ]
        }
        architect = CoverageArchitect()
        cgs = architect._deterministic_generate(features, design_name="alu", rtl_info=rtl_info)

        self.assertEqual(len(cgs), 1)
        cp_signals = [cp.target_signal for cp in cgs[0].coverpoints]

        # Verify coverpoints ground to actual port names
        self.assertIn("operand_a", cp_signals)
        self.assertIn("op_sel", cp_signals)
        self.assertIn("carry", cp_signals)
        self.assertIn("zero", cp_signals)

        # Verify 1-bit flags have binary bins
        carry_cp = next(cp for cp in cgs[0].coverpoints if cp.target_signal == "carry")
        bin_names = [b.bin_name for b in carry_cp.bins]
        self.assertIn("deasserted", bin_names)
        self.assertIn("asserted", bin_names)

        # Generate SystemVerilog code and validate syntax with Slang
        sv_code = architect.generate_sv_code(cgs, design_name="alu")
        self.assertIn("covergroup cg_alu_main @(posedge clk iff !rst_n);", sv_code)

        compile_res = compile_text(sv_code, name="coverage_model.sv")
        self.assertTrue(compile_res.syntax_ok, f"Slang syntax errors in coverage SV:\n{compile_res.status.notes}")

    def test_assertion_architect_ports_and_sv_syntax(self):
        """Verify generated assertion bind module declares all referenced ports and compiles cleanly."""
        features = [
            FeatureItem(feature_id="FEAT-001", title="Reset Output Zeroing", description="Outputs clear on reset"),
            FeatureItem(feature_id="FEAT-002", title="Zero Flag Logic", description="Zero flag logic"),
        ]
        rtl_info = {
            "ports": [
                {"name": "clk", "dir": "input", "width": 1},
                {"name": "rst_n", "dir": "input", "width": 1},
                {"name": "operand_a", "dir": "input", "width": 8},
                {"name": "operand_b", "dir": "input", "width": 8},
                {"name": "result", "dir": "output", "width": 8},
                {"name": "zero", "dir": "output", "width": 1},
                {"name": "carry", "dir": "output", "width": 1},
            ]
        }
        architect = AssertionArchitect()
        assertions = architect._deterministic_generate(features, design_name="alu", rtl_info=rtl_info)

        self.assertGreaterEqual(len(assertions), 3)
        # Verify functional reset assertion exists
        reset_prop = next((p for p in assertions if "reset" in p.name), None)
        self.assertIsNotNone(reset_prop)
        self.assertIn("!rst_n", reset_prop.expression)

        # Generate SystemVerilog assertion code
        sv_code = architect.generate_sv_code(assertions, design_name="alu", rtl_info=rtl_info)
        self.assertIn("module alu_assertions (", sv_code)
        self.assertIn("input logic [7:0] result", sv_code)
        self.assertIn("input logic zero", sv_code)

        # Verify clean Slang compilation
        compile_res = compile_text(sv_code, name="dut_assertions.sv")
        self.assertTrue(compile_res.syntax_ok, f"Slang syntax errors in assertion SV:\n{compile_res.status.notes}")

    def test_coverage_correlator_hierarchical_normalization(self):
        """Verify correlator strips UVM/testbench hierarchy (e.g. top.dut.cg -> cg)."""
        report = VerificationPlanReport(
            plan_id="test1",
            design_name="alu",
            timestamp="2026-10-25 00:00:00",
            spec_source="spec.md",
        )
        correlator = CoverageCorrelator()

        norm_leaf = correlator._norm("uvm_test_top.env.scoreboard.cg_alu_main")
        self.assertEqual(norm_leaf, "cgalumain")

        norm_path = correlator._norm("/tb_top/dut_inst/cp_op_sel")
        self.assertEqual(norm_path, "cpopsel")

    def test_planner_orchestrator_end_to_end(self):
        """Verify full VeriSightPlanner execution on example spec and RTL."""
        from unittest.mock import patch
        from verisight.agents.base_agent import BaseAgent

        spec_path = "examples/specs/alu_spec.md"
        rtl_path = "examples/rtl/"
        with patch.object(BaseAgent, "reason", side_effect=RuntimeError("Offline test fallback")):
            with tempfile.TemporaryDirectory() as td:
                planner = VeriSightPlanner(output_dir=td)
                report = planner.run(spec_path=spec_path, rtl_path=rtl_path, design_name="ALU")

                self.assertGreater(report.total_features, 10)
                self.assertGreaterEqual(report.total_tests, 20)
                self.assertGreater(report.total_coverage_points, 5)
                self.assertGreater(report.total_assertions, 5)
                self.assertTrue(report.sv_coverage_syntax_ok)
                self.assertTrue(report.sv_assertions_syntax_ok)

                cov_file = Path(td) / "coverage_model.sv"
                sva_file = Path(td) / "dut_assertions.sv"
                self.assertTrue(cov_file.exists())
                self.assertTrue(sva_file.exists())

    def test_planner_orchestrator_spec_only_no_rtl(self):
        """Verify VeriSightPlanner execution when RTL is omitted (pure spec-driven mode)."""
        from unittest.mock import patch
        from verisight.agents.base_agent import BaseAgent

        spec_path = "examples/specs/alu_spec.md"
        with patch.object(BaseAgent, "reason", side_effect=RuntimeError("Offline test fallback")):
            with tempfile.TemporaryDirectory() as td:
                planner = VeriSightPlanner(output_dir=td)
                # rtl_path is explicitly None: must not auto-discover or bind to any RTL
                report = planner.run(spec_path=spec_path, rtl_path=None, design_name="ALU_SPEC_ONLY")

                self.assertIsNone(report.rtl_source)
                self.assertGreater(report.total_features, 0)
                self.assertGreaterEqual(report.total_tests, 50)
                self.assertGreater(report.total_coverage_points, 10)
                self.assertGreater(report.total_assertions, 5)
                self.assertTrue(report.sv_coverage_syntax_ok)
                self.assertTrue(report.sv_assertions_syntax_ok)

                cov_file = Path(td) / "coverage_model.sv"
                sva_file = Path(td) / "dut_assertions.sv"
                self.assertTrue(cov_file.exists())
                self.assertTrue(sva_file.exists())


if __name__ == "__main__":
    unittest.main()
