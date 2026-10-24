"""
Regression and validation test suite for VeriSight 8 Critical Fixes.
Covers:
1. CLI argument validation (main.py)
2. Simulator routing and UVM detection (sim_runner.py)
3. AST and Signal Resolution with Escaped Identifiers (xtracer_runner.py)
4. Binary coverage database handling & CoverageFormatError (coverage_parser.py)
5. Dynamic VCD Slicing (vcd_parser.py)
6. Consensus Arbiter in Orchestrator (orchestrator.py)
7. Agent 5 Sandbox Hardening & Anti-Tamper Security (agent5_fix_generator.py)
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ─── 1. CLI Validation Tests ──────────────────────────────────────────

def test_cli_argument_choices_and_defaults():
    from main import parse_args

    # Valid commands
    valid_cmds = ["start", "wizard", "train", "train-kb", "learn", "plan",
                  "sim", "simulate", "serve", "server", "web", "cockpit", "ui"]
    for cmd in valid_cmds:
        args = parse_args([cmd])
        assert args.command == cmd
        assert args.simulator == "auto"

    # Invalid command should exit
    with pytest.raises(SystemExit):
        parse_args(["unsupported_cmd"])

    # Simulator choices
    valid_sims = ["auto", "verilator", "iverilog", "xsim", "dsim", "vcs", "questa", "xcelium"]
    for sim in valid_sims:
        args = parse_args(["start", "--simulator", sim])
        assert args.simulator == sim

    with pytest.raises(SystemExit):
        parse_args(["start", "--simulator", "unknown_sim"])


def test_cli_xtrace_comma_separated_signals():
    from main import parse_args

    args = parse_args(["start", "--xtrace", "--xtrace-signal", "req,ack,data[0]"])
    assert args.xtrace is True
    assert args.xtrace_signal == "req,ack,data[0]"


# ─── 2. Simulator Routing & UVM Detection Tests ───────────────────────

def test_is_uvm_testbench(tmp_path):
    from verisight.tools.sim_runner import is_uvm_testbench

    # Non-UVM testbench
    plain_tb = tmp_path / "plain_tb.sv"
    plain_tb.write_text("module tb; initial $display(\"hello\"); endmodule")
    assert is_uvm_testbench(str(plain_tb)) is False

    # UVM testbench with comments and imports
    uvm_tb = tmp_path / "uvm_tb.sv"
    uvm_tb.write_text("""
        // `include "uvm_macros.svh" (commented out)
        /* block comment
           import uvm_pkg::*;
        */
        `include "uvm_macros.svh"
        import uvm_pkg::*;
        module tb;
        endmodule
    """)
    assert is_uvm_testbench(str(uvm_tb)) is True


def test_resolve_simulator_priorities():
    from verisight.tools.sim_runner import resolve_simulator, SimulationError

    with patch("shutil.which") as mock_which:
        # Non-UVM auto routing prefers iverilog -> verilator -> xvlog
        mock_which.side_effect = lambda bin: "/usr/bin/" + bin if bin in ("iverilog", "verilator") else None
        sim = resolve_simulator("auto", is_uvm=False)
        assert sim == "iverilog"

        mock_which.side_effect = lambda bin: "/usr/bin/" + bin if bin in ("vsim", "xvlog") else None
        sim_uvm = resolve_simulator("auto", is_uvm=True)
        assert sim_uvm == "questa"

        # Explicit iverilog with UVM testbench must fail with clear error
        with pytest.raises(SimulationError) as exc_info:
            resolve_simulator("iverilog", is_uvm=True)
        assert "does not support" in str(exc_info.value) and "UVM" in str(exc_info.value)


# ─── 3. Signal Resolution and Escaped Identifiers ─────────────────────

def test_resolve_and_validate_signals_with_escaped_identifiers():
    from verisight.tools.xtracer_runner import resolve_and_validate_signals, signal_priority_score
    from verisight.schemas.knowledge_schema import UnifiedKnowledge
    from verisight.schemas.vcd_schema import VCDData, VCDSignalWave

    knowledge = UnifiedKnowledge()
    knowledge.vcd = VCDData(signals={
        "tb.dut.ready": VCDSignalWave(name="ready", hierarchy="tb.dut.ready"),
        "tb.dut.data[0]": VCDSignalWave(name="data[0]", hierarchy="tb.dut.data[0]"),
        r"\tb.dut.escaped_bus[0] ": VCDSignalWave(name="escaped_bus[0]", hierarchy=r"\tb.dut.escaped_bus[0] "),
    })

    candidates = resolve_and_validate_signals(r"\escaped_bus[0] ", knowledge, top_module="alu")
    assert r"\escaped_bus[0] " in candidates
    assert "escaped_bus[0]" in candidates or any("escaped_bus" in c for c in candidates)

    # Control signal gets higher priority than data signal
    assert signal_priority_score("ready") > signal_priority_score("data[0]")
    assert signal_priority_score("valid") > signal_priority_score("payload")


# ─── 4. Binary Coverage Conversion & Format Detection ─────────────────

def test_binary_coverage_handling(tmp_path):
    from verisight.parsers.coverage_parser import parse_coverage, CoverageFormatError

    # 1. Nonexistent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        parse_coverage(str(tmp_path / "nonexistent.ucdb"))

    # 2. Binary UCDB file raises CoverageFormatError when vcover not found
    binary_ucdb = tmp_path / "sim.ucdb"
    binary_ucdb.write_bytes(b"\x00\x01\x02\x03\x00UCDB_BINARY_HEADER")
    with patch("shutil.which", return_value=None):
        with pytest.raises(CoverageFormatError) as exc_info:
            parse_coverage(str(binary_ucdb))
        assert "vcover" in str(exc_info.value)

    # 3. Binary VDB directory raises CoverageFormatError when urg not found
    vdb_dir = tmp_path / "simv.vdb"
    vdb_dir.mkdir()
    with patch("shutil.which", return_value=None):
        with pytest.raises(CoverageFormatError) as exc_info:
            parse_coverage(str(vdb_dir))
        assert "urg" in str(exc_info.value)

    # 4. Text coverage parses cleanly
    text_cov = tmp_path / "report.txt"
    text_cov.write_text("Line coverage = 88.5%\nBranch coverage = 75.0%\n")
    cov = parse_coverage(str(text_cov))
    assert cov.code_coverage.get("line_coverage") == 88.5
    assert cov.code_coverage.get("branch_coverage") == 75.0


# ─── 5. Dynamic VCD Slicing Tests ─────────────────────────────────────

def test_query_vcd_window_boundaries_and_slicing(tmp_path):
    from verisight.parsers.vcd_parser import query_vcd_window
    from verisight.schemas.vcd_schema import VCDData, VCDSignalWave, VCDTransition

    # 1. Missing VCD handled gracefully without exception
    res = query_vcd_window(str(tmp_path / "missing.vcd"))
    assert res.tool_status == "skipped_no_vcd"

    # 2. Boundary validation
    fake_vcd = tmp_path / "test.vcd"
    fake_vcd.write_text("$timescale 1ns $end\n$enddefinitions $end\n")
    with pytest.raises(ValueError):
        query_vcd_window(str(fake_vcd), start_ps=-10)
    with pytest.raises(ValueError):
        query_vcd_window(str(fake_vcd), start_ps=5000, end_ps=1000)

    # 3. Waveform window slicing
    mock_vcd = VCDData(
        source_file=str(fake_vcd),
        tool_status="ok",
        signals={
            "tb.dut.clk": VCDSignalWave(
                name="clk", hierarchy="tb.dut.clk",
                transitions=[
                    VCDTransition(time_ps=0, value="0"),
                    VCDTransition(time_ps=1000, value="1"),
                    VCDTransition(time_ps=2000, value="0"),
                    VCDTransition(time_ps=3000, value="1"),
                ]
            )
        }
    )

    with patch("verisight.parsers.vcd_parser.parse_vcd", return_value=mock_vcd):
        # Query window [1000, 2500]
        sliced = query_vcd_window(str(fake_vcd), signals=["clk"], start_ps=1000, end_ps=2500)
        assert sliced.tool_status == "ok"
        transitions = sliced.signals["tb.dut.clk"].transitions
        times = [t.time_ps for t in transitions]
        assert 1000 in times
        assert 2000 in times
        assert 3000 not in times


# ─── 6. Consensus Arbiter Tests ───────────────────────────────────────

def test_consensus_arbiter_logic():
    from verisight.orchestrator import consensus_arbiter
    from verisight.schemas.classification import Classification
    from verisight.schemas.rtl_analysis import RTLAnalysis, XTraceResult, XTracerTraceResult
    from verisight.schemas.knowledge_schema import UnifiedKnowledge

    knowledge = UnifiedKnowledge()

    # Case 1: Agent 2 claims TB Bug, but Agent 3 finds concrete X-trace RTL Bug
    initial_tb = Classification(classification="TB Bug", confidence=80, reason="TB Scoreboard mismatch")
    rtl_analysis = RTLAnalysis()
    rtl_analysis.xtrace.real_traces.append(XTracerTraceResult(
        query_signal="alu.result",
        query_time_ps=1000,
        root_cause_type="uninit_ff",
        summary="Uninitialized flip-flop",
    ))
    rtl_analysis.primary_root_cause = "Confirmed uninitialized flip-flop in alu.result"
    rtl_analysis.primary_category = "X Propagation"
    rtl_analysis.confidence = 90

    final_cls = consensus_arbiter(initial_tb, rtl_analysis, knowledge)
    assert final_cls.classification == "RTL Bug"
    assert final_cls.confidence >= 80

    # Case 2: Agent 2 claims RTL Bug, but Agent 3 finds NO RTL bugs (disagreement)
    initial_rtl = Classification(classification="RTL Bug", confidence=70, reason="Hypothesized RTL flaw")
    empty_rtl_analysis = RTLAnalysis()
    final_disagree = consensus_arbiter(initial_rtl, empty_rtl_analysis, knowledge)
    assert final_disagree.classification == "Unknown"
    assert "inconclusive" in final_disagree.reason.lower()


# ─── 7. Agent 5 Sandbox Hardening Tests ───────────────────────────────

def test_agent5_sandbox_security():
    from verisight.agents.agent5_fix_generator import FixGeneratorAgent
    from verisight.schemas.fix_schema import FixResult
    from verisight.schemas.classification import Classification
    from verisight.schemas.knowledge_schema import UnifiedKnowledge
    from verisight.config import get_config

    agent = FixGeneratorAgent()
    config = get_config()
    config.fix.allow_tb_fix = False

    # 1. TB Bug fix is declined by default
    tb_cls = Classification(classification="TB Bug", confidence=85, reason="Scoreboard driver bug")
    declined = agent.execute(UnifiedKnowledge(), tb_cls)
    assert declined.fix_available is False
    assert "allow-tb-fix" in declined.decline_reason

    # 2. Anti-tampering detects commented-out assertion
    tamper_patch_comment = """
--- alu.sv
+++ alu.sv
@@ -10,3 +10,3 @@
-    assert (req == ack);
+    // assert (req == ack);
"""
    ok, notes = agent._inspect_verification_checks(tamper_patch_comment, "")
    assert ok is False
    assert "Commented-out" in notes

    # 3. Anti-tampering detects removed $error
    tamper_patch_remove = """
--- alu.sv
+++ alu.sv
@@ -20,3 +20,1 @@
-    $error("Data mismatch!");
"""
    ok, notes = agent._inspect_verification_checks(tamper_patch_remove, "")
    assert ok is False
    assert "removed" in notes

    # 4. Anti-tampering detects weakened assertion
    tamper_patch_weaken = """
--- alu.sv
+++ alu.sv
@@ -30,3 +30,3 @@
-    assert (a == b);
+    assert (1);
"""
    ok, notes = agent._inspect_verification_checks(tamper_patch_weaken, "")
    assert ok is False
    assert "weakened" in notes
