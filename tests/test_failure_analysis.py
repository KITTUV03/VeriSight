"""
Tests for the deterministic failure-analysis engine and its integration into
the log parser: compile/elaboration detection, false-PASS closure, unit-aware
time, and earliest-causal primary-event selection.
"""

import os
from pathlib import Path

import pytest

from verisight.analysis import failure_analysis as fa
from verisight.parsers.log_parser import parse_log

REPO = Path(__file__).resolve().parent.parent


# ── unit-aware time ─────────────────────────────────────────────────────────

def test_parse_time_units():
    assert fa.parse_time_to_ns("650000 ns") == 650000.0
    assert fa.parse_time_to_ns("100 ps") == pytest.approx(0.1)
    assert fa.parse_time_to_ns("2 us") == pytest.approx(2000.0)
    assert fa.parse_time_to_ns("") is None
    assert fa.parse_time_to_ns("no-number") is None


def test_ps_sorts_before_ns():
    # Regression for the hardcoded ' ns' bug: 500 ps must be < 1 ns.
    assert fa.parse_time_to_ns("500 ps") < fa.parse_time_to_ns("1 ns")


# ── tool/compile/elaboration detection ──────────────────────────────────────

def test_detect_verilator_compile_error():
    lines = [
        "%Error: rtl/alu.sv:48: syntax error, unexpected ';'",
        "%Error: Exiting due to 2 error(s)",
    ]
    errs = fa.detect_tool_errors(lines)
    assert errs, "expected a compile error to be detected"
    assert errs[0]["stage"] == "compile"
    assert errs[0]["tool"] == "verilator"


def test_uvm_error_line_not_treated_as_compile_error():
    # A runtime UVM_ERROR containing the word 'Error' must NOT be a tool error.
    lines = ["UVM_ERROR apb_scoreboard.sv(55) @ 830000 ns: PROTOCOL MISMATCH ..."]
    assert fa.detect_tool_errors(lines) == []


def test_build_failure_marker():
    assert fa.has_build_failure_marker("make[1]: *** [Vtop] Error 1")
    assert fa.has_build_failure_marker("Exiting due to 2 error(s)")
    assert not fa.has_build_failure_marker("all good here")


# ── parser integration ──────────────────────────────────────────────────────

def test_compile_error_log_is_fail_not_pass():
    """The core false-PASS regression: a compile-only log must be FAIL."""
    log = parse_log(str(REPO / "eval/synthetic/compile_error/sim.log"))
    assert log.summary.pass_fail == "FAIL"
    assert log.summary.failure_stage == "compile"
    assert len(log.tool_errors) >= 1
    assert log.primary_event is not None
    assert log.primary_event.kind == "compile_error"


def test_runtime_log_primary_event_is_earliest():
    """APB primary event must be the earliest-in-time failure (the data mismatch)."""
    log = parse_log(str(REPO / "projects/apb/logs/sim.log"))
    assert log.summary.failure_stage == "runtime"
    assert log.primary_event is not None
    # Earliest APB error is the 0xdeadbeef read-data mismatch at 650000 ns.
    assert "deadbeef" in log.primary_event.message.lower() or \
           fa.parse_time_to_ns(log.primary_event.timestamp) == 650000.0


def test_alu_primary_event_present():
    log = parse_log(str(REPO / "examples/logs/sim.log"))
    assert log.summary.pass_fail == "FAIL"
    assert log.primary_event is not None
    # The earliest failure is at 20 ns.
    assert fa.parse_time_to_ns(log.primary_event.timestamp) == 20.0


def test_message_id_captured():
    log = parse_log(str(REPO / "examples/logs/sim.log"))
    ids = {e.message_id for e in log.errors}
    assert "SCB" in ids  # the [SCB] tag is now preserved
