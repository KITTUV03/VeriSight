"""
VeriSight Live Interactive Web Cockpit UI — FastAPI Backend.

Provides real-time REST endpoints and an integrated single-page application for:
- Live EDA simulation runs (Icarus / Verilator / Questa / VCS)
- Interactive digital waveform inspection (VCD transitions & timeline)
- Root-cause diagnosis and anomaly tracing
- Automated RTL patch review and 1-click healing
- Verification plan traceability and live coverage closure cockpit
"""

import os
import shutil
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from verisight.tools.sim_runner import find_best_simulator, execute_closed_loop_flow
from verisight.parsers.vcd_parser import parse_vcd
from verisight.utils.logger import get_logger

logger = get_logger("web_cockpit")

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
OUTPUT_DIR = WORKSPACE_DIR / "output"


class SimRequest(BaseModel):
    rtl_path: str = "examples/rtl/alu.sv"
    tb_path: str = "examples/tb/alu_tb.sv"
    spec_path: Optional[str] = "examples/specs/alu_spec.md"
    simulator: str = "auto"
    output_dir: str = "output/closed_loop"
    airgap: bool = True
    provider: Optional[str] = "gemini"
    api_key: Optional[str] = None
    model_name: Optional[str] = "gemini-3.5-flash"


class ApplyFixRequest(BaseModel):
    target_file: str
    patch_file: Optional[str] = None
    patch_content: Optional[str] = None


class RevertFixRequest(BaseModel):
    target_file: str


