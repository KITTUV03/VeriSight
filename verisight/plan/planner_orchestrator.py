"""
VeriSight Plan Orchestrator.

Coordinates the end-to-end verification planning pipeline:
1. Spec decomposition & RTL delta inspection (FeatureExtractor)
2. Test plan scenario generation (TestPlanner)
3. Functional coverage model & SystemVerilog covergroup generation (CoverageArchitect)
4. SVA assertion suite & SystemVerilog assertion bind generation (AssertionArchitect)
5. Bi-directional traceability matrix & reporting (TraceabilityEngine)
6. Token-saving semantic RAG caching via ChromaDB
"""

import os
import re
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from verisight.config import get_config, VeriSightConfig
from verisight.plan.schemas import VerificationPlanReport
from verisight.plan.feature_extractor import FeatureExtractor
from verisight.plan.test_planner import TestPlanner
from verisight.plan.coverage_architect import CoverageArchitect
from verisight.plan.assertion_architect import AssertionArchitect
from verisight.plan.coverage_correlator import CoverageCorrelator
from verisight.plan.traceability import (
    build_traceability_matrix,
    export_csv,
    export_markdown,
    export_html,
)
from verisight.rag.knowledge_base import KnowledgeBase
from verisight.utils.logger import get_logger

logger = get_logger("plan.orchestrator")


def _parse_width(w: Any) -> int:
    if isinstance(w, int):
        return max(1, w)
    if isinstance(w, str):
        m = re.search(r"\[?(\d+)\s*:\s*(\d+)\]?", w)
        if m:
            return max(1, abs(int(m.group(1)) - int(m.group(2))) + 1)
        m_num = re.search(r"\d+", w)
        if m_num:
            return max(1, int(m_num.group(0)))
    return 1


