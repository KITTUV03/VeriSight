"""
Comprehensive test suite for UPF (Unified Power Format) Power Intent Integration.
Covers Scenarios 3, 5, 6, power-aware analysis, hierarchy resolution, and API endpoints.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from verisight.parsers.upf_parser import parse_upf, validate_upf_against_rtl
from verisight.parsers.rtl_parser import parse_rtl
from verisight.analysis.power_analysis import analyze_power_intent
from verisight.schemas.upf_schema import UPFKnowledge
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.orchestrator import VeriSightPipeline
from verisight.config import VeriSightConfig, PipelineConfig, LLMConfig
from verisight.server.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
SOC_RTL_DIR = REPO_ROOT / "examples/multi_file_soc/rtl"
SOC_UPF_DIR = REPO_ROOT / "examples/multi_file_soc/power"


@pytest.fixture
def rtl_knowledge():
    """Load and parse the full Multi-File SoC RTL design."""
    rtl_files = [
        str(SOC_RTL_DIR / "i2c_pkg.sv"),
        str(SOC_RTL_DIR / "i2c_interface.sv"),
        str(SOC_RTL_DIR / "i2c_fsm.sv"),
        str(SOC_RTL_DIR / "i2c_controller.sv"),
        str(SOC_RTL_DIR / "apb_slave.sv"),
        str(SOC_RTL_DIR / "apb_master.sv"),
        str(SOC_RTL_DIR / "top.sv"),
    ]
    return parse_rtl(rtl_files)


def test_upf_parsing_and_extraction(rtl_knowledge):
    """Verify parsing and extraction of UPF power-intent constructs."""
    upf_file = SOC_UPF_DIR / "soc.upf"
    assert upf_file.exists(), f"Missing UPF file: {upf_file}"

    upf = parse_upf(upf_file, rtl_knowledge=rtl_knowledge)
    assert isinstance(upf, UPFKnowledge)
    assert upf.is_valid

    # 1. Power Domains
    domain_names = {pd.name for pd in upf.power_domains}
    assert "TOP" in domain_names
    assert "PD_CORE" in domain_names
    assert "PD_PERIPH" in domain_names

    # 2. Supply Ports & Nets
    port_names = {sp.name for sp in upf.supply_ports}
    assert {"VDD", "VDD_LOW", "VSS"}.issubset(port_names)

    net_names = {sn.name for sn in upf.supply_nets}
    assert {"VDD", "VDD_SW", "VDD_LOW", "VSS"}.issubset(net_names)

    # 3. Power Switches
    assert len(upf.power_switches) == 1
    sw = upf.power_switches[0]
    assert sw.name == "sw_core"
    assert sw.domain == "PD_CORE"
    assert "VDD_SW" in sw.output_supply_port
    assert "pwr_gate_en" in sw.control_port

    # 4. Isolation Strategy
    assert len(upf.isolation_strategies) == 1
    iso = upf.isolation_strategies[0]
    assert iso.name == "iso_core"
    assert iso.domain == "PD_CORE"
    assert iso.applies_to == "outputs"
    assert iso.clamp_value == "0"
    assert iso.isolation_signal == "pwr_iso_en"

    # 5. Level Shifter Strategy
    assert len(upf.level_shifters) == 1
    ls = upf.level_shifters[0]
    assert ls.name == "ls_periph"
    assert ls.domain == "PD_PERIPH"

    # 6. Retention Strategy
    assert len(upf.retention_strategies) == 1
    ret = upf.retention_strategies[0]
    assert ret.name == "ret_slave"
    assert ret.domain == "PD_CORE"
    assert ret.retention_power_net == "VDD"

    # 7. Power State Table (PST)
    assert len(upf.power_state_tables) == 1
    pst = upf.power_state_tables[0]
    assert pst.name == "pst_soc"
    assert "ALL_ON" in pst.states
    assert "SLEEP" in pst.states


def test_upf_hierarchy_resolution(rtl_knowledge):
    """Verify UPF scope and elements are correctly bound to RTL instances."""
    upf_file = SOC_UPF_DIR / "soc.upf"
    upf = parse_upf(upf_file, rtl_knowledge=rtl_knowledge)

    # Resolved hierarchy maps instance names to power domains
    assert upf.resolved_hierarchy.get("u_apb_slave") == "PD_CORE"
    assert upf.resolved_hierarchy.get("u_i2c") == "PD_PERIPH"
    assert upf.resolved_hierarchy.get("top") == "TOP"


def test_scenario_3_multi_file_rtl_with_upf_pipeline(rtl_knowledge, tmp_path):
    """
    Scenario 3: Multi-file RTL + UPF full pipeline execution.
    Verifies that power intent is made available to agents and reports.
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
    upf_file = str(SOC_UPF_DIR / "soc.upf")

    out_dir = tmp_path / "upf_pipeline_out"
    config = VeriSightConfig(
        pipeline=PipelineConfig(output_dir=str(out_dir), save_intermediates=True, enable_rag=False),
        llm=LLMConfig(airgap=True),
    )
    pipeline = VeriSightPipeline(config=config)
    report = pipeline.run(rtl_path=rtl_files, upf_path=upf_file)

    assert report is not None
    assert (out_dir / "upf.json").exists()
    assert (out_dir / "knowledge.json").exists()

    # Verify agent 1 extracted UPF knowledge
    assert pipeline.knowledge.upf is not None
    assert len(pipeline.knowledge.upf.power_domains) == 3

    # Verify agent 3 executed power intent analysis
    assert pipeline.rtl_analysis is not None
    assert pipeline.rtl_analysis.power is not None
    assert len(pipeline.rtl_analysis.power.domains_analyzed) == 3


