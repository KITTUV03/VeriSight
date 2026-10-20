"""
Functional Coverage Architect for VeriSight Plan.

Produces functional coverage plans and generates real, synthesizable/simulatable
SystemVerilog functional coverage code (`covergroup`, `coverpoint`, `cross`, `bins`).
"""

import re
import json
from typing import List, Optional, Dict, Any

from verisight.agents.base_agent import BaseAgent
from verisight.plan.schemas import FeatureItem, CovergroupDef, CoveragePoint, CoverageBin
from verisight.utils.logger import get_logger

logger = get_logger("plan.coverage_architect")

SYSTEM_PROMPT = """You are a Principal Verification Architect specializing in SystemVerilog Functional Coverage.
Your job is to design comprehensive Covergroups and generate ready-to-compile SystemVerilog coverage code.

CRITICAL RULES:
1. Cover every major feature with specific coverpoints and cross coverage.
2. Group coverage into clean SystemVerilog `covergroup` definitions.
3. Include standard bins:
   - Nominal value bins
   - Corner/boundary bins (min, max, zero)
   - Transition bins (e.g. 0 => 1, 1 => 0, consecutive states)
   - illegal_bins / ignore_bins
4. Map every coverage item to one or more Feature IDs (e.g. feature_ids: ["FEAT-001"]).
5. Generate valid SystemVerilog code that can be embedded into a UVM subscriber or testbench.
6. Return a valid JSON object matching the requested schema.
"""


def _sanitize_sv_id(s: str) -> str:
    """Sanitize any arbitrary string into a valid SystemVerilog identifier."""
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', s).strip('_')
    if not cleaned:
        cleaned = "sig"
    if cleaned[0].isdigit():
        cleaned = f"sig_{cleaned}"
    return cleaned


