"""
Unit tests for verisight.tools — yosys and x-tracer integration.

yosys is expected to be installed in the test environment (it's a common
system package); x-tracer is not, so those tests rely on monkeypatching.
"""

import pytest
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
ALU_RTL = str(EXAMPLES_DIR / "rtl" / "alu.sv")


class TestYosysRunner:
    """Tests for verisight.tools.yosys_runner."""

    def test_synthesize_netlist_produces_gate_level_verilog(self, tmp_path):
        from verisight.tools.yosys_runner import synthesize_netlist

        output_path = tmp_path / "netlist.v"
        result = synthesize_netlist([ALU_RTL], "alu", output_path)

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text()
        assert "module" in content

    def test_synthesize_netlist_raises_on_missing_rtl_files(self, tmp_path):
        from verisight.tools.yosys_runner import synthesize_netlist

        with pytest.raises(RuntimeError):
            synthesize_netlist([], "alu", tmp_path / "netlist.v")

    def test_synthesize_netlist_raises_on_bad_top_module(self, tmp_path):
        from verisight.tools.yosys_runner import synthesize_netlist

        with pytest.raises(RuntimeError):
            synthesize_netlist([ALU_RTL], "does_not_exist_module", tmp_path / "netlist.v")


class TestFindXTracer:
    """Tests for verisight.tools.xtracer_runner.find_xtracer."""

    def test_find_xtracer_raises_when_not_found(self, monkeypatch, tmp_path):
        from verisight.tools.xtracer_runner import find_xtracer, XTracerNotFoundError

        monkeypatch.delenv("VERISIGHT_XTRACER_PATH", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: None)

        with pytest.raises(XTracerNotFoundError):
            find_xtracer(explicit_path=str(tmp_path / "nonexistent" / "x_tracer.py"))

    def test_find_xtracer_resolves_explicit_path(self, tmp_path):
        from verisight.tools.xtracer_runner import find_xtracer

        fake_script = tmp_path / "x_tracer.py"
        fake_script.write_text("# stub")

        assert find_xtracer(explicit_path=str(fake_script)) == fake_script

    def test_find_xtracer_resolves_env_var(self, monkeypatch, tmp_path):
        from verisight.tools.xtracer_runner import find_xtracer

        fake_script = tmp_path / "x_tracer.py"
        fake_script.write_text("# stub")
        monkeypatch.setenv("VERISIGHT_XTRACER_PATH", str(fake_script))

        assert find_xtracer() == fake_script


class TestDeriveQueries:
    """Tests for verisight.tools.xtracer_runner.derive_queries."""

    def _build_knowledge(self, actual="xx", timestamp="20 ns", field_name="result"):
        from verisight.schemas.knowledge_schema import UnifiedKnowledge
        from verisight.schemas.rtl_schema import RTLKnowledge
        from verisight.schemas.tb_schema import TBKnowledge
        from verisight.schemas.spec_schema import SpecKnowledge
        from verisight.schemas.log_schema import LogKnowledge, ScoreboardMismatch

        log = LogKnowledge(
            scoreboard_mismatches=[
                ScoreboardMismatch(
                    timestamp=timestamp,
                    expected="e1",
                    actual=actual,
                    field=field_name,
                    component="uvm_test_top.env.scb",
                    message=f"MISMATCH: {field_name}={actual}",
                )
            ]
        )
        return UnifiedKnowledge(
            spec=SpecKnowledge(),
            rtl=RTLKnowledge(top_module="alu"),
            tb=TBKnowledge(),
            logs=log,
        )

    def test_derive_queries_converts_ns_to_ps(self):
        from verisight.tools.xtracer_runner import derive_queries

        knowledge = self._build_knowledge(actual="xx", timestamp="20 ns")
        queries = derive_queries(knowledge, "alu")

        assert len(queries) == 1
        assert queries[0].field_name == "result"
        assert queries[0].time_ps == 20000
        assert "result" in queries[0].signal_candidates
        assert "alu.result" in queries[0].signal_candidates

    def test_derive_queries_skips_non_x_mismatches(self):
        from verisight.tools.xtracer_runner import derive_queries

        knowledge = self._build_knowledge(actual="5f", timestamp="40 ns")
        queries = derive_queries(knowledge, "alu")

        assert queries == []


class TestRunXTracerWithCandidates:
    """Tests for verisight.tools.xtracer_runner.run_xtracer_with_candidates fallback."""

    def test_falls_back_to_second_candidate(self, monkeypatch, tmp_path):
        import verisight.tools.xtracer_runner as xtracer_runner

        calls = []

        def fake_run_xtracer(xtracer_path, netlists, vcd, signal, time_ps, max_depth=100):
            calls.append(signal)
            if signal == "bad.result":
                raise RuntimeError("signal not found")
            return {"signal": signal, "root_cause_type": "uninit_ff", "summary": "ok"}

        monkeypatch.setattr(xtracer_runner, "run_xtracer", fake_run_xtracer)

        result = xtracer_runner.run_xtracer_with_candidates(
            tmp_path / "x_tracer.py",
            [tmp_path / "netlist.v"],
            tmp_path / "sim.vcd",
            ["bad.result", "alu.result"],
            20000,
        )

        assert calls == ["bad.result", "alu.result"]
        assert result["signal"] == "alu.result"
        assert result["root_cause_type"] == "uninit_ff"

    def test_raises_when_all_candidates_fail(self, monkeypatch, tmp_path):
        import verisight.tools.xtracer_runner as xtracer_runner

        def always_fails(xtracer_path, netlists, vcd, signal, time_ps, max_depth=100):
            raise RuntimeError(f"signal not found: {signal}")

        monkeypatch.setattr(xtracer_runner, "run_xtracer", always_fails)

        with pytest.raises(RuntimeError):
            xtracer_runner.run_xtracer_with_candidates(
                tmp_path / "x_tracer.py",
                [tmp_path / "netlist.v"],
                tmp_path / "sim.vcd",
                ["bad.result", "also_bad.result"],
                20000,
            )
