"""
Feature Extractor for VeriSight Plan.

Decomposes design specifications into formal functional features, register definitions,
modes, and interface requirements. Optionally cross-checks against RTL AST to identify
missing spec items or undocumented RTL features.
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from verisight.agents.base_agent import BaseAgent
from verisight.parsers.spec_parser import parse_spec
from verisight.parsers.rtl_parser import parse_rtl
from verisight.plan.schemas import FeatureItem
from verisight.utils.logger import get_logger

logger = get_logger("plan.feature_extractor")

SYSTEM_PROMPT = """You are a Principal ASIC/SoC Verification Architect with 25+ years of industry experience.
Your job is to deconstruct a hardware design specification into a comprehensive, structured Feature Plan.

CRITICAL RULES:
1. Deconstruct the specification into granular, atomic features with unique IDs (e.g. FEAT-001, FEAT-002).
2. Categorize each feature into one of: Functional, Interface, Register, CornerCase, Protocol, Performance.
3. Assign priority: Critical, High, Medium, Low.
4. If RTL details are provided, compare with the spec and indicate rtl_cross_check:
   - "Confirmed": Feature exists in spec and is implemented in RTL.
   - "Missing_In_RTL": Feature described in spec but missing in RTL.
   - "Undocumented_In_Spec": Feature found in RTL but absent from spec.
5. Cover normal operating modes, reset behavior, arithmetic/logic operations, overflow/underflow, flags, and error conditions.
6. Return a valid JSON object matching the requested schema.
"""


class FeatureExtractor(BaseAgent):
    """Decomposes specifications and cross-checks RTL to produce Feature Items."""

    def __init__(self):
        super().__init__("feature_extractor")

    def execute(self, spec_text: str, spec_path: str, rtl_path: Optional[str] = None) -> List[FeatureItem]:
        """Execute feature extraction."""
        return self.extract_features(spec_text, spec_path, rtl_path)

    def extract_features(
        self,
        spec_text: str,
        spec_path: str,
        rtl_path: Optional[str] = None,
    ) -> List[FeatureItem]:
        """
        Extract features from specification and optional RTL.

        Args:
            spec_text: Raw specification document content.
            spec_path: Path to specification file.
            rtl_path: Optional path to RTL file or directory.

        Returns:
            List of FeatureItem objects.
        """
        logger.info(f"Extracting features from specification: {spec_path}")

        rtl_summary = ""
        rtl_data = None
        if rtl_path and Path(rtl_path).exists():
            try:
                rtl_data = parse_rtl(rtl_path)
                modules_desc = []
                for mod in rtl_data.modules:
                    ports = [f"{p.name} ({p.direction} [{p.width}])" for p in mod.ports]
                    fsm_info = [f"{f.name} (states={[s.name for s in f.states]})" for f in mod.fsms]
                    clocks = [cd.clock_signal for cd in mod.clock_domains]
                    resets = [cd.reset_signal for cd in mod.clock_domains if cd.reset_signal]
                    modules_desc.append(
                        f"Module: {mod.name}\n"
                        f"  Ports: {', '.join(ports)}\n"
                        f"  Clocks: {clocks}, Resets: {resets}\n"
                        f"  FSMs: {', '.join(fsm_info) if fsm_info else 'None'}"
                    )
                rtl_summary = "\n".join(modules_desc)
                logger.info(f"Cross-checking with RTL ({len(rtl_data.modules)} modules parsed)")
            except Exception as e:
                logger.warning(f"RTL parsing error during feature extraction: {e}")

        # Increase prompt context window (support full specs up to 80k chars)
        prompt_spec = spec_text if len(spec_text) <= 80000 else spec_text[:80000]

        prompt = f"""Deconstruct the following hardware specification into a complete Feature Plan.

═══ SPECIFICATION DOCUMENT ═══
{prompt_spec}

═══ RTL HARDWARE IMPLEMENTATION (for cross-correlation) ═══
{rtl_summary or "No RTL provided (spec-only extraction)."}