class CoverageArchitect(BaseAgent):
    """Designs functional coverage models and generates SystemVerilog covergroups."""

    def __init__(self):
        super().__init__("coverage_architect")

    def execute(self, features: List[FeatureItem], design_name: str = "DUT") -> List[CovergroupDef]:
        """Execute coverage model design."""
        return self.design_coverage_model(features, design_name)

    def design_coverage_model(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
    ) -> List[CovergroupDef]:
        """
        Design covergroups and coverage points mapped to features.

        Args:
            features: List of extracted FeatureItems.
            design_name: Name of the design under test.

        Returns:
            List of CovergroupDef objects.
        """
        logger.info(f"Designing functional coverage model for {design_name}...")

        feature_summary = "\n".join(
            [f"- [{f.feature_id}] {f.title} ({f.category}): {f.description}" for f in features[:12]]
        )

        prompt = f"""Design a complete SystemVerilog Functional Coverage model for {design_name}.

═══ KEY FEATURES ═══
{feature_summary}

Requirements:
1. Define covergroups for operations, operand ranges, control flags, and error states.
2. Include boundary bins (0, 1, max, sign change).
3. Include cross coverage (e.g. opcode crossed with operands, flags crossed with status).
4. Map each coverage point to the corresponding Feature IDs.
5. All coverpoint names and signal names must be valid SystemVerilog identifiers (alphanumeric and underscore, no hyphens, do not start with digits).

Return a JSON object with a single "covergroups" list:
- group_name (e.g. cg_{design_name.lower()}_ops)
- sample_trigger (e.g. "@(posedge clk iff !rst_n)")
- description (verification scope)
- crosses (list of cross strings e.g. ["cross cp_opcode, cp_carry"])
- coverpoints (list of objects with fields:
    - coverage_id (e.g. COV-001)
    - feature_ids (list of string IDs)
    - name (e.g. cp_opcode)
    - target_signal (e.g. opcode)
    - sample_event (e.g. "@(posedge clk)")
    - description (verification intent)
    - bins (list of objects with: bin_name, bin_type ("bins"|"illegal_bins"|"ignore_bins"), condition, description)
)
"""

        try:
            raw_response = self.reason(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            json_str = self._extract_json(raw_response)
            parsed_json = json.loads(json_str) if json_str else {}

            cg_data = parsed_json.get("covergroups", [])
            covergroups = []
            for cg in cg_data:
                covergroups.append(CovergroupDef(**cg))

            if covergroups:
                logger.info(f"Successfully generated {len(covergroups)} covergroups via LLM.")
                return covergroups
        except Exception as e:
            logger.warning(f"LLM coverage design failed or offline ({e}). Using deterministic generator.")

        return self._deterministic_generate(features, design_name)

    def generate_sv_code(self, covergroups: List[CovergroupDef], design_name: str = "dut") -> str:
        """
        Generate standalone SystemVerilog functional coverage code (.sv).
        """
        lines = [
            f"// ===========================================================================",
            f"// VeriSight Plan — Autonomous Functional Coverage Model",
            f"// Target: {design_name}",
            f"// Automatically generated by VeriSight Plan Architect",
            f"// ===========================================================================",
            f"`ifndef {design_name.upper()}_COVERAGE_SV",
            f"`define {design_name.upper()}_COVERAGE_SV",
            "",
            f"package {design_name.lower()}_coverage_pkg;",
            f"  import uvm_pkg::*;",
            f"  `include \"uvm_macros.svh\"",
            "",
            f"  class {design_name.lower()}_coverage_subscriber extends uvm_subscriber;",
            f"    `uvm_component_utils({design_name.lower()}_coverage_subscriber)",
            "",
        ]

        # Add covergroups
        for cg in covergroups:
            cg_id = _sanitize_sv_id(cg.group_name)
            lines.append(f"    // Covergroup: {cg_id}")
            lines.append(f"    // {cg.description}")
            lines.append(f"    covergroup {cg_id} with function sample({cg.sample_trigger});")
            lines.append(f"      option.per_instance = 1;")
            lines.append(f"      option.name = \"{cg_id}\";")
            lines.append("")

            for cp in cg.coverpoints:
                cp_id = _sanitize_sv_id(cp.name)
                sig_id = _sanitize_sv_id(cp.target_signal)
                lines.append(f"      // [{cp.coverage_id}] {cp.description}")
                lines.append(f"      {cp_id}: coverpoint {sig_id} {{")
                if cp.bins:
                    for b in cp.bins:
                        b_id = _sanitize_sv_id(b.bin_name)
                        desc = f" // {b.description}" if b.description else ""
                        lines.append(f"        {b.bin_type} {b_id} = {b.condition};{desc}")
                else:
                    lines.append(f"        bins all_values[] = default;")
                lines.append(f"      }}")
                lines.append("")

            for cr in cg.crosses:
                lines.append(f"      {cr};")

            lines.append(f"    endgroup : {cg_id}")
            lines.append("")

        # Constructor
        lines.extend([
            f"    function new(string name = \"{design_name.lower()}_coverage_subscriber\", uvm_component parent = null);",
            f"      super.new(name, parent);",
        ])
        for cg in covergroups:
            cg_id = _sanitize_sv_id(cg.group_name)
            lines.append(f"      {cg_id} = new();")
        lines.extend([
            f"    endfunction : new",
            "",
            f"    virtual function void write(uvm_sequence_item t);",
            f"      // Sample covergroups on transaction arrival",
        ])
        for cg in covergroups:
            cg_id = _sanitize_sv_id(cg.group_name)
            lines.append(f"      {cg_id}.sample();")
        lines.extend([
            f"    endfunction : write",
            f"  endclass : {design_name.lower()}_coverage_subscriber",
            f"endpackage : {design_name.lower()}_coverage_pkg",
            f"`endif // {design_name.upper()}_COVERAGE_SV",
            "",
        ])

        return "\n".join(lines)

    def _deterministic_generate(
        self, features: List[FeatureItem], design_name: str
    ) -> List[CovergroupDef]:
        """Deterministic fallback coverage model generator."""
        cps = []
        cov_idx = 1

        for feat in features:
            safe_name = _sanitize_sv_id(feat.title)[:24]
            first_word = feat.title.split()[0] if feat.title.split() else "sig"
            safe_sig = _sanitize_sv_id(first_word)[:16]
            cps.append(
                CoveragePoint(
                    coverage_id=f"COV-{cov_idx:03d}",
                    feature_ids=[feat.feature_id],
                    name=f"cp_{safe_name}",
                    target_signal=safe_sig,
                    sample_event="@(posedge clk)",
                    bins=[
                        CoverageBin(bin_name="nominal_values", bin_type="bins", condition="{[1:254]}", description="Normal range"),
                        CoverageBin(bin_name="boundary_min", bin_type="bins", condition="{0}", description="Minimum zero bound"),
                        CoverageBin(bin_name="boundary_max", bin_type="bins", condition="{255}", description="Maximum ceiling bound"),
                    ],
                    description=f"Measure functional coverage for {feat.title}",
                )
            )
            cov_idx += 1

        return [
            CovergroupDef(
                group_name=f"cg_{design_name.lower()}_main",
                sample_trigger="@(posedge clk iff !rst_n)",
                description=f"Main functional coverage group for {design_name}",
                coverpoints=cps,
                crosses=[],
            )
        ]