def create_app() -> FastAPI:
    """Create and configure the FastAPI web cockpit application."""
    app = FastAPI(
        title="VeriSight Neural Cockpit",
        description="Live Interactive Silicon Verification & Waveform Studio",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Mount static assets
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/reports", StaticFiles(directory=str(OUTPUT_DIR)), name="reports")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = STATIC_DIR / "index.html"
        if not index_file.exists():
            return HTMLResponse("<h1>VeriSight Web Cockpit Initializing...</h1>")
        return FileResponse(index_file)

    @app.get("/api/status")
    async def get_system_status():
        """Retrieve system diagnostics, detected EDA tools, and API key status."""
        detected_sim = find_best_simulator()
        simulators_status = {
            "best": detected_sim,
            "iverilog": bool(shutil.which("iverilog")),
            "vvp": bool(shutil.which("vvp")),
            "verilator": bool(shutil.which("verilator")),
            "questa": bool(shutil.which("vsim")),
            "vcs": bool(shutil.which("vcs")),
        }

        has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

        # Pre-packaged projects
        projects = []
        if (WORKSPACE_DIR / "examples/rtl/alu.sv").exists():
            projects.append({
                "id": "alu",
                "name": "ALU (Arithmetic Logic Unit)",
                "rtl": "examples/rtl/alu.sv",
                "tb": "examples/tb/alu_tb.sv",
                "spec": "examples/specs/alu_spec.md",
                "description": "Missing reset logic bug resulting in X-propagation and UVM errors",
            })
        if (WORKSPACE_DIR / "projects/fifo/rtl/fifo.sv").exists():
            projects.append({
                "id": "fifo",
                "name": "Synchronous FIFO Buffer",
                "rtl": "projects/fifo/rtl/fifo.sv",
                "tb": "projects/fifo/tb/fifo_tb.sv",
                "spec": "projects/fifo/specs/spec.md",
                "description": "FIFO boundary condition and full/empty flag synchronization",
            })

        return {
            "status": "online",
            "workspace": str(WORKSPACE_DIR),
            "simulators": simulators_status,
            "ai_keys": {
                "gemini": has_gemini,
                "anthropic": has_anthropic,
                "sovereign_airgap": True,
            },
            "projects": projects,
        }

    @app.get("/api/runs")
    async def list_runs():
        """Discover and list all previous verification and debug runs in output/."""
        runs = []
        if not OUTPUT_DIR.exists():
            return {"runs": []}

        for p in sorted(OUTPUT_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_dir():
                continue

            run_id = p.name
            mtime = p.stat().st_mtime
            has_report_html = (p / "report.html").exists() or (p / "debug" / "report.html").exists()
            has_plan_html = (p / "verification_plan.html").exists() or (p / "plan" / "verification_plan.html").exists()
            has_vcd = (p / "sim.vcd").exists() or (p / "sim" / "sim.vcd").exists()

            # Inspect error.json if present
            err_json_path = p / "error.json"
            if not err_json_path.exists():
                err_json_path = p / "debug" / "error.json"

            classification = "Simulation Run"
            confidence = 0
            root_cause = ""
            if err_json_path.exists():
                try:
                    data = json.loads(err_json_path.read_text())
                    classification = data.get("classification", "Unknown")
                    confidence = data.get("confidence", 0)
                    root_cause = data.get("root_cause", "")
                except Exception:
                    pass

            runs.append({
                "id": run_id,
                "path": str(p),
                "timestamp": mtime,
                "has_report_html": has_report_html,
                "has_plan_html": has_plan_html,
                "has_vcd": has_vcd,
                "classification": classification,
                "confidence": confidence,
                "root_cause": root_cause,
                "report_url": f"/reports/{run_id}/debug/report.html" if (p / "debug" / "report.html").exists() else (f"/reports/{run_id}/report.html" if (p / "report.html").exists() else None),
                "plan_url": f"/reports/{run_id}/plan/verification_plan.html" if (p / "plan" / "verification_plan.html").exists() else (f"/reports/{run_id}/verification_plan.html" if (p / "verification_plan.html").exists() else None),
            })

        return {"runs": runs}

    @app.get("/api/runs/{run_id}")
    async def get_run_details(run_id: str):
        """Retrieve detailed outputs and files for a specific run."""
        run_path = OUTPUT_DIR / run_id
        if not run_path.exists():
            raise HTTPException(status_code=404, detail="Run not found")

        # Find error.json
        err_data = None
        for ep in [run_path / "error.json", run_path / "debug" / "error.json"]:
            if ep.exists():
                try:
                    err_data = json.loads(ep.read_text())
                    break
                except Exception:
                    pass

        # Find summary.txt
        summary_txt = ""
        for sp in [run_path / "summary.txt", run_path / "debug" / "summary.txt"]:
            if sp.exists():
                try:
                    summary_txt = sp.read_text()
                    break
                except Exception:
                    pass

        # Find sim.log
        sim_log = ""
        for lp in [run_path / "sim" / "sim.log", run_path / "sim.log"]:
            if lp.exists():
                try:
                    sim_log = lp.read_text()
                    break
                except Exception:
                    pass

        # Find fix patch
        fix_patch = ""
        for fp in [run_path / "fix", run_path / "debug" / "fix"]:
            if fp.exists() and fp.is_dir():
                diff_files = list(fp.glob("*.patch")) + list(fp.glob("*.diff")) + list(fp.glob("*.sv"))
                if diff_files:
                    try:
                        fix_patch = diff_files[0].read_text()
                    except Exception:
                        pass

        # Find VCD path
        vcd_rel = None
        for vp in [run_path / "sim" / "sim.vcd", run_path / "sim.vcd"]:
            if vp.exists():
                vcd_rel = str(vp.relative_to(WORKSPACE_DIR))
                break

        return {
            "id": run_id,
            "error_data": err_data,
            "summary": summary_txt,
            "sim_log": sim_log[:50000],  # cap length for responsive JSON
            "fix_patch": fix_patch,
            "vcd_path": vcd_rel,
            "report_url": f"/reports/{run_id}/debug/report.html" if (run_path / "debug" / "report.html").exists() else (f"/reports/{run_id}/report.html" if (run_path / "report.html").exists() else None),
            "plan_url": f"/reports/{run_id}/plan/verification_plan.html" if (run_path / "plan" / "verification_plan.html").exists() else (f"/reports/{run_id}/verification_plan.html" if (run_path / "verification_plan.html").exists() else None),
        }

    @app.post("/api/sim")
    async def run_simulation_api(req: SimRequest):
        """Execute closed-loop simulation on demand and return real-time metrics."""
        rtl = str(WORKSPACE_DIR / req.rtl_path) if not Path(req.rtl_path).is_absolute() else req.rtl_path
        tb = str(WORKSPACE_DIR / req.tb_path) if not Path(req.tb_path).is_absolute() else req.tb_path
        spec = None
        if req.spec_path:
            spec = str(WORKSPACE_DIR / req.spec_path) if not Path(req.spec_path).is_absolute() else req.spec_path

        out = str(WORKSPACE_DIR / req.output_dir) if not Path(req.output_dir).is_absolute() else req.output_dir

        if not Path(rtl).exists():
            raise HTTPException(status_code=400, detail=f"RTL path does not exist: {req.rtl_path}")
        if not Path(tb).exists():
            raise HTTPException(status_code=400, detail=f"Testbench path does not exist: {req.tb_path}")

        try:
            results = execute_closed_loop_flow(
                rtl_path=rtl,
                tb_path=tb,
                spec_path=spec,
                simulator=req.simulator,
                output_dir=out,
                airgap=req.airgap,
                provider=req.provider,
                api_key=req.api_key,
                model_name=req.model_name,
                launch_browser=False,
            )

            sim_res = results.get("sim")
            rca_res = results.get("rca")
            dashboards = results.get("dashboards", {})

            # Prepare URLs relative to reports
            run_id = Path(out).name
            report_url = f"/reports/{run_id}/debug/report.html"
            plan_url = f"/reports/{run_id}/plan/verification_plan.html" if spec else None

            # Read simulation log preview
            log_content = ""
            if sim_res and Path(sim_res.log_path).exists():
                try:
                    log_content = Path(sim_res.log_path).read_text(errors="ignore")
                except Exception:
                    pass

            # Read fix patch if created
            fix_patch = ""
            fix_dir = Path(out) / "debug" / "fix"
            if fix_dir.exists():
                patches = list(fix_dir.glob("*.patch")) + list(fix_dir.glob("*.diff")) + list(fix_dir.glob("*.sv"))
                if patches:
                    try:
                        fix_patch = patches[0].read_text(errors="ignore")
                    except Exception:
                        pass

            return {
                "success": sim_res.success if sim_res else False,
                "simulator": sim_res.simulator if sim_res else req.simulator,
                "duration_s": sim_res.duration_s if sim_res else 0.0,
                "error_count": sim_res.error_count if sim_res else 0,
                "warning_count": sim_res.warning_count if sim_res else 0,
                "classification": rca_res.classification if rca_res else "None",
                "confidence": rca_res.confidence if rca_res else 0,
                "root_cause": rca_res.root_cause if rca_res else "None",
                "category": rca_res.category if rca_res else "None",
                "log_preview": log_content[:20000],
                "fix_patch": fix_patch,
                "vcd_path": str(sim_res.vcd_path.relative_to(WORKSPACE_DIR)) if (sim_res and sim_res.vcd_path and sim_res.vcd_path.exists()) else None,
                "report_url": report_url,
                "plan_url": plan_url,
                "run_id": run_id,
            }
        except Exception as e:
            logger.exception("Simulation execution failed")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/waveform")
    async def get_waveform_data(path: Optional[str] = None):
        """Parse VCD waveform and return compact transition vectors for frontend rendering."""
        vcd_target = None
        if path:
            candidate = WORKSPACE_DIR / path if not Path(path).is_absolute() else Path(path)
            if candidate.exists():
                vcd_target = candidate

        if not vcd_target:
            # Fallback to latest sim.vcd
            for cand in [
                OUTPUT_DIR / "closed_loop" / "sim" / "sim.vcd",
                OUTPUT_DIR / "demo_alu_closed_loop" / "sim" / "sim.vcd",
                OUTPUT_DIR / "sim.vcd",
            ]:
                if cand.exists():
                    vcd_target = cand
                    break

        if not vcd_target or not vcd_target.exists():
            return {
                "status": "not_found",
                "message": "No VCD waveform available. Run a simulation first.",
                "signals": [],
            }

        vcd_data = parse_vcd(str(vcd_target))

        # Simplify signals for fast interactive UI canvas rendering
        formatted_signals = []
        sig_list = list(vcd_data.signals.values()) if isinstance(vcd_data.signals, dict) else list(vcd_data.signals)
        for sig in sig_list[:50]:  # limit to top 50 signals
            transitions = []
            for tr in sig.transitions[:200]:  # limit transitions
                transitions.append({
                    "t": tr.time_ps,
                    "v": tr.value,
                })

            formatted_signals.append({
                "name": sig.name,
                "width": sig.width,
                "is_bus": sig.width > 1,
                "transitions": transitions,
            })

        end_time_ps = 250000
        for s in sig_list:
            if s.transitions:
                end_time_ps = max(end_time_ps, s.transitions[-1].time_ps)

        return {
            "status": "ok",
            "source": str(vcd_target.relative_to(WORKSPACE_DIR)),
            "timescale": vcd_data.timescale,
            "end_time_ps": end_time_ps,
            "signal_count": len(vcd_data.signals),
            "signals": formatted_signals,
        }

    @app.post("/api/apply-fix")
    async def apply_fix(req: ApplyFixRequest):
        """Apply the generated patch or corrected code to the target RTL file, backing up the original."""
        target = WORKSPACE_DIR / req.target_file if not Path(req.target_file).is_absolute() else Path(req.target_file)
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"Target file not found: {req.target_file}")

        # Create backup
        backup_file = target.with_suffix(target.suffix + ".verisight_bak")
        if not backup_file.exists():
            shutil.copy2(target, backup_file)

        applied_content = None
        if req.patch_content:
            applied_content = req.patch_content
        elif req.patch_file:
            p_path = WORKSPACE_DIR / req.patch_file if not Path(req.patch_file).is_absolute() else Path(req.patch_file)
            if p_path.exists():
                applied_content = p_path.read_text(errors="ignore")

        if not applied_content:
            raise HTTPException(status_code=400, detail="No patch content or file provided")

        target.write_text(applied_content)
        return {
            "status": "applied",
            "target": str(target.relative_to(WORKSPACE_DIR)),
            "backup": str(backup_file.relative_to(WORKSPACE_DIR)),
            "message": f"Successfully patched {target.name}. Original backed up to {backup_file.name}.",
        }

    @app.post("/api/revert-fix")
    async def revert_fix(req: RevertFixRequest):
        """Revert the target RTL file from its .verisight_bak backup."""
        target = WORKSPACE_DIR / req.target_file if not Path(req.target_file).is_absolute() else Path(req.target_file)
        backup_file = target.with_suffix(target.suffix + ".verisight_bak")
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail="No backup found to revert from")

        shutil.copy2(backup_file, target)
        backup_file.unlink()
        return {
            "status": "reverted",
            "target": str(target.relative_to(WORKSPACE_DIR)),
            "message": f"Successfully reverted {target.name} to pre-patch state.",
        }

    @app.get("/api/file")
    async def read_workspace_file(path: str = Query(...)):
        """Read a workspace source file safely (prevent directory traversal)."""
        target = (WORKSPACE_DIR / path).resolve()
        if not str(target).startswith(str(WORKSPACE_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied: outside workspace")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        try:
            content = target.read_text(errors="ignore")
            return {
                "path": path,
                "name": target.name,
                "size": target.stat().st_size,
                "content": content,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False, open_browser: bool = True):
    """Start the Uvicorn web server hosting VeriSight Web Cockpit."""
    import uvicorn
    import webbrowser

    url = f"http://{host}:{port}"
    logger.info(f"⚡ Launching VeriSight Web Cockpit at {url}")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run("verisight.server.app:create_app", factory=True, host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
