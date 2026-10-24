"""
Regression & integration tests for the pyslang-backed SystemVerilog frontend.

Covers the capabilities required by the PyVerilog→pyslang migration:
  * Valid SystemVerilog RTL (ports/types, always blocks, FSM, locations)
  * Valid UVM classes / testbench
  * SVA properties and temporal operators (|-> / |=>)
  * Interfaces and modports
  * Multi-file packages and `include dependencies
  * Deliberately malformed syntax  → genuine syntax diagnostics
  * Missing-package / unresolved symbols → missing_dependency (NOT syntax)
  * Degraded/partial analysis flagging
  * X-Tracer integration (uninitialized-register detection)
  * Pre-commit validator exit semantics
  * Legacy Verilog regression

Each test checks an expected RESULT (names, categories, counts, locations),
not merely that an object was returned. If pyslang is unavailable the frontend
tests are skipped (the regex fallback is covered by test_parsers.py).
"""

import os
from pathlib import Path

import pytest

from verisight.parsers import sv_frontend
from verisight.schemas.parser_schema import (
    CATEGORY_SYNTAX, CATEGORY_MISSING_DEPENDENCY,
)

FIX = Path(__file__).parent / "fixtures" / "sv"
EXAMPLES = Path(__file__).parent.parent / "examples"

pytestmark = pytest.mark.skipif(
    not sv_frontend.is_available(),
    reason="pyslang frontend not available",
)


# ─── Frontend: diagnostics & categorization ─────────────────────────────
class TestFrontendDiagnostics:
    def test_clean_rtl_has_no_diagnostics(self):
        r = sv_frontend.compile_files([str(EXAMPLES / "rtl" / "alu.sv")])
        assert r.status.backend == "pyslang"
        assert r.syntax_ok is True
        assert r.degraded is False
        assert len([d for d in r.diagnostics if d.is_error()]) == 0
        assert [i.name for i in r.top_instances()] == ["alu"]

    def test_malformed_syntax_reports_syntax_errors(self):
        r = sv_frontend.compile_files([str(FIX / "bad_syntax.sv")])
        syntax_errs = [d for d in r.diagnostics if d.category == CATEGORY_SYNTAX and d.is_error()]
        assert len(syntax_errs) >= 1
        assert r.syntax_ok is False
        # locations must be real (1-based line/col)
        d = syntax_errs[0]
        assert d.line >= 1 and d.column >= 1
        assert d.file.endswith("bad_syntax.sv")

    def test_missing_package_is_missing_dependency_not_syntax(self):
        r = sv_frontend.compile_files([str(FIX / "missing_pkg.sv")])
        missing = [d for d in r.diagnostics if d.category == CATEGORY_MISSING_DEPENDENCY]
        syntax_errs = [d for d in r.diagnostics if d.category == CATEGORY_SYNTAX and d.is_error()]
        assert len(missing) >= 1, "unknown package must be a missing dependency"
        assert len(syntax_errs) == 0, "missing package must NOT be a syntax error"
        assert r.syntax_ok is True
        assert r.degraded is True  # unresolved dependency ⇒ partial analysis

    def test_unavailable_frontend_is_explicit(self):
        # compile_text on an empty-ish snippet still returns a structured result
        r = sv_frontend.compile_text("module m; endmodule")
        assert r.status.backend in ("pyslang", "none")


