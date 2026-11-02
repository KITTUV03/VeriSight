"""
Comprehensive unit tests for advanced integrated research engines:
1. pywellen (Rust waveform engine)
2. TraceWeave (Failure-to-waveform evidence correlation)
3. CirFix SBFL (Spectrum-based fault localization with Ochiai)
4. SymbiYosys / SBY (Formal verification config and runner)
5. AssertLLM / AutoSVA (Automated SVA property synthesis from specs)
6. hgdb (Reverse-debugger and backward cycle tracer)
7. Root-Cause-Bench (Hardware RCA evaluation suite)
"""

import pytest
from pathlib import Path

from verisight.parsers.vcd_parser import parse_vcd
from verisight.tools.traceweave import correlate_failure_evidence, TraceWeaveReport
from verisight.tools.fault_localization import localize_faults, compute_ochiai, compute_tarantula
from verisight.tools.formal_verifier import generate_sby_config, run_formal_check
from verisight.plan.assertion_generator import synthesize_sva_from_spec
from verisight.tools.reverse_debugger import trace_backward_from_failure
from verisight.benchmarks.root_cause_bench import (
    STANDARD_SCENARIOS, evaluate_diagnosis_accuracy, BenchmarkScenario
)
from verisight.schemas.log_schema import LogKnowledge, LogEntry
from verisight.schemas.rtl_schema import RTLKnowledge, RTLModule, AlwaysBlock


def test_pywellen_vcd_parsing():
    """Verify pywellen Rust backend parses VCD waveforms."""
    vcd_path = "projects/ahb/waves/dump.vcd"
    if not Path(vcd_path).exists():
        pytest.skip("AHB VCD not found")

    data = parse_vcd(vcd_path)
    assert data.tool_status == "ok"
    assert data.parser_backend in ("pywellen", "vcdvcd")
    assert len(data.signals) > 0


def test_traceweave_correlation():
    """Verify TraceWeave correlates simulation errors with waveform and RTL."""
    log_data = LogKnowledge(
        errors=[
            LogEntry(
                timestamp="55000",
                timestamp_ps=55000000,
                severity="ERROR",
                message="READ DATA MISMATCH | ADDR=0x00000008 Expected=0xdeadbeef Actual=0x0000beef",
            )
        ]
    )

    report = correlate_failure_evidence(log_data, None, None)
    assert isinstance(report, TraceWeaveReport)
    assert report.failures_analyzed == 1
    assert len(report.correlated_failures) == 1
    assert report.correlated_failures[0].timestamp_ps == 55000000


def test_fault_localization_sbfl():
    """Verify CirFix SBFL calculates Ochiai and Tarantula suspiciousness."""
    score_ochiai = compute_ochiai(failed_e=4, passed_e=1, total_failed=4)
    assert 0.0 < score_ochiai <= 1.0

    score_tarantula = compute_tarantula(failed_e=4, passed_e=0, total_failed=4, total_passed=4)
    assert score_tarantula == 1.0

    log_data = LogKnowledge(
        entries=[
            LogEntry(severity="INFO", message="READ DATA PASS | ADDR=0x00000000"),
            LogEntry(severity="ERROR", message="READ DATA MISMATCH | ADDR=0x00000008 Actual=0x0000beef"),
        ],
        errors=[LogEntry(severity="ERROR", message="MISMATCH on DATA0")],
    )
    rtl_data = RTLKnowledge(
        modules=[
            RTLModule(
                name="ahb_slave",
                always_blocks=[
                    AlwaysBlock(
                        block_type="always_ff",
                        line_number=80,
                        signals_written=["reg_data0"],
                    )
                ]
            )
        ]
    )

    sbfl_report = localize_faults(log_data, rtl_data)
    assert sbfl_report.tool_status == "ok"
    assert len(sbfl_report.ranked_suspects) >= 1
    assert sbfl_report.top_suspect is not None
    assert sbfl_report.top_suspect.signal_name == "reg_data0"


def test_formal_verifier_config_and_runner():
    """Verify SymbiYosys configuration generation and graceful execution."""
    cfg = generate_sby_config(
        top_module="ahb_slave",
        rtl_files=["projects/ahb/rtl/ahb_slave.sv"],
        depth=15,
    )
    assert "mode bmc" in cfg
    assert "prep -top ahb_slave" in cfg
    assert "depth 15" in cfg

    res = run_formal_check(
        rtl_files=["projects/ahb/rtl/ahb_slave.sv"],
        top_module="ahb_slave",
        properties=["assert property (@(posedge clk) req |-> ack);"],
    )
    assert res.tool_status in ("ok", "tool_missing", "counterexample_found")
    assert res.properties_checked == 1


def test_assertllm_sva_synthesis():
    """Verify AssertLLM / AutoSVA synthesizes SystemVerilog Assertions from markdown spec."""
    spec_text = """
    # AMBA APB Specification
    ## Signal Definitions
    `pclk`, `presetn`, `psel`, `penable`, `pwrite`, `paddr`, `pslverr`, `pready`
    ## Rules
    1. Read-Only STATUS Register Write Protection:
       Any write attempt to address 0x04 must assert pslverr.
    """
    suite = synthesize_sva_from_spec(spec_text, module_name="apb_slave")
    assert len(suite.assertions) >= 1
    assert "pslverr" in suite.assertions[0].sva_code
    assert "module apb_slave_sva_bind" in suite.bind_file_content


def test_hgdb_reverse_trace():
    """Verify reverse-debugger steps backward from failure timestamp."""
    vcd_path = "projects/ahb/waves/dump.vcd"
    if not Path(vcd_path).exists():
        pytest.skip("AHB VCD not found")

    vcd_data = parse_vcd(vcd_path)
    res = trace_backward_from_failure(
        vcd_data=vcd_data,
        target_signal="HREADYOUT",
        failure_time_ps=1000000,
        max_steps=5,
    )
    assert res.tool_status == "ok"
    assert len(res.backward_steps) > 0


def test_root_cause_bench_scenarios():
    """Verify RootCauseBench scenarios and diagnostic scoring."""
    assert len(STANDARD_SCENARIOS) >= 5
    scenario = STANDARD_SCENARIOS[0]  # APB RO protection
    assert evaluate_diagnosis_accuracy("Slave did not assert pslverr on RO write", scenario) is True
    assert evaluate_diagnosis_accuracy("Completely unrelated clock issue", scenario) is False