Provide the output as a JSON object with a single "features" list of objects with fields:
- feature_id (e.g. FEAT-001, FEAT-002, ...)
- title (short title)
- description (precise functional description)
- category (Functional | Interface | Register | CornerCase | Protocol | Performance)
- source_section (spec section name/header if available)
- priority (Critical | High | Medium | Low)
- rtl_cross_check (Confirmed | Missing_In_RTL | Undocumented_In_Spec | N/A)
"""

        try:
            raw_response = self.reason(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            json_str = self._extract_json(raw_response)
            parsed_json = json.loads(json_str) if json_str else {}

            features_data = parsed_json.get("features", [])
            features = []
            for item in features_data:
                features.append(FeatureItem(**item))

            if features:
                logger.info(f"Successfully extracted {len(features)} features via LLM.")
                return features
        except Exception as e:
            logger.warning(f"LLM feature extraction failed or offline ({e}). Using deterministic extractor.")

        return self._deterministic_extract(spec_text, rtl_data)

    def _deterministic_extract(self, spec_text: str, rtl_data: Any) -> List[FeatureItem]:
        """Deterministic fallback feature extractor supporting tables, lists, and RTL cross-correlation."""
        features: List[FeatureItem] = []
        feat_idx = 1
        seen_titles = set()

        # Collect RTL port/signal names for cross-check
        rtl_port_names = set()
        if rtl_data and hasattr(rtl_data, "modules"):
            for mod in rtl_data.modules:
                for p in getattr(mod, "ports", []):
                    rtl_port_names.add(p.name.lower())

        lines = spec_text.splitlines()
        current_section = "General"
        in_table = False
        table_headers = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                in_table = False
                continue

            # Header tracking
            if line_str.startswith("#"):
                current_section = line_str.lstrip("#").strip()
                in_table = False
                continue

            # Table row parsing (e.g. | Opcode | Mnemonic | Description |)
            if line_str.startswith("|") and line_str.endswith("|"):
                cells = [c.strip() for c in line_str.strip("|").split("|")]
                if all(set(c) <= {"-", ":", " "} for c in cells):
                    in_table = True
                    continue
                if not in_table:
                    table_headers = [c.lower() for c in cells]
                    in_table = True
                    continue
                else:
                    # Valid data row in table
                    if len(cells) >= 2:
                        title = f"{cells[0]}: {cells[1]}"[:45]
                        desc = " — ".join(cells)
                        if title not in seen_titles and len(desc) > 8:
                            seen_titles.add(title)
                            cat = "Register" if any(k in current_section.lower() or k in title.lower() for k in ["reg", "offset", "csr"]) else "Functional"
                            features.append(
                                FeatureItem(
                                    feature_id=f"FEAT-{feat_idx:03d}",
                                    title=title,
                                    description=desc,
                                    category=cat,
                                    source_section=current_section,
                                    priority="High" if "reset" in desc.lower() or "error" in desc.lower() else "Medium",
                                    rtl_cross_check="Confirmed" if any(p in desc.lower() for p in rtl_port_names) else ("Confirmed" if rtl_data else "N/A"),
                                )
                            )
                            feat_idx += 1
                    continue

            # Bullet points or numbered lists
            is_bullet = line_str.startswith(("- ", "* ", "+ "))
            is_numbered = bool(re.match(r"^\d+\.\s+", line_str))
            has_kv = len(line_str) > 12 and ":" in line_str and not line_str.startswith("//")

            if is_bullet or is_numbered or has_kv:
                text = re.sub(r"^[-*+\d.]+\s*", "", line_str).strip()
                if len(text) > 10:
                    raw_title = text.split(":")[0].strip()[:45] if ":" in text else text[:45]
                    if raw_title in seen_titles:
                        continue
                    seen_titles.add(raw_title)

                    # Categorization heuristics
                    low_text = text.lower()
                    if any(k in low_text for k in ["reset", "power-on", "clock", "pin", "pad"]):
                        cat = "Interface"
                        prio = "Critical"
                    elif any(k in low_text for k in ["reg", "offset", "address", "csr", "read-only", "w1c"]):
                        cat = "Register"
                        prio = "High"
                    elif any(k in low_text for k in ["apb", "ahb", "axi", "handshake", "valid", "ready", "protocol"]):
                        cat = "Protocol"
                        prio = "Critical"
                    elif any(k in low_text for k in ["overflow", "underflow", "illegal", "corner", "error", "fault", "violation"]):
                        cat = "CornerCase"
                        prio = "High"
                    elif any(k in low_text for k in ["latency", "throughput", "bandwidth", "frequency", "performance"]):
                        cat = "Performance"
                        prio = "Medium"
                    else:
                        cat = "Functional"
                        prio = "High" if feat_idx <= 4 else "Medium"

                    # Cross check with RTL ports
                    cross = "N/A"
                    if rtl_port_names:
                        matched = any(p in low_text for p in rtl_port_names)
                        cross = "Confirmed" if matched else "Missing_In_RTL"

                    features.append(
                        FeatureItem(
                            feature_id=f"FEAT-{feat_idx:03d}",
                            title=raw_title,
                            description=text,
                            category=cat,
                            source_section=current_section,
                            priority=prio,
                            rtl_cross_check=cross,
                        )
                    )
                    feat_idx += 1

        # Check for Undocumented RTL features (ports in RTL not present in spec text)
        if rtl_port_names:
            spec_lower = spec_text.lower()
            for port in sorted(rtl_port_names):
                if port not in ("clk", "rst_n", "rst", "clock", "reset") and port not in spec_lower:
                    features.append(
                        FeatureItem(
                            feature_id=f"FEAT-{feat_idx:03d}",
                            title=f"Undocumented RTL Port: {port}",
                            description=f"RTL defines port '{port}' which is not explicitly documented in the specification.",
                            category="Interface",
                            source_section="RTL Discovery",
                            priority="Medium",
                            rtl_cross_check="Undocumented_In_Spec",
                        )
                    )
                    feat_idx += 1

        if not features:
            features.append(
                FeatureItem(
                    feature_id="FEAT-001",
                    title="Core Functional Processing",
                    description="Execute primary operations as defined in the specification.",
                    category="Functional",
                    source_section=current_section,
                    priority="Critical",
                    rtl_cross_check="Confirmed" if rtl_data else "N/A",
                )
            )

        return features