# ─── RTL builder: structure extraction ──────────────────────────────────
class TestRTLBuild:
    def _build(self, *files):
        from verisight.parsers.pyslang_rtl import build_rtl_knowledge
        fs = [str(f) for f in files]
        r = sv_frontend.compile_files(fs)
        return build_rtl_knowledge(r, fs)

    def test_alu_ports_types_and_widths(self):
        k = self._build(EXAMPLES / "rtl" / "alu.sv")
        alu = k.modules[0]
        names = {p.name: p for p in alu.ports}
        assert {"clk", "rst_n", "operand_a", "result"} <= set(names)
        # 8-bit vectors reported with a real width, scalars as 1
        assert names["operand_a"].width in ("[7:0]", "8")
        assert names["clk"].width == "1"

    def test_alu_always_blocks_classified(self):
        k = self._build(EXAMPLES / "rtl" / "alu.sv")
        alu = k.modules[0]
        types = {b.block_type for b in alu.always_blocks}
        assert "combinational" in types
        assert "sequential" in types
        seq = [b for b in alu.always_blocks if b.block_type == "sequential"][0]
        assert seq.clock_signal == "clk"
        assert "rst" in seq.reset_signal.lower()
        # real read/write sets from the AST
        assert "result" in seq.signals_written

    def test_packed_struct_and_enum_widths(self):
        k = self._build(FIX / "types_pkg.sv")
        dut = [m for m in k.modules if m.name == "typed_dut"][0]
        ports = {p.name: p for p in dut.ports}
        # packed struct {8+8+1} = 17 bits
        assert ports["in_bus"].width == "[16:0]"
        # enum state is 2 bits
        assert ports["state"].width == "[1:0]"

    def test_fsm_detected(self):
        k = self._build(FIX / "types_pkg.sv")
        dut = [m for m in k.modules if m.name == "typed_dut"][0]
        assert len(dut.fsms) >= 1

    def test_sva_assertions_extracted(self):
        k = self._build(FIX / "sva_props.sv")
        m = k.modules[0]
        kinds = {a.assertion_type for a in m.assertions}
        assert "assert" in kinds
        assert "cover" in kinds
        # source locations preserved
        assert all(a.line_number > 0 for a in m.assertions)

    def test_multi_module_hierarchy(self):
        proj = EXAMPLES.parent / "projects" / "fifo" / "rtl"
        files = [str(f) for f in proj.glob("*.sv")]
        if not files:
            pytest.skip("fifo project not present")
        from verisight.parsers.pyslang_rtl import build_rtl_knowledge
        r = sv_frontend.compile_files(files)
        k = build_rtl_knowledge(r, files)
        names = {m.name for m in k.modules}
        assert "syn_fifo" in names
        # child instance discovered via hierarchy walk
        assert any(m.instantiations for m in k.modules)

    def test_legacy_verilog_still_parses(self):
        k = self._build(FIX / "legacy_counter.v")
        assert len(k.modules) == 1
        m = k.modules[0]
        assert m.name == "legacy_counter"
        assert len(m.ports) == 4
        assert any(b.block_type == "sequential" for b in m.always_blocks)


# ─── Parser wrappers: backend + degraded flags ──────────────────────────
class TestParserWrappers:
    def test_parse_rtl_uses_pyslang(self):
        from verisight.parsers.rtl_parser import parse_rtl
        k = parse_rtl(str(EXAMPLES / "rtl" / "alu.sv"))
        assert k.parser_status.backend == "pyslang"
        assert k.parser_status.degraded is False
        assert k.top_module == "alu"

    def test_parse_uvm_uses_pyslang_and_flags_degraded(self):
        from verisight.parsers.uvm_parser import parse_uvm
        tb = parse_uvm(str(EXAMPLES / "tb"))
        assert tb.parser_status.backend == "pyslang"
        # UVM without uvm_pkg ⇒ unresolved deps ⇒ degraded, but still extracts
        assert tb.parser_status.degraded is True
        assert any(d.name == "alu_driver" for d in tb.drivers)
        assert any(m.name == "alu_monitor" for m in tb.monitors)
        assert any(s.name == "alu_scoreboard" for s in tb.scoreboards)
        assert any(t.name == "alu_seq_item" for t in tb.transactions)
        assert "alu_if" in [i.name for i in tb.interfaces]
        assert "alu_pkg" in tb.packages

    def test_uvm_no_duplicate_classes(self):
        from verisight.parsers.uvm_parser import parse_uvm
        tb = parse_uvm(str(EXAMPLES / "tb"))
        # alu_driver is defined once and `included by the package — must not double
        assert [d.name for d in tb.drivers].count("alu_driver") == 1


