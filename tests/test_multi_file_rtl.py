"""
Comprehensive test suite for Multi-File RTL Input and Cross-File Dependency Resolution.
Covers Scenarios 1, 2, 4, 6 and edge-case validations.
"""

import pytest
from pathlib import Path

from verisight.parsers.rtl_parser import (
    parse_rtl,
    resolve_rtl_files,
    order_rtl_sources,
    check_missing_dependencies,
)
from verisight.schemas.rtl_schema import RTLKnowledge
from verisight.orchestrator import VeriSightPipeline
from verisight.config import VeriSightConfig, PipelineConfig, LLMConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
SOC_RTL_DIR = REPO_ROOT / "examples/multi_file_soc/rtl"


def test_scenario_1_single_rtl_file():
    """Scenario 1: Single RTL file ingestion and parsing."""
    single_file = SOC_RTL_DIR / "apb_slave.sv"
    assert single_file.exists(), f"Missing test file: {single_file}"

    knowledge = parse_rtl(str(single_file))
    assert isinstance(knowledge, RTLKnowledge)
    assert len(knowledge.modules) == 1
    assert knowledge.modules[0].name == "apb_slave"
    assert knowledge.top_module == "apb_slave"
    assert len(knowledge.file_list) == 1
    assert str(single_file.resolve()) == str(Path(knowledge.file_list[0]).resolve())


def test_scenario_2_multi_file_rtl_resolution():
    """
    Scenario 2: Upload 7 individual RTL files.
    Verify all files are maintained separately (no blind concatenation),
    cross-file package, interface, and module dependencies are resolved,
    and top module is accurately detected.
    """
    rtl_files = [
        str(SOC_RTL_DIR / "i2c_pkg.sv"),
        str(SOC_RTL_DIR / "i2c_interface.sv"),
        str(SOC_RTL_DIR / "i2c_fsm.sv"),
        str(SOC_RTL_DIR / "i2c_controller.sv"),
        str(SOC_RTL_DIR / "apb_slave.sv"),
        str(SOC_RTL_DIR / "apb_master.sv"),
        str(SOC_RTL_DIR / "top.sv"),
    ]
    for f in rtl_files:
        assert Path(f).exists(), f"File does not exist: {f}"

    knowledge = parse_rtl(rtl_files)

    # 1. Verify all 7 files were preserved individually
    assert len(knowledge.file_list) == 7
    # 2. Verify all modules were parsed across distinct files
    module_names = {m.name for m in knowledge.modules}
    assert "top" in module_names
    assert "apb_master" in module_names
    assert "apb_slave" in module_names
    assert "i2c_controller" in module_names
    assert "i2c_fsm" in module_names

    # 3. Verify packages and interfaces were extracted
    assert "i2c_pkg" in knowledge.packages
    assert "i2c_interface" in knowledge.interfaces

    # 4. Verify top-level module correctly identified as 'top'
    assert knowledge.top_module == "top"
    assert "top" in knowledge.top_candidates

    # 5. Verify no missing dependencies among these valid files
    assert len(knowledge.missing_dependencies) == 0


def test_multi_file_dependency_ordering():
    """Verify order_rtl_sources places packages/headers before consumer modules."""
    files = [
        SOC_RTL_DIR / "top.sv",
        SOC_RTL_DIR / "i2c_fsm.sv",
        SOC_RTL_DIR / "i2c_pkg.sv",
        SOC_RTL_DIR / "i2c_interface.sv",
    ]
    ordered_files, def_pkgs, def_ifaces, auto_incdirs = order_rtl_sources(files)

    ordered_names = [f.name for f in ordered_files]
    # i2c_pkg must precede i2c_fsm because i2c_fsm imports i2c_pkg
    assert ordered_names.index("i2c_pkg.sv") < ordered_names.index("i2c_fsm.sv")
    # submodules must precede top.sv
    assert ordered_names.index("i2c_fsm.sv") < ordered_names.index("top.sv")
    assert "i2c_pkg" in def_pkgs
    assert "i2c_interface" in def_ifaces


def test_missing_dependency_diagnostic(tmp_path):
    """Scenario 5/Edge: Identify missing module dependencies when instantiating undefined module."""
    incomplete_file = tmp_path / "orphan_instantiator.sv"
    incomplete_file.write_text("""
    module orphan_instantiator (
        input logic clk,
        input logic rst_n
    );
        missing_crypto_engine u_crypto (.clk(clk), .rst_n(rst_n));
    endmodule
    """)

    knowledge = parse_rtl(str(incomplete_file))
    assert "missing_crypto_engine" in knowledge.missing_dependencies

    # Verify diagnostic code and severity
    dep_diags = [d for d in knowledge.parser_status.diagnostics if d.category == "missing_dependency"]
    assert len(dep_diags) > 0
    assert "missing_crypto_engine" in dep_diags[0].message
    assert dep_diags[0].severity == "error"


def test_multi_file_explicit_top_override():
    """Verify user can explicitly select top-level module."""
    rtl_files = [
        str(SOC_RTL_DIR / "apb_slave.sv"),
        str(SOC_RTL_DIR / "apb_master.sv"),
        str(SOC_RTL_DIR / "top.sv"),
    ]
    # Explicitly pick apb_slave as top
    knowledge = parse_rtl(rtl_files, top_module="apb_slave")
    assert knowledge.top_module == "apb_slave"


def test_empty_and_unsupported_files(tmp_path):
    """Verify handling of empty files and unsupported extensions."""
    empty_f = tmp_path / "empty.sv"
    empty_f.write_text("")

    bad_ext = tmp_path / "notes.txt"
    bad_ext.write_text("just some text")

    files = resolve_rtl_files([empty_f, bad_ext])
    assert empty_f in files
    assert bad_ext not in files  # .txt should be filtered from RTL files


def test_scenario_4_rtl_only_pipeline(tmp_path):
    """
    Scenario 4: Multi-file RTL project run through pipeline without UPF.
    All existing analysis features work seamlessly.
    """
    rtl_files = [
        str(SOC_RTL_DIR / "i2c_pkg.sv"),
        str(SOC_RTL_DIR / "i2c_fsm.sv"),
        str(SOC_RTL_DIR / "i2c_controller.sv"),
        str(SOC_RTL_DIR / "apb_slave.sv"),
        str(SOC_RTL_DIR / "apb_master.sv"),
        str(SOC_RTL_DIR / "top.sv"),
    ]

    out_dir = tmp_path / "multi_rtl_out"
    config = VeriSightConfig(
        pipeline=PipelineConfig(output_dir=str(out_dir), save_intermediates=True, enable_rag=False),
        llm=LLMConfig(airgap=True),
    )
    pipeline = VeriSightPipeline(config=config)
    report = pipeline.run(rtl_path=rtl_files)

    assert report is not None
    assert (out_dir / "rtl.json").exists()
    assert (out_dir / "knowledge.json").exists()
    # No UPF file was supplied, so upf.json should not exist
    assert not (out_dir / "upf.json").exists()
    assert report.classification == "RTL Bug"
    assert "apb_slave" in report.rtl_file or "top" in report.rtl_file or report.module in ("top", "apb_slave", "apb_master", "i2c_controller", "X Propagation")
