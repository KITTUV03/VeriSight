"""
Tests for EDA Playground Exporter tool and endpoints.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from verisight.tools.eda_playground_exporter import export_to_edaplayground, SIMULATOR_PRESETS
from verisight.server.app import create_app


def test_export_to_edaplayground_basic(tmp_path):
    """Test standard export of ALU RTL and TB into EDA Playground bundle."""
    rtl_path = "examples/rtl/alu.sv"
    tb_path = "examples/tb/alu_tb.sv"
    out_dir = tmp_path / "edaplayground_bundle"

    res = export_to_edaplayground(
        rtl_path=rtl_path,
        tb_path=tb_path,
        output_dir=str(out_dir),
        preferred_simulator="questa",
        anonymize_rtl=False,
    )

    assert Path(res["design_sv"]).exists()
    assert Path(res["testbench_sv"]).exists()
    assert Path(res["launch_html"]).exists()
    assert Path(res["config_json"]).exists()
    assert Path(res["readme_md"]).exists()

    design_content = Path(res["design_sv"]).read_text()
    assert "module alu" in design_content
    assert "design.sv" in design_content

    tb_content = Path(res["testbench_sv"]).read_text()
    assert "module alu_tb" in tb_content
    assert "$dumpfile" in tb_content
    assert "$dumpvars" in tb_content

    config = json.loads(Path(res["config_json"]).read_text())
    assert config["recommended_simulator"] == "questa"
    assert "questa" in config["simulators"]
    assert "vcs" in config["simulators"]
    assert "edaplayground_url" in config

    assert Path(res["userscript_js"]).exists()
    userscript = Path(res["userscript_js"]).read_text()
    assert "// ==UserScript==" in userscript
    assert "VeriSight" in userscript

    launch_html = Path(res["launch_html"]).read_text()
    assert "EDA Playground Cloud Simulation Studio" in launch_html
    assert "Copy design.sv" in launch_html
    assert "Copy testbench.sv" in launch_html
    assert "bookmarkletLink" in launch_html
    assert "Copy Console Script" in launch_html


def test_eda_runner_fallback(tmp_path):
    """Test eda_runner fallback when Playwright is not installed."""
    from verisight.tools.eda_runner import run_eda_browser
    out_dir = tmp_path / "runner_test_bundle"
    res = export_to_edaplayground(
        rtl_path="examples/rtl/alu.sv",
        tb_path="examples/tb/alu_tb.sv",
        output_dir=str(out_dir),
    )
    success = run_eda_browser(bundle_dir=str(out_dir))
    assert success is True


def test_export_to_edaplayground_anonymized(tmp_path):
    """Test export with confidential RTL anonymization token masking."""
    rtl_path = "examples/rtl/alu.sv"
    tb_path = "examples/tb/alu_tb.sv"
    out_dir = tmp_path / "anon_bundle"

    res = export_to_edaplayground(
        rtl_path=rtl_path,
        tb_path=tb_path,
        output_dir=str(out_dir),
        anonymize_rtl=True,
    )

    assert res["anonymized"] is True
    assert res["anonymized_count"] > 0

    design_content = Path(res["design_sv"]).read_text()
    assert "mod_" in design_content or "sig_" in design_content


def test_eda_playground_fastapi_endpoint(tmp_path):
    """Test the Web Cockpit FastAPI endpoint for EDA Playground export."""
    app = create_app()
    client = TestClient(app)

    out_dir = tmp_path / "web_edap"
    response = client.post(
        "/api/export/edaplayground",
        json={
            "rtl_path": "examples/rtl/alu.sv",
            "tb_path": "examples/tb/alu_tb.sv",
            "output_dir": str(out_dir),
            "preferred_simulator": "vcs",
            "anonymize_rtl": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert Path(data["design_sv"]).exists()
    assert Path(data["testbench_sv"]).exists()
    assert Path(data["launch_html"]).exists()
