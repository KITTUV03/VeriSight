"""
SVA Assertion Architect for VeriSight Plan.

Generates formal SystemVerilog Assertions (SVA) plans and synthesizable/simulatable
assertion bind modules (`property`, `assert property`, `cover property`).
"""

import re
import json
from typing import List, Optional, Dict, Any

from verisight.agents.base_agent import BaseAgent
from verisight.plan.schemas import FeatureItem, SVAProperty
from verisight.utils.logger import get_logger

logger = get_logger("plan.assertion_architect")

SYSTEM_PROMPT = """You are a Principal Formal and Dynamic Verification Engineer specializing in SystemVerilog Assertions (SVA).
Your job is to formulate a comprehensive SVA Assertion Plan and generate production-grade SystemVerilog assertion properties.

CRITICAL RULES:
1. Generate concurrent assertions with clocking and disable conditions:
   - Example: property p_name; @(posedge clk) disable iff (!rst_n) req |-> ##[1:2] ack; endproperty
2. Check for:
   - Reset behavior (all outputs must reach default values on reset)
   - Protocol handshakes (valid/ready, request/grant)
   - Arithmetic bounds and overflow flags
   - FIFO safety (no write when full, no read when empty)
   - Mutual exclusion (one-hot flags, exclusive grant)
3. Include both `assert property` (safety) and `cover property` (liveness/reachability).
4. Map every assertion to one or more Feature IDs (feature_ids: ["FEAT-001", ...]).
5. Return a valid JSON object matching the requested schema.
"""


STOP_WORDS = {
    "the", "a", "an", "all", "each", "every", "when", "if", "and", "or",
    "for", "in", "to", "of", "with", "is", "shall", "must", "should", "will"
}

