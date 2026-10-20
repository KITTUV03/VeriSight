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
    ) -> VerificationPlanReport:
        """
        Execute full autonomous verification planning pipeline.

        Args:
            spec_path: Path to specification document (.md, .txt).
            rtl_path: Optional path to RTL file or directory (.sv, .v).
            design_name: Optional design name (inferred from path if omitted).

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
        )

        # 3. Functional Coverage Model & SystemVerilog Code Generation
        logger.info(f"Phase 3/4: Designing Functional Coverage Model & SystemVerilog Code...")
        covergroups = self.coverage_architect.design_coverage_model(
            features=features,
            design_name=design_name,
        )
        sv_coverage_code = self.coverage_architect.generate_sv_code(
            covergroups=covergroups,
            design_name=design_name,
        )

        # 4. SVA Assertion Suite & SystemVerilog Code Generation
        logger.info(f"Phase 4/4: Designing SVA Assertions Suite & SystemVerilog Code...")
        assertions = self.assertion_architect.design_assertions(
            features=features,
            design_name=design_name,
        )
        sv_assertion_code = self.assertion_architect.generate_sv_code(
            assertions=assertions,
            design_name=design_name,
        )

        # 5. Bi-directional Traceability Matrix
        logger.info("Building Bi-Directional Traceability Matrix...")
        traceability_matrix = build_traceability_matrix(
            features=features,
            tests=test_scenarios,
            covergroups=covergroups,
            assertions=assertions,
        )

        total_cov_points = sum(len(cg.coverpoints) for cg in covergroups)

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
        )

        # 6. Dynamic Coverage Closure Ingestion (Planned vs. Actual UCDB/vDB)
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
