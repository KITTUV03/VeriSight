"""
Unit tests for VeriSight Live Web Cockpit Server (FastAPI).
"""

import pytest
from fastapi.testclient import TestClient
from verisight.server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_serve_index(client):
    """Verify root path serves the single page application HTML."""
    res = client.get("/")
    assert res.status_code == 200
    assert "VeriSight" in res.text
    assert "Neural Cockpit" in res.text or "VERISIGHT" in res.text


def test_api_status(client):
    """Verify system diagnostics endpoint returns EDA tools and projects."""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "simulators" in data
    assert "projects" in data
    assert len(data["projects"]) > 0


def test_api_runs(client):
    """Verify past runs discovery endpoint."""
    res = client.get("/api/runs")
    assert res.status_code == 200
    data = res.json()
    assert "runs" in data
    assert isinstance(data["runs"], list)


def test_api_waveform(client):
    """Verify waveform endpoint returns signals or graceful message."""
    res = client.get("/api/waveform")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "signals" in data


def test_api_file_valid(client):
    """Verify safe workspace file reading endpoint."""
    res = client.get("/api/file?path=examples/rtl/alu.sv")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "alu.sv"
    assert "module alu" in data["content"]


def test_api_file_path_traversal_blocked(client):
    """Verify directory traversal attempts are securely rejected with 403."""
    res = client.get("/api/file?path=../../etc/passwd")
    assert res.status_code == 403
