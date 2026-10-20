"""
Tests for verisight.tools.sim_runner module.
"""

import os
from pathlib import Path
import pytest

from verisight.tools.sim_runner import (
    SimResult,
    find_best_simulator,
    run_simulation,
    execute_closed_loop_flow,
)


def test_find_best_simulator():
    """Verify simulator detection returns a valid string or None."""
    sim = find_best_simulator()
    assert sim is None or isinstance(sim, str)
    # If iverilog is on PATH, it should find iverilog
    if os.path.exists("/usr/bin/iverilog"):
        assert sim in ("iverilog", "vcs", "questa")


def test_sim_result_structure():
    """Verify SimResult dataclass attributes."""
    res = SimResult(
        simulator="iverilog",
        success=True,
        log_path="sim.log",
        vcd_path="sim.vcd",
        error_count=0,
        warning_count=1,
        duration_s=0.45,
    )
    assert res.simulator == "iverilog"
    assert res.success is True
    assert res.error_count == 0
    assert res.warning_count == 1
    assert res.duration_s == 0.45


def test_run_simulation_iverilog(tmp_path):
    """Run iverilog simulation on ALU RTL + TB and check outputs."""
    rtl_path = "examples/rtl/alu.sv"
    tb_path = "examples/tb/alu_tb.sv"
    
    if not Path(rtl_path).exists() or not Path(tb_path).exists():
        pytest.skip("ALU RTL or TB does not exist")
    
    sim = find_best_simulator()
    if sim != "iverilog" and not os.path.exists("/usr/bin/iverilog"):
        pytest.skip("iverilog is not installed on this system")

    result = run_simulation(
        rtl_files=rtl_path,
        tb_files=tb_path,
        output_dir=tmp_path,
        simulator="iverilog",
    )

    assert result.simulator == "iverilog"
    assert Path(result.log_path).exists()
    assert Path(result.log_path).stat().st_size > 0
    
    # Check that VCD was produced
    if result.vcd_path:
        assert Path(result.vcd_path).exists()


def test_execute_closed_loop_flow(tmp_path):
    """Test closed-loop simulation -> RCA -> Plan pipeline in airgap mode."""
    rtl_path = "examples/rtl/alu.sv"
    tb_path = "examples/tb/alu_tb.sv"
    spec_path = "examples/specs/alu_spec.md"

    if not Path(rtl_path).exists() or not Path(tb_path).exists():
        pytest.skip("ALU RTL or TB does not exist")

    sim = find_best_simulator()
    if not sim:
        pytest.skip("No simulator available on PATH")

    res = execute_closed_loop_flow(
        rtl_path=rtl_path,
        tb_path=tb_path,
        spec_path=spec_path,
        output_dir=str(tmp_path / "closed_loop_test"),
        simulator="iverilog",
        airgap=True,
        launch_browser=False,
    )

    assert "sim" in res
    assert "rca" in res
    assert "plan" in res
    assert "dashboards" in res

    dashboards = res["dashboards"]
    assert "debug_report_html" in dashboards
    assert Path(dashboards["debug_report_html"]).exists()
    assert "plan_cockpit_html" in dashboards
    assert Path(dashboards["plan_cockpit_html"]).exists()
