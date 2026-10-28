"""
Unit tests for the Spec-Driven Testbench Generation Agent (Workflow 4).
"""

import pytest
from pathlib import Path

from verisight.agents.spec_driven_tb_agent import SpecDrivenTestbenchAgent
from verisight.schemas.spec_driven_tb_schema import SpecDrivenTBResult


def test_spec_driven_tb_agent_input_validation(tmp_path):
    """Test that agent strictly enforces both Specification and RTL inputs."""
    agent = SpecDrivenTestbenchAgent(output_dir=str(tmp_path))

    # Missing spec
    with pytest.raises(ValueError, match="MANDATORY INPUT MISSING: Design Specification"):
        agent.validate_inputs(spec_path="", rtl_path="projects/ram/rtl/ram_rtl.sv")

    # Missing RTL
    with pytest.raises(ValueError, match="MANDATORY INPUT MISSING: RTL Source Code"):
        agent.validate_inputs(spec_path="projects/ram/specs/spec.md", rtl_path="")

    # Nonexistent spec
    with pytest.raises(FileNotFoundError):
        agent.validate_inputs(spec_path="nonexistent_spec.md", rtl_path="projects/ram/rtl/ram_rtl.sv")


def test_spec_driven_tb_agent_generation(tmp_path):
    """Test full 10-stage execution of the Spec-Driven Testbench Generation Agent on RAM."""
    spec_path = "projects/ram/specs/spec.md"
    rtl_path = "projects/ram/rtl/ram_rtl.sv"

    out_dir = tmp_path / "uvm_ram_tb"
    agent = SpecDrivenTestbenchAgent(output_dir=str(out_dir))

    result: SpecDrivenTBResult = agent.generate_testbench(
        spec_path=spec_path,
        rtl_path=rtl_path,
        output_dir=str(out_dir),
        run_sim=True,
    )

    # 1. Verify Mental Model
    assert result.mental_model.design_name == "ram_rtl"
    assert len(result.mental_model.ports) >= 6
    assert result.mental_model.clock_signal == "clk"
    assert result.mental_model.reset_signal == "rst_n"

    # 2. Verify Intent vs. Implementation Check
    # The agent MUST identify the off-by-one mismatch in ram_rtl.sv line 29!
    mismatches = [
        item for item in result.mental_model.intent_vs_implementation
        if item.classification == "Potential Mismatch"
    ]
    assert len(mismatches) >= 1
    assert "mem[addr+1]" in mismatches[0].evidence
    assert "MANDATORY SPEC GROUNDING" in mismatches[0].impact_on_reference_model

    # 3. Verify Atomic Requirements
    assert len(result.requirements) >= 5
    req_ids = [r.req_id for r in result.requirements]
    assert "REQ-001" in req_ids
    assert "REQ-003" in req_ids
    assert "REQ-004" in req_ids

    # 4. Verify Generated Files
    assert len(result.files_generated) >= 14
    expected_files = [
        "verif/ram_rtl_if.sv",
        "verif/ram_rtl_seq_item.sv",
        "verif/ram_rtl_driver.sv",
        "verif/ram_rtl_monitor.sv",
        "verif/ram_rtl_agent.sv",
        "verif/ram_rtl_reference_model.sv",
        "verif/ram_rtl_scoreboard.sv",
        "verif/ram_rtl_coverage.sv",
        "verif/ram_rtl_sequences.sv",
        "verif/ram_rtl_env.sv",
        "verif/ram_rtl_test.sv",
        "verif/ram_rtl_pkg.sv",
        "top/ram_rtl_tb_top.sv",
        "run.do",
        "Makefile",
    ]
    for ef in expected_files:
        assert (out_dir / ef).exists(), f"Expected file {ef} was not generated!"

    # 5. Verify Reference Model Adheres to Specification (NOT copying RTL bug)
    ref_model_content = (out_dir / "verif/ram_rtl_reference_model.sv").read_text()
    assert "golden_memory[tr.addr]" in ref_model_content
    # Ensure it did NOT copy the bug:
    assert "tr.addr + 1" not in ref_model_content
    assert "tr.addr+1" not in ref_model_content

    # 6. Verify Artifacts
    assert (out_dir / "mental_model.md").exists()
    assert (out_dir / "mental_model.json").exists()
    assert (out_dir / "verification_plan.md").exists()
    assert (out_dir / "verification_plan.json").exists()
    assert (out_dir / "traceability_matrix.md").exists()
    assert (out_dir / "traceability_matrix.json").exists()
    assert (out_dir / "validation_report.md").exists()
    assert (out_dir / "validation_report.json").exists()

    # 7. Verify Static Review
    assert result.static_validation.syntax_clean is True
