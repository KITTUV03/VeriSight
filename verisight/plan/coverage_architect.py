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


STOP_WORDS = {
    "the", "a", "an", "all", "each", "every", "when", "if", "and", "or",
    "for", "in", "to", "of", "with", "is", "shall", "must", "should", "will"
}


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

    def execute(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
        rtl_info: Optional[Dict[str, Any]] = None,
    ) -> List[CovergroupDef]:
        """Execute coverage model design."""
        return self.design_coverage_model(features, design_name, rtl_info)

    def design_coverage_model(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
        rtl_info: Optional[Dict[str, Any]] = None,
    ) -> List[CovergroupDef]:
        """
        Design covergroups and coverage points mapped to features.

        Args:
            features: List of extracted FeatureItems.
            design_name: Name of the design under test.
            rtl_info: Optional RTL port, signal, and type metadata.

        Returns:
            List of CovergroupDef objects.
        """
        logger.info(f"Designing functional coverage model for {design_name} across {len(features)} features...")

        # Chunk features into batches of up to 15 to avoid LLM context window limits
        chunk_size = 15
        feature_chunks = [features[i:i + chunk_size] for i in range(0, len(features), chunk_size)]
        all_covergroups: List[CovergroupDef] = []

        rtl_summary = ""
        if rtl_info and "ports" in rtl_info:
            ports_desc = [f"{p.get('name', '')} ({p.get('dir', '')} [{p.get('width', 1)}])" for p in rtl_info["ports"]]
            rtl_summary = f"RTL Ports: {', '.join(ports_desc)}"

        use_llm = True
        for chunk_idx, chunk in enumerate(feature_chunks):
            if not use_llm:
                break
            feature_summary = "\n".join(
                [f"- [{f.feature_id}] {f.title} ({f.category}): {f.description}" for f in chunk]
            )

            prompt = f"""Design a complete SystemVerilog Functional Coverage model for {design_name} (Batch {chunk_idx+1}/{len(feature_chunks)}).

═══ RTL SIGNALS (Ground coverpoints to these names) ═══
{rtl_summary or "Inferred from spec"}

═══ FEATURES TO COVER ═══
{feature_summary}

Requirements:
1. Define covergroups for operations, operand ranges, control flags, and error states.
2. Ground all target_signals to actual RTL port/signal names when available.
3. For 1-bit flags (e.g. carry, zero, overflow, ready, valid), create binary bins {{1'b0}} and {{1'b1}}.
4. For multi-bit buses, create nominal, zero, boundary max, and corner bins.
5. Include cross coverage (e.g. opcode crossed with operands, flags crossed with status).
6. Map each coverage point to corresponding Feature IDs.
7. Return a JSON object with a single "covergroups" list:
- group_name (e.g. cg_{design_name.lower()}_ops)
- sample_trigger (e.g. "@(posedge clk iff !rst_n)")
- description (verification scope)
- crosses (list of cross strings e.g. ["cross cp_opcode, cp_carry"])
- coverpoints (list of objects with: coverage_id, feature_ids, name, target_signal, sample_event, description, bins)
"""
            try:
                raw_response = self.reason(prompt=prompt, system_prompt=SYSTEM_PROMPT)
                json_str = self._extract_json(raw_response)
                parsed_json = json.loads(json_str) if json_str else {}

                cg_data = parsed_json.get("covergroups", [])
                for cg in cg_data:
                    all_covergroups.append(CovergroupDef(**cg))
            except Exception as e:
                logger.warning(f"LLM coverage design batch {chunk_idx+1} failed ({e}). Switching to deterministic generator.")
                use_llm = False
                break

        if all_covergroups:
            logger.info(f"Successfully generated {len(all_covergroups)} covergroups via LLM.")
            return self._ground_coverpoints_to_rtl(all_covergroups, rtl_info)

        return self._deterministic_generate(features, design_name, rtl_info)

    def _ground_coverpoints_to_rtl(
        self, covergroups: List[CovergroupDef], rtl_info: Optional[Dict[str, Any]]
    ) -> List[CovergroupDef]:
        """Post-process and ground coverpoint target signals to actual RTL port identifiers."""
        if not rtl_info or "ports" not in rtl_info or not rtl_info["ports"]:
            return covergroups

        port_names = [p["name"] for p in rtl_info["ports"] if p["name"] not in ("clk", "rst_n", "rst")]
        if not port_names:
            return covergroups
        port_map = {p["name"].lower(): p["name"] for p in rtl_info["ports"]}

        for cg in covergroups:
            for cp in cg.coverpoints:
                sig_low = cp.target_signal.lower()
                if sig_low in port_map:
                    cp.target_signal = port_map[sig_low]
                else:
                    # Search context text for closest matching RTL port
                    context = f"{cp.target_signal} {cp.name} {cp.description}".lower()
                    matched = None
                    for p in port_names:
                        if p.lower() in context:
                            matched = p
                            break
                    if not matched:
                        if any(k in context for k in ["op", "opcode", "sel", "cmd", "mode"]):
                            matched = next((p for p in port_names if "op" in p.lower() or "sel" in p.lower()), None)
                        elif any(k in context for k in ["carry", "overflow"]):
                            matched = next((p for p in port_names if "carry" in p.lower() or "ovf" in p.lower()), None)
                        elif any(k in context for k in ["zero"]):
                            matched = next((p for p in port_names if "zero" in p.lower()), None)
                        elif any(k in context for k in ["result", "out", "data_o"]):
                            matched = next((p for p in port_names if "result" in p.lower() or "out" in p.lower()), None)
                        elif any(k in context for k in ["operand", "in", "data_i", "a", "b"]):
                            matched = next((p for p in port_names if "a" in p.lower() or "in" in p.lower()), port_names[0])
                    if matched:
                        cp.target_signal = matched

        return covergroups

    def generate_sv_code(self, covergroups: List[CovergroupDef], design_name: str = "dut") -> str:
        """
        Generate standalone SystemVerilog functional coverage code (.sv).
        Uses valid SystemVerilog covergroup syntax compatible with Slang/pyslang.
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
            
            # Valid SystemVerilog trigger syntax
            trigger = cg.sample_trigger.strip() if cg.sample_trigger else ""
            if trigger.startswith("@"):
                lines.append(f"    covergroup {cg_id} {trigger};")
            else:
                lines.append(f"    covergroup {cg_id};")

            lines.append(f"      option.per_instance = 1;")
            lines.append(f"      option.name = \"{cg_id}\";")
            lines.append("")

            seen_cp_names = set()
            for cp in cg.coverpoints:
                cp_id = _sanitize_sv_id(cp.name)
                # Ensure unique coverpoint names
                if cp_id in seen_cp_names:
                    cp_id = f"{cp_id}_{_sanitize_sv_id(cp.coverage_id)}"
                seen_cp_names.add(cp_id)

                sig_id = _sanitize_sv_id(cp.target_signal)
                lines.append(f"      // [{cp.coverage_id}] {cp.description}")
                lines.append(f"      {cp_id}: coverpoint {sig_id} {{")
                if cp.bins:
                    seen_bins = set()
                    for b in cp.bins:
                        b_id = _sanitize_sv_id(b.bin_name)
                        if b_id in seen_bins:
                            b_id = f"{b_id}_{len(seen_bins)}"
                        seen_bins.add(b_id)
                        desc = f" // {b.description}" if b.description else ""
                        lines.append(f"        {b.bin_type} {b_id} = {b.condition};{desc}")
                else:
                    lines.append(f"        bins all_values[] = default;")
                lines.append(f"      }}")
                lines.append("")

            for cr in cg.crosses:
                cleaned_cr = cr.strip().rstrip(";")
                lines.append(f"      {cleaned_cr};")

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
        self,
        features: List[FeatureItem],
        design_name: str,
        rtl_info: Optional[Dict[str, Any]] = None,
    ) -> List[CovergroupDef]:
        """Deterministic, grounded functional coverage model generator."""
        cps: List[CoveragePoint] = []
        cov_idx = 1
        seen_cp_names = set()

        # Build port lookup from rtl_info if available
        ports_dict = {}
        if rtl_info and "ports" in rtl_info:
            for p in rtl_info["ports"]:
                p_name = p.get("name", "").lower()
                ports_dict[p_name] = p

        # 1. First, create grounded coverpoints for all known RTL ports
        for p_name, p in ports_dict.items():
            if p_name in ("clk", "rst_n", "rst", "clock", "reset"):
                continue

            width = _parse_width(p.get("width", 1))
            safe_port = _sanitize_sv_id(p_name)
            cp_name = f"cp_{safe_port}"
            seen_cp_names.add(cp_name)

            # Match port to relevant feature IDs
            matched_fids = [f.feature_id for f in features if p_name in f.title.lower() or p_name in f.description.lower()]
            if not matched_fids:
                matched_fids = [features[0].feature_id] if features else ["FEAT-001"]

            bins = []
            if width == 1:
                bins = [
                    CoverageBin(bin_name="deasserted", bin_type="bins", condition="{1'b0}", description="Deasserted 0"),
                    CoverageBin(bin_name="asserted", bin_type="bins", condition="{1'b1}", description="Asserted 1"),
                    CoverageBin(bin_name="trans_01", bin_type="bins", condition="(1'b0 => 1'b1)", description="Transition 0 to 1"),
                    CoverageBin(bin_name="trans_10", bin_type="bins", condition="(1'b1 => 1'b0)", description="Transition 1 to 0"),
                ]
            elif width <= 4:
                # Small control/opcode bus
                max_v = (1 << width) - 1
                bins = [
                    CoverageBin(bin_name="all_values", bin_type="bins", condition=f"{{[0:{max_v}]}}", description="All valid encodings"),
                    CoverageBin(bin_name="zero_val", bin_type="bins", condition="{0}", description="Zero encoding"),
                    CoverageBin(bin_name="max_val", bin_type="bins", condition=f"{{{max_v}}}", description="Max encoding"),
                ]
            else:
                # Multi-bit data bus
                max_v = (1 << width) - 1
                mid_max = max(1, max_v - 1)
                bins = [
                    CoverageBin(bin_name="zero", bin_type="bins", condition="{0}", description="Zero boundary"),
                    CoverageBin(bin_name="nominal", bin_type="bins", condition=f"{{[1:{mid_max}]}}", description="Nominal data range"),
                    CoverageBin(bin_name="all_ones", bin_type="bins", condition=f"{{{max_v}}}", description="All ones boundary"),
                ]

            cps.append(
                CoveragePoint(
                    coverage_id=f"COV-{cov_idx:03d}",
                    feature_ids=matched_fids,
                    name=cp_name,
                    target_signal=safe_port,
                    sample_event="@(posedge clk)",
                    bins=bins,
                    description=f"Functional coverage for port '{safe_port}' [{width}-bit]",
                )
            )
            cov_idx += 1

        # 2. Add coverage points for any features not directly tied to a port
        for feat in features:
            f_text = f"{feat.title} {feat.description}".lower()
            # If feature was already mapped to a port coverpoint, continue
            if any(feat.feature_id in cp.feature_ids for cp in cps):
                continue

            # Synthesize clean, non-stopword identifier
            words = [w for w in re.findall(r"[a-zA-Z0-9]+", feat.title.lower()) if w not in STOP_WORDS and len(w) > 1]
            core_name = "_".join(words[:3]) if words else f"feat_{feat.feature_id.lower().replace('-', '_')}"
            safe_sig = _sanitize_sv_id(core_name)[:20]
            cp_name = f"cp_{safe_sig}"
            if cp_name in seen_cp_names:
                cp_name = f"{cp_name}_{cov_idx}"
            seen_cp_names.add(cp_name)

            # Determine appropriate bins
            if any(k in f_text for k in ["flag", "carry", "zero", "overflow", "negative", "enable", "valid", "ready", "error"]):
                bins = [
                    CoverageBin(bin_name="deasserted", bin_type="bins", condition="{1'b0}", description="Flag inactive"),
                    CoverageBin(bin_name="asserted", bin_type="bins", condition="{1'b1}", description="Flag active"),
                ]
            elif any(k in f_text for k in ["opcode", "operation", "mode", "state", "command"]):
                bins = [
                    CoverageBin(bin_name="op_nominal", bin_type="bins", condition="{[0:7]}", description="Standard modes"),
                    CoverageBin(bin_name="op_special", bin_type="bins", condition="{8}", description="Corner mode"),
                ]
            else:
                bins = [
                    CoverageBin(bin_name="nominal_values", bin_type="bins", condition="{[1:254]}", description="Normal range"),
                    CoverageBin(bin_name="boundary_min", bin_type="bins", condition="{0}", description="Minimum bound"),
                    CoverageBin(bin_name="boundary_max", bin_type="bins", condition="{255}", description="Ceiling bound"),
                ]

            cps.append(
                CoveragePoint(
                    coverage_id=f"COV-{cov_idx:03d}",
                    feature_ids=[feat.feature_id],
                    name=cp_name,
                    target_signal=safe_sig,
                    sample_event="@(posedge clk)",
                    bins=bins,
                    description=f"Measure coverage for: {feat.title}",
                )
            )
            cov_idx += 1

        # 3. Create cross coverage if multiple complementary coverpoints exist
        crosses = []
        cp_names = [cp.name for cp in cps]
        op_cps = [n for n in cp_names if any(k in n for k in ["op", "cmd", "mode"])]
        flag_cps = [n for n in cp_names if any(k in n for k in ["carry", "zero", "overflow", "flag", "err"])]

        for op_cp in op_cps[:2]:
            for flag_cp in flag_cps[:2]:
                crosses.append(f"cross_{op_cp}_x_{flag_cp}: cross {op_cp}, {flag_cp}")

        return [
            CovergroupDef(
                group_name=f"cg_{design_name.lower()}_main",
                sample_trigger="@(posedge clk iff !rst_n)",
                description=f"Grounded functional coverage model for {design_name}",
                coverpoints=cps,
                crosses=crosses,
            )
        ]