SV_KEYWORDS = {
    "clk", "rst_n", "rst", "posedge", "negedge", "disable", "iff", "property",
    "endproperty", "assert", "cover", "assume", "default", "clocking", "endclocking",
    "input", "output", "inout", "logic", "wire", "reg", "module", "endmodule",
    "begin", "end", "isunknown", "past", "stable", "rose", "fell", "onehot",
    "onehot0", "countones", "inside", "dist", "always", "initial", "case", "endcase"
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
        cleaned = "prop"
    if cleaned[0].isdigit():
        cleaned = f"prop_{cleaned}"
    return cleaned


class AssertionArchitect(BaseAgent):
    """Designs formal SVA properties and generates SystemVerilog assertion modules."""

    def __init__(self):
        super().__init__("assertion_architect")

    def execute(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
        rtl_info: Optional[Dict[str, Any]] = None,
        spec_text: str = "",
    ) -> List[SVAProperty]:
        """Execute SVA assertion design."""
        return self.design_assertions(features, design_name, rtl_info, spec_text)

    def design_assertions(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
        rtl_info: Optional[Dict[str, Any]] = None,
        spec_text: str = "",
    ) -> List[SVAProperty]:
        """
        Design SVA assertion properties mapped to features.

        Args:
            features: List of extracted FeatureItems.
            design_name: Name of the design under test.
            rtl_info: Optional RTL port, signal, and type metadata.
            spec_text: Raw specification text for protocol invariant extraction.

        Returns:
            List of SVAProperty objects.
        """
        logger.info(f"Designing SVA assertions for {design_name} across {len(features)} features...")

        # Chunk features into batches of up to 15 to prevent context truncation
        chunk_size = 15
        feature_chunks = [features[i:i + chunk_size] for i in range(0, len(features), chunk_size)]
        all_assertions: List[SVAProperty] = []

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

            prompt = f"""Design a suite of SystemVerilog Assertions (SVA) for {design_name} (Batch {chunk_idx+1}/{len(feature_chunks)}).

═══ RTL SIGNALS (Ground assertion signals to these names) ═══
{rtl_summary or "Inferred from spec"}

═══ FEATURE REQUIREMENTS ═══
{feature_summary}

Requirements:
1. Create temporal assertions covering reset initialization, data stability, protocol handshakes, and flag correctness.
2. Ground expressions in actual RTL signals: do NOT invent non-existent signal names.
3. Formulate proper SVA syntax with clocking events and disable iff conditions.
4. Include meaningful failure error messages for simulation logging.
5. Map each assertion to relevant Feature IDs.

Return a JSON object with a single "assertions" list of objects with fields:
- assertion_id (e.g. SVA-001, SVA-002, ...)
- feature_ids (list of string IDs)
- name (property name e.g. prop_reset_clears_outputs)
- property_type ("assert" | "cover" | "assume")
- clock_expr (e.g. "posedge clk")
- disable_expr (e.g. "!rst_n" or "rst")
- expression (SVA property logic e.g. "req |-> ##1 ack")
- failure_message (error message on violation)
- description (verification intent)
"""
            try:
                raw_response = self.reason(prompt=prompt, system_prompt=SYSTEM_PROMPT)
                json_str = self._extract_json(raw_response)
                parsed_json = json.loads(json_str) if json_str else {}

                prop_data = parsed_json.get("assertions", [])
                for p in prop_data:
                    all_assertions.append(SVAProperty(**p))
            except Exception as e:
                logger.warning(f"LLM assertion design batch {chunk_idx+1} failed ({e}). Switching to deterministic generator.")
                use_llm = False
                break

        if all_assertions:
            logger.info(f"Successfully generated {len(all_assertions)} SVA properties via LLM.")
            return all_assertions

        return self._deterministic_generate(features, design_name, rtl_info, spec_text)

    def generate_sv_code(
        self,
        assertions: List[SVAProperty],
        design_name: str = "dut",
        rtl_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate standalone SystemVerilog assertion bind module (.sv).
        Declares all ports needed by properties so Slang/pyslang compiles without errors.
        """
        # Determine port declarations for the assertion module
        port_decls: List[str] = [
            "  input logic clk",
            "  input logic rst_n",
        ]
        declared_signals = {"clk", "rst_n"}

        if rtl_info and "ports" in rtl_info:
            for p in rtl_info["ports"]:
                p_name = p.get("name", "").lower()
                if p_name in declared_signals:
                    continue
                width = _parse_width(p.get("width", 1))
                width_prefix = f"[{width-1}:0] " if width > 1 else ""
                port_decls.append(f"  input logic {width_prefix}{p_name}")
                declared_signals.add(p_name)

        # In addition, extract identifier tokens from property expressions to avoid undeclared identifiers
        for sva in assertions:
            full_expr = f"{sva.expression} {sva.disable_expr or ''} {sva.clock_expr or ''}"
            # Strip SV based literals (e.g. 32'h10, 1'b1), strings ("..."), and system functions ($error, $stable)
            clean_expr = re.sub(r"\d*'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ]+", " ", full_expr)
            clean_expr = re.sub(r'"[^"]*"', " ", clean_expr)
            clean_expr = re.sub(r'\$[a-zA-Z0-9_]+', " ", clean_expr)
            tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", clean_expr)
            for t in tokens:
                t_low = t.lower()
                if t_low not in declared_signals and t_low not in SV_KEYWORDS and not t.isdigit():
                    port_decls.append(f"  input logic [31:0] {t}")
                    declared_signals.add(t_low)

        ports_block = ",\n".join(port_decls)

        lines = [
            f"// ===========================================================================",
            f"// VeriSight Plan — SystemVerilog Assertion (SVA) Suite",
            f"// Target: {design_name}",
            f"// Automatically generated by VeriSight Plan Architect",
            f"// ===========================================================================",
            f"`ifndef {design_name.upper()}_ASSERTIONS_SV",
            f"`define {design_name.upper()}_ASSERTIONS_SV",
            "",
            f"module {design_name.lower()}_assertions (",
            ports_block,
            f");",
            "",
            f"  // Default clocking block",
            f"  default clocking cb @(posedge clk);",
            f"  endclocking",
            "",
        ]

        seen_prop_names = set()
        for sva in assertions:
            safe_prop_name = _sanitize_sv_id(sva.name)
            if safe_prop_name in seen_prop_names:
                safe_prop_name = f"{safe_prop_name}_{_sanitize_sv_id(sva.assertion_id)}"
            seen_prop_names.add(safe_prop_name)

            lines.append(f"  // [{sva.assertion_id}] {sva.description}")
            dis_clause = f" disable iff ({sva.disable_expr})" if sva.disable_expr else ""
            lines.append(f"  property {safe_prop_name};")
            lines.append(f"    @({sva.clock_expr}){dis_clause}")
            expr = sva.expression.strip().rstrip(";")
            lines.append(f"      {expr};")
            lines.append(f"  endproperty : {safe_prop_name}")
            lines.append("")

            if sva.property_type == "assert":
                lines.append(
                    f"  {safe_prop_name}_check: assert property ({safe_prop_name})\n"
                    f"    else $error(\"[{sva.assertion_id} VIOLATION] {sva.failure_message}\");"
                )
            elif sva.property_type == "cover":
                lines.append(f"  {safe_prop_name}_cov: cover property ({safe_prop_name});")
            elif sva.property_type == "assume":
                lines.append(f"  {safe_prop_name}_asm: assume property ({safe_prop_name});")

            lines.append("")

        lines.extend([
            f"endmodule : {design_name.lower()}_assertions",
            "",
            f"// Bind directive example for verification integration:",
            f"// bind {design_name} {design_name.lower()}_assertions sva_inst (.*);",
            "",
            f"`endif // {design_name.upper()}_ASSERTIONS_SV",
            "",
        ])

        return "\n".join(lines)

    def _deterministic_generate(
        self,
        features: List[FeatureItem],
        design_name: str,
        rtl_info: Optional[Dict[str, Any]] = None,
        spec_text: str = "",
    ) -> List[SVAProperty]:
        """
        Deterministic, protocol-aware SVA property generator.
        Delegates to ProtocolArchitect for PCIe, CHI, DDR, AXI, or strictly-grounded custom RTL.
        """
        logger.info(f"Using ProtocolArchitect to synthesize grounded SVA properties for {design_name}...")
        from verisight.plan.protocol_architect import generate_grounded_protocol_plan
        _, sva, _ = generate_grounded_protocol_plan(
            design_name=design_name,
            features=features,
            rtl_info=rtl_info,
            spec_text=spec_text,
        )
        return sva

