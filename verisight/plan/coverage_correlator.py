"""
Dynamic Coverage Closure Correlator for VeriSight Plan.

Correlates Planned Verification Requirements (Features, Covergroups, Assertions)
against Actual Simulator Coverage Databases (Questa UCDB, Synopsys vDB, JSON).

Transforms static verification plans into a Live Coverage Cockpit:
- Calculates actual % hit per feature (e.g. Feature 1: 92% hit (Target: 100%))
- Flags uncovered / unhit bins as critical coverage holes
- Generates targeted SystemVerilog / UVM directed sequences to close the remaining deficit
"""

import re
from typing import List, Dict, Any, Optional
from verisight.plan.schemas import (
    FeatureItem,
    CovergroupDef,
    CoveragePoint,
    TraceabilityRow,
    VerificationPlanReport,
)
from verisight.plan.coverage_ingest import SimulatorCoverageDB, CoverageIngester
from verisight.utils.logger import get_logger

logger = get_logger("plan.coverage_correlator")


class CoverageCorrelator:
    """Correlator matching planned covergroups with simulator coverage databases."""

    def __init__(self):
        self.ingester = CoverageIngester()

    def correlate(
        self,
        report: VerificationPlanReport,
        coverage_path: Optional[str] = None,
        coverage_db: Optional[SimulatorCoverageDB] = None,
    ) -> VerificationPlanReport:
        """
        Correlate plan report with actual simulator coverage DB.

        Args:
            report: VerificationPlanReport model.
            coverage_path: Path to simulator coverage report (.ucdb, .vdb, .txt, .json).
            coverage_db: Pre-parsed SimulatorCoverageDB (optional).

        Returns:
            Updated VerificationPlanReport with actual coverage metrics and unhit holes.
        """
        if not coverage_db and coverage_path:
            coverage_db = self.ingester.ingest(coverage_path)

        # If no real coverage DB was provided or found, do not fabricate simulation
        # results. Leave actual_coverage/coverage_status at their schema defaults
        # (None/unset) so consumers can tell "not yet simulated" apart from "0% hit".
        if not coverage_db or coverage_db.total_bins == 0:
            logger.info(
                "No external simulator coverage database provided or supplied DB has "
                "0 bins; skipping coverage correlation. Plan remains as-designed — no "
                "actual coverage percentages are reported until a real coverage DB is ingested."
            )
            report.coverage_db_source = "Not Simulated (no coverage database provided)"
            report.coverage_evidence_level = "no_simulation_data"
            return report

        report.coverage_db_source = coverage_db.source_path or "Simulator UCDB/vDB Ingest"
        report.coverage_evidence_level = "simulator_data_ingested"

        # Build lookup table for ingested coverpoints and bins
        # Normalize keys: lowercase, alphanumeric, with hierarchical leaf stripping
        ingested_cp_map: Dict[str, Any] = {}
        ingested_bin_map: Dict[str, Any] = {}

        for cg_name, cg in coverage_db.covergroups.items():
            for cp_name, cp in cg.coverpoints.items():
                norm_cp = self._norm(cp_name)
                norm_cp_raw = re.sub(r"[^a-zA-Z0-9]", "", cp_name).lower()
                ingested_cp_map[norm_cp] = cp
                ingested_cp_map[norm_cp_raw] = cp
                for b_name, b in cp.bins.items():
                    norm_b = self._norm(b_name)
                    norm_b_raw = re.sub(r"[^a-zA-Z0-9]", "", b_name).lower()
                    ingested_bin_map[f"{norm_cp}::{norm_b}"] = b
                    ingested_bin_map[f"{norm_cp_raw}::{norm_b_raw}"] = b
                    ingested_bin_map[norm_b] = b
                    ingested_bin_map[norm_b_raw] = b

        total_planned_bins = 0
        total_hit_bins = 0
        total_unreported_bins = 0
        all_holes: List[Dict[str, Any]] = []
        sim_unhit_list = list(coverage_db.unhit_bins_list)
        assigned_holes: set = set()

        # 1. Update Covergroups & Coverpoints with actual simulator metrics
        for cg in report.covergroups:
            cg_total = 0
            cg_hit = 0
            for cp in cg.coverpoints:
                norm_cp = self._norm(cp.name)
                sim_cp = ingested_cp_map.get(norm_cp)

                # If no direct coverpoint name match, try matching by target signal
                if not sim_cp:
                    norm_sig = self._norm(cp.target_signal)
                    sim_cp = ingested_cp_map.get(norm_sig)

                cp_total = len(cp.bins) or 1
                cp_hit = 0
                unhit_bin_names = []
                unreported_bin_names = []

                for b in cp.bins:
                    total_planned_bins += 1
                    norm_b = self._norm(b.bin_name)
                    sim_b = ingested_bin_map.get(f"{norm_cp}::{norm_b}") or ingested_bin_map.get(norm_b)

                    if sim_b:
                        b.hits = sim_b.hits
                        b.hit_status = "Covered" if sim_b.is_hit else "Unhit"
                        if sim_b.is_hit:
                            cp_hit += 1
                            total_hit_bins += 1
                        else:
                            unhit_bin_names.append(b.bin_name)
                    else:
                        # Fallback if not directly named in simulator dump:
                        b_words = set(re.findall(r"[a-z0-9]+", b.bin_name.lower()))
                        cp_words = set(re.findall(r"[a-z0-9]+", cp.name.lower()))

                        matched_unhit = False
                        if sim_unhit_list:
                            # Only mark unhit if this bin or coverpoint matches an actual unhit hole from the simulator DB
                            for ub in sim_unhit_list:
                                ub_b_words = set(re.findall(r"[a-z0-9]+", ub.bin_name.lower()))
                                ub_cp_words = set(re.findall(r"[a-z0-9]+", ub.coverpoint_name.lower()))
                                if (b_words & ub_b_words) or (cp_words & ub_cp_words):
                                    if any(k in b_words for k in ["overflow", "underflow", "err", "illegal", "zero"]):
                                        matched_unhit = True
                                        break
                        elif any(k in b_words for k in ["overflow", "underflow", "err", "illegal"]):
                            matched_unhit = True

                        if matched_unhit:
                            b.hits = 0
                            b.hit_status = "Unhit"
                            unhit_bin_names.append(b.bin_name)
                        else:
                            # No matching entry in the ingested simulator DB for this
                            # bin — there is no evidence of whether it was hit, so do
                            # not invent a hit count. Report it as unreported rather
                            # than silently counting it as "Covered".
                            b.hits = None
                            b.hit_status = "Not_Reported"
                            unreported_bin_names.append(b.bin_name)

                cp_reported = cp_total - len(unreported_bin_names)

                cp.total_bins_count = cp_total
                cp.hit_bins_count = cp_hit
                cp.unhit_bins = unhit_bin_names
                cp.not_reported_bins = unreported_bin_names
                cp.actual_coverage = round((cp_hit / cp_reported) * 100.0, 1) if cp_reported > 0 else None

                cg_total += cp_reported
                cg_hit += cp_hit
                total_unreported_bins += len(unreported_bin_names)

            cg.actual_coverage = round((cg_hit / cg_total) * 100.0, 1) if cg_total > 0 else None

        # 2. Correlate Feature hit percentage & remaining bins
        # Map feature_id -> list of coverpoints
        feat_to_cps: Dict[str, List[CoveragePoint]] = {}
        for cg in report.covergroups:
            for cp in cg.coverpoints:
                for fid in cp.feature_ids:
                    feat_to_cps.setdefault(fid, []).append(cp)

        for feat in report.features:
            cps = feat_to_cps.get(feat.feature_id, [])
            feat_tot_bins = 0
            feat_reported_bins = 0
            feat_hit_bins = 0
            feat_unhit_bins: List[Dict[str, Any]] = []

            for cp in cps:
                cp_total = cp.total_bins_count or len(cp.bins)
                feat_tot_bins += cp_total
                feat_reported_bins += cp_total - len(cp.not_reported_bins or [])
                feat_hit_bins += cp.hit_bins_count or 0
                for b in cp.bins:
                    if b.hit_status == "Unhit" or (b.hits is not None and b.hits == 0):
                        hole_dict = {
                            "feature_id": feat.feature_id,
                            "feature_title": feat.title,
                            "coverpoint": cp.name,
                            "target_signal": cp.target_signal,
                            "bin_name": b.bin_name,
                            "condition": b.condition,
                            "hits": b.hits or 0,
                        }
                        feat_unhit_bins.append(hole_dict)
                        all_holes.append(hole_dict)

            # If no direct coverpoint holes were found, check if any unhit bins from the simulator report match this feature
            if not feat_unhit_bins and sim_unhit_list:
                feat_text = f"{feat.feature_id} {feat.title} {feat.description}".lower()
                for ub in sim_unhit_list:
                    ub_id = f"{ub.coverpoint_name}::{ub.bin_name}"
                    if ub_id in assigned_holes:
                        continue
                    # Match keywords
                    b_kw = ub.bin_name.lower().replace("bin_", "")
                    cp_kw = ub.coverpoint_name.lower().replace("cp_", "")
                    matched = False

                    if any(k in feat_text for k in b_kw.split("_")):
                        matched = True
                    elif any(k in feat_text for k in cp_kw.split("_")):
                        matched = True
                    elif "overflow" in b_kw and any(k in feat_text for k in ["add", "overflow", "carry", "flag"]):
                        matched = True
                    elif "underflow" in b_kw and any(k in feat_text for k in ["sub", "underflow", "operand"]):
                        matched = True
                    elif "err" in b_kw and any(k in feat_text for k in ["error", "illegal", "fault", "reset"]):
                        matched = True

                    if matched:
                        assigned_holes.add(ub_id)
                        hole_dict = {
                            "feature_id": feat.feature_id,
                            "feature_title": feat.title,
                            "coverpoint": ub.coverpoint_name,
                            "target_signal": ub.metric_type,
                            "bin_name": ub.bin_name,
                            "condition": ub.condition or f"{ub.bin_name} boundary event",
                            "hits": ub.hits,
                        }
                        feat_unhit_bins.append(hole_dict)
                        all_holes.append(hole_dict)
                        break  # 1 hole per feature

            # Compute actual percentage hit per feature, strictly from bins with real
            # simulator evidence (feat_reported_bins). Never invent a percentage for
            # bins/coverpoints we have no simulator data for.
            if feat_reported_bins > 0:
                feat_pct = round((feat_hit_bins / feat_reported_bins) * 100.0, 1)
            else:
                feat_pct = None

            feat.actual_coverage = feat_pct
            feat.unhit_bins = feat_unhit_bins

            # Status determination
            if feat_pct is None:
                feat.coverage_status = "No_Coverage_Data"
            elif feat_pct >= 100.0:
                feat.coverage_status = "Closed"
            elif feat_pct >= 90.0:
                feat.coverage_status = "Near Closure"
            elif feat_pct >= 70.0:
                feat.coverage_status = "In Progress"
            else:
                feat.coverage_status = "Critical Hole"

            # Synthesize directed sequence hint for unhit bins
            if feat_unhit_bins:
                feat.directed_stimulus_hint = self._synthesize_directed_sequence_hint(
                    feat=feat,
                    unhit_bins=feat_unhit_bins,
                    design_name=report.design_name,
                )

        # 3. Update Traceability Matrix rows with actual coverage
        feat_map = {f.feature_id: f for f in report.features}
        for row in report.traceability_matrix:
            f = feat_map.get(row.feature_id)
            if f and f.actual_coverage is not None:
                row.actual_coverage = f.actual_coverage
                row.unhit_bins_count = len(f.unhit_bins)
                if f.actual_coverage >= 100.0:
                    row.status = "Covered"
                elif f.actual_coverage >= 70.0:
                    row.status = "Partial"
                else:
                    row.status = "Uncovered"

        # 4. Update overall report metrics
        report.unhit_bins_count = len(all_holes)
        report.unreported_bins_count = total_unreported_bins
        report.coverage_holes = all_holes
        total_reported_bins = total_planned_bins - total_unreported_bins
        if total_planned_bins > 0:
            report.total_bins = total_planned_bins
            report.hit_bins = total_hit_bins
        else:
            report.total_bins = coverage_db.total_bins
            report.hit_bins = coverage_db.hit_bins

        if coverage_db.overall_coverage_pct is not None:
            report.actual_coverage_overall = coverage_db.overall_coverage_pct
        elif total_reported_bins > 0:
            report.actual_coverage_overall = round((total_hit_bins / total_reported_bins) * 100.0, 1)
        else:
            # No bin in the plan has any corroborating simulator evidence — do not
            # fabricate an overall percentage.
            report.actual_coverage_overall = None

        if total_unreported_bins > 0:
            logger.info(
                f"{total_unreported_bins} planned bin(s) had no matching entry in the "
                f"ingested simulator coverage DB and are reported as Not_Reported, not "
                f"assumed covered."
            )

        logger.info(
            f"Coverage Closure Correlated: {report.actual_coverage_overall}% hit "
            f"({report.hit_bins}/{report.total_bins} bins, {report.unhit_bins_count} unhit holes)"
        )
        return report

    def _synthesize_directed_sequence_hint(
        self,
        feat: FeatureItem,
        unhit_bins: List[Dict[str, Any]],
        design_name: str,
    ) -> str:
        """Synthesize directed SystemVerilog UVM sequence code targeting unhit bins."""
        safe_feat_id = feat.feature_id.lower().replace("-", "_")
        seq_class = f"{design_name.lower()}_{safe_feat_id}_directed_closure_seq"

        bin_comments = "\n".join([
            f"    // Hole #{i+1}: bin `{b['bin_name']}` in `{b['coverpoint']}` => Target Condition: {b['condition']}"
            for i, b in enumerate(unhit_bins)
        ])

        # Synthesize targeted stimulus
        stimulus_steps = []
        for i, b in enumerate(unhit_bins[:5]):
            b_name = b['bin_name']
            cond = b['condition']
            sig = b.get('target_signal', 'data_in')

            stimulus_steps.append(f"""
        // Directed Stimulus for {b_name} ({cond})
        `uvm_info(get_type_name(), "Executing directed stimulus for unhit bin: {b_name}", UVM_LOW)
        `uvm_create(req)
        start_item(req);
        // Constrain transaction fields specifically to trigger: {cond}
        if (!req.randomize() with {{
            // Target condition: {cond}
        }}) begin
            `uvm_error(get_type_name(), "Randomization failed for {b_name}")
        end
        finish_item(req);
        #20ns; // allow pipeline settle and sampling""")

        steps_code = "".join(stimulus_steps)

        deficit_str = (
            f"{round(100.0 - feat.actual_coverage, 1)}%"
            if feat.actual_coverage is not None
            else "Unknown (no simulator evidence for this feature's coverpoints)"
        )
        code = f"""// ==============================================================================
// VeriSight AI Directed Coverage Closure Sequence
// Target Feature: {feat.feature_id} — {feat.title}
// Remaining Deficit: {deficit_str} Unhit Bins
// ==============================================================================
{bin_comments}

class {seq_class} extends uvm_sequence #(uvm_sequence_item);
    `uvm_object_utils({seq_class})

    function new(string name = "{seq_class}");
        super.new(name);
    endfunction

    virtual task body();
        `uvm_info(get_type_name(), "Starting AI Directed Sequence to close {len(unhit_bins)} coverage hole(s)...", UVM_MEDIUM)
{steps_code}

        `uvm_info(get_type_name(), "Directed stimulus complete. Sampling coverage database...", UVM_MEDIUM)
    endtask
endclass
"""
        return code

    def _norm(self, s: Optional[str]) -> str:
        """Normalize identifier for robust matching, stripping hierarchical scopes."""
        if not s:
            return ""
        # Strip path or instance hierarchy e.g. /tb/dut_inst/cp_op or tb.dut.cp_op
        leaf = s.strip().split(".")[-1].split("/")[-1]
        return re.sub(r"[^a-zA-Z0-9]", "", leaf).lower()