def test_scenario_5_upf_validation_and_diagnostics(rtl_knowledge):
    """
    Scenario 5: Inconsistent and invalid UPF file.
    Verifies meaningful diagnostics for hierarchy mismatches, undeclared signals,
    and power sequencing / retention hazards.
    """
    bad_upf_file = SOC_UPF_DIR / "inconsistent.upf"
    upf = parse_upf(bad_upf_file, rtl_knowledge=rtl_knowledge)

    # 1. Element not in RTL
    elem_diags = [d for d in upf.diagnostics if d.code == "UPF_ELEMENT_NOT_IN_RTL"]
    assert len(elem_diags) > 0
    assert "u_nonexistent_subsystem" in elem_diags[0].message

    # 2. Undeclared domain
    dom_diags = [d for d in upf.diagnostics if d.code == "UPF_UNRESOLVED_DOMAIN"]
    assert len(dom_diags) > 0
    assert "PD_UNDECLARED" in dom_diags[0].message

    # 3. Undeclared isolation signal
    sig_diags = [d for d in upf.diagnostics if d.code == "UPF_ISO_SIGNAL_UNRESOLVED"]
    assert len(sig_diags) > 0
    assert "nonexistent_iso_signal" in sig_diags[0].message

    # 4. Power Analysis Check (Retention and PST hazards)
    knowledge = UnifiedKnowledge(rtl=rtl_knowledge, upf=upf)
    power_res = analyze_power_intent(knowledge)
    assert power_res is not None

    # Check retention connected to switched net
    ret_issues = [iss for iss in power_res.retention_issues if iss.severity == "critical"]
    assert len(ret_issues) > 0
    assert "VDD_SW_FAULTY" in ret_issues[0].description

    # Check illegal power state in PST
    seq_issues = [iss for iss in power_res.sequencing_issues if iss.severity == "critical"]
    assert len(seq_issues) > 0
    assert "Illegal Power State" in seq_issues[0].description


def test_scenario_6_backward_compatibility_rtl_only(tmp_path):
    """Scenario 6: Verify existing RTL-only projects continue working without UPF."""
    single_file = str(SOC_RTL_DIR / "apb_slave.sv")
    out_dir = tmp_path / "bw_compat_out"

    config = VeriSightConfig(
        pipeline=PipelineConfig(output_dir=str(out_dir), save_intermediates=True, enable_rag=False),
        llm=LLMConfig(airgap=True),
    )
    pipeline = VeriSightPipeline(config=config)
    report = pipeline.run(rtl_path=single_file)

    assert report is not None
    assert pipeline.knowledge.upf is None
    assert pipeline.rtl_analysis.power is None
    assert not (out_dir / "upf.json").exists()


def test_server_project_upload_api():
    """Verify /api/project/upload FastAPI endpoint with multi-file RTL and UPF."""
    app = create_app()
    client = TestClient(app)

    # 1. Multi-file RTL + UPF upload
    payload = {
        "rtl_files": [
            {"name": "i2c_pkg.sv", "content": (SOC_RTL_DIR / "i2c_pkg.sv").read_text(encoding="utf-8")},
            {"name": "i2c_fsm.sv", "content": (SOC_RTL_DIR / "i2c_fsm.sv").read_text(encoding="utf-8")},
            {"name": "top.sv", "content": (SOC_RTL_DIR / "top.sv").read_text(encoding="utf-8")},
        ],
        "upf_file": {
            "name": "soc.upf",
            "content": (SOC_UPF_DIR / "soc.upf").read_text(encoding="utf-8"),
        },
        "top_module": "top",
    }

    response = client.post("/api/project/upload", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mode"] == "power_aware"
    assert data["file_count"] == 3
    assert data["top_module"] == "top"
    assert data["upf_info"] is not None
    assert len(data["upf_info"]["domains"]) == 3

    # 2. RTL-only upload without UPF
    rtl_only_payload = {
        "rtl_files": [
            {"name": "apb_slave.sv", "content": (SOC_RTL_DIR / "apb_slave.sv").read_text(encoding="utf-8")},
        ],
        "upf_file": None,
    }
    response_rtl = client.post("/api/project/upload", json=rtl_only_payload)
    assert response_rtl.status_code == 200
    data_rtl = response_rtl.json()
    assert data_rtl["success"] is True
    assert data_rtl["mode"] == "rtl_only"
    assert data_rtl["upf_info"] is None