class VeriSightPlanner:
    """End-to-end autonomous Verification & Architecture Planner."""

    def __init__(self, output_dir: str = "output/verification_plan", knowledge_base: Optional[KnowledgeBase] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.kb = knowledge_base

        self.feature_extractor = FeatureExtractor()
        self.test_planner = TestPlanner()
        self.coverage_architect = CoverageArchitect()
        self.assertion_architect = AssertionArchitect()
        self.coverage_correlator = CoverageCorrelator()

    def run(
        self,
        spec_path: str,
        rtl_path: Optional[str] = None,
        design_name: Optional[str] = None,
        coverage_path: Optional[str] = None,
        generate_uvm: bool = False,
    ) -> VerificationPlanReport:
        """
        Execute full autonomous verification planning pipeline.

        Args:
            spec_path: Path to specification document (.md, .txt).
            rtl_path: Optional path to RTL file or directory (.sv, .v).
            design_name: Optional design name (inferred from path if omitted).
            generate_uvm: If True, also generate a full UVM testbench environment
                (verisight.uvm.UVMArchitect) whose coverage subscriber reuses this
                plan's own covergroups instead of a second, independent model.
                Off by default to preserve existing behavior/outputs.

        Returns:
            VerificationPlanReport object.
        """
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║           VeriSight Plan — Autonomous Architect          ║")
        logger.info("╚══════════════════════════════════════════════════════════╝")

        spec_file = Path(spec_path).expanduser()
        if not spec_file.exists():
            raise FileNotFoundError(f"Specification file not found: {spec_path}")

        # If a directory was provided, auto-discover the spec file inside it
        if spec_file.is_dir():
            candidates = list(spec_file.glob("*.md")) + list(spec_file.glob("*.txt")) + list(spec_file.glob("*.pdf"))
            if not candidates:
                raise FileNotFoundError(f"No .md, .txt, or .pdf specification file found inside directory: {spec_path}")
            spec_file = candidates[0]
            logger.info(f"Auto-discovered specification file in directory: {spec_file}")

        from verisight.utils.file_utils import read_file
        spec_text = read_file(spec_file)

        if not design_name:
            design_name = spec_file.stem.replace("_spec", "").replace("spec", "").upper() or "DUT"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Extract RTL ports and structures for grounding
        rtl_info: Dict[str, Any] = {
            "ports": [],
            "clocks": [],
            "resets": [],
            "fsms": [],
        }

        # Auto-discover RTL source file in adjacent project directories if not provided
        if not rtl_path:
            cand_dirs = [
                spec_file.parent.parent / "rtl",
                spec_file.parent / "rtl",
                spec_file.parent,
            ]
            for cd in cand_dirs:
                if cd.exists() and cd.is_dir():
                    rtl_cands = list(cd.glob("*.sv")) + list(cd.glob("*.v"))
                    if rtl_cands:
                        rtl_path = str(rtl_cands[0])
                        logger.info(f"Auto-discovered RTL source file for {design_name}: {rtl_path}")
                        break

        if rtl_path and Path(rtl_path).exists():
            try:
                from verisight.parsers.rtl_parser import parse_rtl
                rtl_data = parse_rtl(rtl_path)
                for mod in getattr(rtl_data, "modules", []):
                    for p in getattr(mod, "ports", []):
                        rtl_info["ports"].append({
                            "name": p.name,
                            "dir": getattr(p, "direction", "in"),
                            "width": _parse_width(getattr(p, "width", 1) or 1),
                        })
                    for cd in getattr(mod, "clock_domains", []):
                        if getattr(cd, "clock_signal", None):
                            rtl_info["clocks"].append(cd.clock_signal)
                        if getattr(cd, "reset_signal", None):
                            rtl_info["resets"].append(cd.reset_signal)
                    for fsm in getattr(mod, "fsms", []):
                        rtl_info["fsms"].append({
                            "name": fsm.name,
                            "states": [s.name for s in getattr(fsm, "states", [])],
                        })
                logger.info(f"Extracted {len(rtl_info['ports'])} RTL ports for grounding coverage & assertions.")
            except Exception as e:
                logger.warning(f"Could not parse RTL for grounding: {e}")

        # 1. Feature Extraction & RTL Delta Check
        logger.info(f"Phase 1/4: Decomposing Specification into Features for {design_name}...")
        features = self.feature_extractor.extract_features(
            spec_text=spec_text,
            spec_path=spec_path,
            rtl_path=rtl_path,
        )

        # 2. Test Plan Formulation
        logger.info(f"Phase 2/4: Formulating Exhaustive Test Scenarios...")
        test_scenarios = self.test_planner.generate_test_plan(
            features=features,
            design_name=design_name,
            rtl_info=rtl_info,
        )

        # 3. Functional Coverage Model & SystemVerilog Code Generation
        logger.info(f"Phase 3/4: Designing Functional Coverage Model & SystemVerilog Code...")
        covergroups = self.coverage_architect.design_coverage_model(
            features=features,
            design_name=design_name,
            rtl_info=rtl_info,
            spec_text=spec_text,
        )
        sv_coverage_code = self.coverage_architect.generate_sv_code(
            covergroups=covergroups,
            design_name=design_name,
            rtl_info=rtl_info,
        )

        # 4. SVA Assertion Suite & SystemVerilog Code Generation
        logger.info(f"Phase 4/4: Designing SVA Assertions Suite & SystemVerilog Code...")
        assertions = self.assertion_architect.design_assertions(
            features=features,
            design_name=design_name,
            rtl_info=rtl_info,
            spec_text=spec_text,
        )
        sv_assertion_code = self.assertion_architect.generate_sv_code(
            assertions=assertions,
            design_name=design_name,
            rtl_info=rtl_info,
        )

        # 5. SystemVerilog Syntax Validation Gate (pyslang AST check)
        from verisight.parsers.sv_frontend import compile_text, format_diagnostics

        cov_compile = compile_text(sv_coverage_code, name="coverage_model.sv")
        cov_syntax_ok = cov_compile.syntax_ok
        val_notes: List[str] = []

        if cov_syntax_ok:
            logger.info("Coverage model SystemVerilog syntax verified clean (pyslang).")
            val_notes.append("coverage_model.sv: Syntax clean (0 errors).")
        else:
            diag_str = format_diagnostics(cov_compile.diagnostics, limit=3)
            logger.warning(f"Coverage model SV syntax diagnostics:\n{diag_str}")
            val_notes.append(f"coverage_model.sv: {diag_str}")

        sva_compile = compile_text(sv_assertion_code, name="dut_assertions.sv")
        sva_syntax_ok = sva_compile.syntax_ok
        if sva_syntax_ok:
            logger.info("SVA assertions SystemVerilog syntax verified clean (pyslang).")
            val_notes.append("dut_assertions.sv: Syntax clean (0 errors).")
        else:
            diag_str = format_diagnostics(sva_compile.diagnostics, limit=3)
            logger.warning(f"SVA assertions SV syntax diagnostics:\n{diag_str}")
            val_notes.append(f"dut_assertions.sv: {diag_str}")

        # 6. Bi-directional Traceability Matrix
        logger.info("Building Bi-Directional Traceability Matrix...")
        traceability_matrix = build_traceability_matrix(
            features=features,
            tests=test_scenarios,
            covergroups=covergroups,
            assertions=assertions,
        )

        total_cov_points = sum(len(cg.coverpoints) for cg in covergroups)

        # 6b. Optional UVM Testbench Environment Generation
        # Reuses this plan's own covergroups (grounded in extracted features) for
        # the UVM coverage subscriber instead of synthesizing a second, independent
        # coverage model.
        uvm_result = None
        if generate_uvm:
            logger.info("Generating UVM testbench environment (reusing this plan's coverage model)...")
            try:
                from verisight.uvm.uvm_architect import UVMArchitect
                uvm_result = UVMArchitect(output_dir=str(self.output_dir / "uvm")).generate(
                    rtl_path=rtl_path,
                    spec_path=spec_path,
                    design_name=design_name,
                    covergroups=covergroups,
                )
                logger.info(f"UVM environment generated in {uvm_result.output_dir} ({len(uvm_result.files_generated)} files).")
            except Exception as e:
                logger.warning(f"UVM environment generation failed: {e}")

        report = VerificationPlanReport(
            plan_id=str(uuid.uuid4())[:8],
            design_name=design_name,
            timestamp=timestamp,
            spec_source=spec_path,
            rtl_source=rtl_path,
            coverage_db_source=coverage_path,
            total_features=len(features),
            total_tests=len(test_scenarios),
            total_coverage_points=total_cov_points,
            total_assertions=len(assertions),
            features=features,
            test_scenarios=test_scenarios,
            covergroups=covergroups,
            assertions=assertions,
            traceability_matrix=traceability_matrix,
            rag_cached=True if self.kb else False,
            sv_coverage_code=sv_coverage_code,
            sv_assertion_code=sv_assertion_code,
            sv_coverage_syntax_ok=cov_syntax_ok,
            sv_assertions_syntax_ok=sva_syntax_ok,
            sv_validation_notes=val_notes,
            uvm_generated=uvm_result is not None,
            uvm_output_dir=uvm_result.output_dir if uvm_result else None,
            uvm_files_generated=uvm_result.files_generated if uvm_result else [],
            uvm_syntax_ok=uvm_result.syntax_clean if uvm_result else None,
            uvm_protocol_detected=uvm_result.protocol_detected if uvm_result else None,
        )

        # 7. Dynamic Coverage Closure Ingestion (Planned vs. Actual UCDB/vDB)
        logger.info("Correlating Planned Requirements with Simulator Coverage Database...")
        report = self.coverage_correlator.correlate(
            report=report,
            coverage_path=coverage_path,
        )


        # 6. Save Artifacts
        # JSON Schema
        with open(self.output_dir / "verification_plan.json", "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        # Markdown Document
        export_markdown(report, self.output_dir / "verification_plan.md")

        # HTML Interactive Dashboard
        export_html(report, self.output_dir / "verification_plan.html")

        # Traceability CSV
        export_csv(report.traceability_matrix, self.output_dir / "traceability_matrix.csv")

        # SystemVerilog Code Files
        with open(self.output_dir / "coverage_model.sv", "w", encoding="utf-8") as f:
            f.write(sv_coverage_code)
        with open(self.output_dir / "dut_assertions.sv", "w", encoding="utf-8") as f:
            f.write(sv_assertion_code)

        # 7. Persist to ChromaDB RAG if available
        if self.kb:
            try:
                self.kb.store_document(
                    collection_name="spec_requirements",
                    doc_id=f"plan_{report.plan_id}",
                    text=f"Verification Plan for {design_name}: {len(features)} features, {len(test_scenarios)} tests.",
                    metadata={"design": design_name, "timestamp": timestamp},
                )
                logger.info("Persisted Verification Plan summary to ChromaDB RAG.")
            except Exception as e:
                logger.debug(f"Could not store plan in ChromaDB: {e}")

        logger.info(f"Verification Plan Complete! Outputs saved in: {self.output_dir}/")
        return report
