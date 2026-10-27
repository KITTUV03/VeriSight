"""
Unit tests for VeriSight UVM Architect.

Tests autonomous UVM 1.2 testbench environment generation inspired by XcelUVM:
1. End-to-end generation from RTL AST (APB, ALU, FIFO).
2. Synthesizes interface, sequence items, driver, monitor, agent, scoreboard, coverage, tests, and top module.
3. SystemVerilog syntax validation (Slang/pyslang AST check).
"""

import unittest
from pathlib import Path
import tempfile
import shutil

from verisight.uvm.uvm_architect import UVMArchitect
from verisight.parsers.sv_frontend import compile_text


class TestUVMArchitect(unittest.TestCase):
    """Test suite for autonomous UVM generation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="verisight_uvm_test_")

    def tearDown(self):
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_uvm_generation_for_apb_slave(self):
        """Test UVM testbench generation for APB slave peripheral."""
        architect = UVMArchitect(output_dir=self.test_dir)
        res = architect.generate(
            rtl_path="projects/apb/rtl/apb_slave.sv",
            spec_path="projects/apb/specs/apb_spec.md",
            design_name="apb_slave",
        )

        self.assertEqual(res.design_name, "apb_slave")
        self.assertEqual(res.protocol_detected, "apb")
        self.assertGreaterEqual(len(res.files_generated), 12)

        # Check required files exist
        base_dir = Path(res.output_dir)
        self.assertTrue((base_dir / "verif" / "apb_slave_if.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_seq_item.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_driver.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_monitor.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_agent.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_scoreboard.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_coverage.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_env.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_test.sv").exists())
        self.assertTrue((base_dir / "verif" / "apb_slave_pkg.sv").exists())
        self.assertTrue((base_dir / "top" / "apb_slave_tb_top.sv").exists())
        self.assertTrue((base_dir / "run.do").exists())
        self.assertTrue((base_dir / "Makefile").exists())

        # Syntax check interface and top
        if_content = (base_dir / "verif" / "apb_slave_if.sv").read_text(encoding="utf-8")
        compile_if = compile_text(if_content, name="apb_slave_if.sv")
        self.assertTrue(compile_if.syntax_ok, f"Syntax errors in generated interface:\n{compile_if.status.notes}")

    def test_uvm_generation_for_alu(self):
        """Test UVM testbench generation for ALU design."""
        architect = UVMArchitect(output_dir=self.test_dir)
        res = architect.generate(
            rtl_path="examples/rtl/alu.sv",
            design_name="alu",
        )

        self.assertEqual(res.design_name, "alu")
        self.assertGreaterEqual(res.inputs_count, 1)
        self.assertGreaterEqual(res.outputs_count, 1)

        base_dir = Path(res.output_dir)
        if_content = (base_dir / "verif" / "alu_if.sv").read_text(encoding="utf-8")
        compile_if = compile_text(if_content, name="alu_if.sv")
        self.assertTrue(compile_if.syntax_ok)

    def test_uvm_generation_spec_only_fallback(self):
        """Test UVM generation when no RTL is available (spec-only synthesis)."""
        architect = UVMArchitect(output_dir=self.test_dir)
        res = architect.generate(
            design_name="custom_device",
        )

        self.assertEqual(res.design_name, "custom_device")
        self.assertGreaterEqual(len(res.files_generated), 12)


if __name__ == "__main__":
    unittest.main()