# ─── Interfaces ─────────────────────────────────────────────────────────
class TestInterfaces:
    def test_interface_modports_parsed(self):
        from verisight.parsers.uvm_parser import parse_uvm
        tb = parse_uvm(str(FIX / "bus_if.sv"))
        ifaces = {i.name: i for i in tb.interfaces}
        assert "bus_if" in ifaces
        bus = ifaces["bus_if"]
        assert "master" in bus.modports and "slave" in bus.modports
        assert "cb" in bus.clocking_blocks


# ─── X-Tracer integration ───────────────────────────────────────────────
class TestXTracerIntegration:
    def test_alu_uninitialized_register_detected(self):
        from verisight.parsers.rtl_parser import parse_rtl
        from verisight.schemas.knowledge_schema import UnifiedKnowledge
        from verisight.agents.agent3_rtl_analyzer import RTLRootCauseAnalyzer

        k = UnifiedKnowledge()
        k.rtl = parse_rtl(str(EXAMPLES / "rtl" / "alu.sv"))
        xr = RTLRootCauseAnalyzer(output_dir="/tmp/vs_xtrace")._analyze_x_propagation(k)
        # ground truth: 'result' is written but never reset → X origin
        assert "alu.result" in xr.uninitialized_registers
        assert any(o.origin_signal == "result" for o in xr.x_origins)
        # the reset-covered regs must NOT be flagged
        assert "alu.carry" not in xr.uninitialized_registers
        # parser provenance + static-analysis limitation surfaced
        assert xr.parser_backend == "pyslang"
        assert any("simulation" in l.lower() for l in xr.limitations)


# ─── Pre-commit validator ───────────────────────────────────────────────
class TestPreCommitValidator:
    def test_clean_file_passes(self):
        from verisight.tools.sv_validate import validate, EXIT_OK
        assert validate([str(EXAMPLES / "rtl" / "alu.sv")]) == EXIT_OK

    def test_legacy_verilog_passes(self):
        from verisight.tools.sv_validate import validate, EXIT_OK
        assert validate([str(FIX / "legacy_counter.v")]) == EXIT_OK

    def test_malformed_fails_nonzero(self):
        from verisight.tools.sv_validate import validate, EXIT_SYNTAX_FAIL
        assert validate([str(FIX / "bad_syntax.sv")]) == EXIT_SYNTAX_FAIL

    def test_missing_dep_not_a_syntax_failure(self):
        from verisight.tools.sv_validate import validate, EXIT_OK
        # syntax-only mode: unresolved package is not a hard failure
        assert validate([str(FIX / "missing_pkg.sv")]) == EXIT_OK

    def test_uvm_standalone_unverified_not_failed(self):
        from verisight.tools.sv_validate import validate, EXIT_OK
        # spurious syntax from unexpanded macros ⇒ UNVERIFIED, not a fail
        assert validate([str(EXAMPLES / "tb" / "alu_driver.sv")]) == EXIT_OK

    def test_strict_mode_fails_on_missing_dep(self):
        from verisight.tools.sv_validate import validate, EXIT_SYNTAX_FAIL
        assert validate([str(FIX / "missing_pkg.sv")], strict=True) == EXIT_SYNTAX_FAIL


# ─── Fix-generator syntax pre-check (pyslang-backed) ────────────────────
class TestFixSyntaxCheck:
    def _agent(self):
        from verisight.agents.agent5_fix_generator import FixGeneratorAgent
        return FixGeneratorAgent()

    def test_valid_fix_snippet_passes(self):
        ok, _ = self._agent()._validate_syntax(
            "always_ff @(posedge clk) begin\n    result <= 0;\nend\n"
        )
        assert ok is True

    def test_broken_fix_snippet_fails(self):
        ok, notes = self._agent()._validate_syntax("assign out = (a + b;")
        assert ok is False
