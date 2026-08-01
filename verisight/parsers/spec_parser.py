"""
Specification Parser for VeriSight.

Parses Markdown design specification documents and extracts structured
knowledge including functional requirements, timing constraints, reset
behavior, protocol rules, register maps, state machines, and corner cases.

This is a deterministic parser — no LLM calls.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

from verisight.schemas.spec_schema import (
    SpecKnowledge, Requirement, TimingRequirement, ResetBehavior,
    ProtocolRule, RegisterDescription, RegisterField,
    StateMachineSpec, StateTransition, CornerCase, IllegalCondition,
)
from verisight.utils.file_utils import read_file
from verisight.utils.logger import get_logger

logger = get_logger("spec_parser")


def parse_spec(filepath: str) -> SpecKnowledge:
    """
    Parse a Markdown design specification into structured knowledge.

    Args:
        filepath: Path to the .md specification file.

    Returns:
        SpecKnowledge Pydantic model.
    """
    logger.info(f"Parsing specification: {filepath}")
    content = read_file(filepath)
    if not content:
        logger.error(f"Empty or unreadable spec file: {filepath}")
        return SpecKnowledge()

    # Extract title from first heading
    title = _extract_title(content)

    # Split into sections by heading
    sections = _split_sections(content)

    # Extract structured data from sections
    spec = SpecKnowledge(
        title=title,
        raw_sections=sections,
        functional_requirements=_extract_requirements(sections),
        timing_requirements=_extract_timing(sections),
        reset_behavior=_extract_reset(sections),
        protocol_rules=_extract_protocol_rules(sections),
        register_descriptions=_extract_registers(sections),
        state_machines=_extract_state_machines(sections),
        corner_cases=_extract_corner_cases(sections),
        illegal_conditions=_extract_illegal_conditions(sections),
    )

    logger.info(
        f"Spec parsed: {len(spec.functional_requirements)} requirements, "
        f"{len(spec.register_descriptions)} registers, "
        f"{len(spec.state_machines)} FSMs"
    )
    return spec


def _extract_title(content: str) -> str:
    """Extract title from first H1 heading."""
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _split_sections(content: str) -> Dict[str, str]:
    """
    Split Markdown content into sections by heading hierarchy.

    Returns dict mapping heading text to section body.
    """
    sections: Dict[str, str] = {}
    # Match headings at any level
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    matches = list(heading_pattern.finditer(content))
    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[heading] = content[start:end].strip()

    return sections


def _extract_requirements(sections: Dict[str, str]) -> List[Requirement]:
    """Extract functional requirements from sections."""
    requirements = []
    req_counter = 1

    # Keywords that indicate requirement sections
    req_keywords = [
        "requirement", "functional", "feature", "operation",
        "behavior", "description", "overview", "specification",
    ]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        is_req_section = any(k in heading_lower for k in req_keywords)

        if is_req_section or body.strip():
            # Extract bullet points as individual requirements
            bullets = re.findall(r"^[\-\*]\s+(.+)$", body, re.MULTILINE)
            for bullet in bullets:
                requirements.append(Requirement(
                    id=f"REQ-{req_counter:03d}",
                    description=bullet.strip(),
                    section=heading,
                    category=_categorize_requirement(bullet),
                ))
                req_counter += 1

            # Extract numbered items
            numbered = re.findall(r"^\d+[\.\)]\s+(.+)$", body, re.MULTILINE)
            for item in numbered:
                requirements.append(Requirement(
                    id=f"REQ-{req_counter:03d}",
                    description=item.strip(),
                    section=heading,
                    category=_categorize_requirement(item),
                ))
                req_counter += 1

            # If section has no bullets but has content, treat whole section as one req
            if not bullets and not numbered and is_req_section and len(body) > 10:
                requirements.append(Requirement(
                    id=f"REQ-{req_counter:03d}",
                    description=body[:500].strip(),
                    section=heading,
                    category=_categorize_requirement(body),
                ))
                req_counter += 1

    return requirements


def _categorize_requirement(text: str) -> str:
    """Categorize a requirement by keyword analysis."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["clock", "timing", "frequency", "latency", "delay"]):
        return "timing"
    if any(k in text_lower for k in ["reset", "initialize", "power-on"]):
        return "reset"
    if any(k in text_lower for k in ["protocol", "handshake", "bus", "apb", "ahb", "axi"]):
        return "protocol"
    return "functional"


def _extract_timing(sections: Dict[str, str]) -> List[TimingRequirement]:
    """Extract timing requirements."""
    timing_reqs = []
    timing_keywords = ["timing", "clock", "frequency", "latency", "delay", "period"]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        if any(k in heading_lower for k in timing_keywords):
            # Extract timing specifications from bullets
            bullets = re.findall(r"^[\-\*]\s+(.+)$", body, re.MULTILINE)
            for bullet in bullets:
                # Try to extract signal name and constraint
                signal_match = re.search(r"(\w+)\s*[:=]", bullet)
                value_match = re.search(r"(\d+\.?\d*)\s*(ns|us|ms|ps|MHz|GHz|clk|cycles?)", bullet)
                timing_reqs.append(TimingRequirement(
                    signal=signal_match.group(1) if signal_match else "",
                    constraint=bullet.strip(),
                    value=value_match.group(1) if value_match else "",
                    unit=value_match.group(2) if value_match else "ns",
                    section=heading,
                ))

    return timing_reqs


def _extract_reset(sections: Dict[str, str]) -> List[ResetBehavior]:
    """Extract reset behavior specifications."""
    resets = []
    reset_keywords = ["reset", "initialization", "power-on", "startup"]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        if any(k in heading_lower for k in reset_keywords):
            # Detect reset signal names
            reset_signals = re.findall(
                r"(\w*reset\w*|\w*rst\w*)", body, re.IGNORECASE
            )
            reset_signal = reset_signals[0] if reset_signals else "rst_n"

            # Detect active level
            active = "low" if any(
                k in body.lower() for k in ["active low", "active-low", "_n", "negedge"]
            ) else "high"

            # Detect sync/async
            reset_type = "asynchronous" if any(
                k in body.lower() for k in ["async", "asynchronous"]
            ) else "synchronous"

            # Extract affected signals and reset values
            affected = []
            reset_values = {}
            for line in body.splitlines():
                # Pattern: signal_name = value (on reset) or signal → 0
                val_match = re.search(
                    r"(\w+)\s*(?:=|→|->|:)\s*(\d+|0x[0-9a-fA-F]+|'[bhd]\d+)", line
                )
                if val_match:
                    sig = val_match.group(1)
                    val = val_match.group(2)
                    affected.append(sig)
                    reset_values[sig] = val

            resets.append(ResetBehavior(
                reset_signal=reset_signal,
                active_level=active,
                type=reset_type,
                affected_signals=affected,
                reset_values=reset_values,
                section=heading,
            ))

    return resets


def _extract_protocol_rules(sections: Dict[str, str]) -> List[ProtocolRule]:
    """Extract protocol rules."""
    rules = []
    protocol_keywords = ["protocol", "interface", "bus", "apb", "ahb", "axi", "wishbone", "handshake"]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        if any(k in heading_lower for k in protocol_keywords):
            # Detect protocol name
            protocol = "Custom"
            for p in ["APB", "AHB", "AXI", "Wishbone"]:
                if p.lower() in heading_lower or p.lower() in body.lower():
                    protocol = p
                    break

            bullets = re.findall(r"^[\-\*]\s+(.+)$", body, re.MULTILINE)
            for i, bullet in enumerate(bullets):
                rules.append(ProtocolRule(
                    protocol=protocol,
                    rule_id=f"PROT-{i + 1:03d}",
                    description=bullet.strip(),
                    section=heading,
                ))

    return rules


def _extract_registers(sections: Dict[str, str]) -> List[RegisterDescription]:
    """Extract register descriptions from tables and lists."""
    registers = []
    reg_keywords = ["register", "address", "memory map", "csr"]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        if any(k in heading_lower for k in reg_keywords):
            # Try to parse markdown tables
            table_rows = re.findall(
                r"\|\s*(\w+)\s*\|\s*(0x[0-9a-fA-F]+|\d+)\s*\|(.+)\|",
                body,
            )
            for name, addr, rest in table_rows:
                if name.lower() in ("name", "register", "---"):
                    continue
                registers.append(RegisterDescription(
                    name=name.strip(),
                    address=addr.strip(),
                    description=rest.strip().strip("|").strip(),
                    section=heading,
                ))

            # Also try bullet-based register descriptions
            reg_matches = re.findall(
                r"^[\-\*]\s+\*\*(\w+)\*\*\s*(?:\(([^)]+)\))?\s*[:\-]\s*(.+)$",
                body, re.MULTILINE
            )
            for name, addr, desc in reg_matches:
                registers.append(RegisterDescription(
                    name=name.strip(),
                    address=addr.strip() if addr else "",
                    description=desc.strip(),
                    section=heading,
                ))

    return registers


def _extract_state_machines(sections: Dict[str, str]) -> List[StateMachineSpec]:
    """Extract state machine specifications."""
    fsms = []
    fsm_keywords = ["state machine", "fsm", "state diagram", "states"]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        if any(k in heading_lower for k in fsm_keywords):
            # Extract state names
            states = re.findall(r"\b([A-Z][A-Z_0-9]{2,})\b", body)
            states = list(dict.fromkeys(states))  # deduplicate preserving order

            # Extract transitions (patterns like STATE1 → STATE2 or STATE1 -> STATE2)
            transitions = []
            trans_matches = re.findall(
                r"(\w+)\s*(?:→|->|to)\s*(\w+)\s*(?:when|if|on|:)?\s*(.*?)(?:\n|$)",
                body, re.IGNORECASE
            )
            for src, dst, cond in trans_matches:
                transitions.append(StateTransition(
                    from_state=src.strip(),
                    to_state=dst.strip(),
                    condition=cond.strip(),
                ))

            if states:
                fsms.append(StateMachineSpec(
                    name=heading,
                    states=states,
                    initial_state=states[0] if states else "",
                    transitions=transitions,
                    section=heading,
                ))

    return fsms


def _extract_corner_cases(sections: Dict[str, str]) -> List[CornerCase]:
    """Extract corner cases and boundary conditions."""
    cases = []
    corner_keywords = ["corner", "boundary", "edge case", "special case", "exception"]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        if any(k in heading_lower for k in corner_keywords):
            bullets = re.findall(r"^[\-\*]\s+(.+)$", body, re.MULTILINE)
            for bullet in bullets:
                cases.append(CornerCase(
                    description=bullet.strip(),
                    section=heading,
                ))

    return cases


def _extract_illegal_conditions(sections: Dict[str, str]) -> List[IllegalCondition]:
    """Extract illegal/forbidden conditions."""
    conditions = []
    illegal_keywords = ["illegal", "forbidden", "prohibited", "invalid", "error condition"]

    for heading, body in sections.items():
        heading_lower = heading.lower()
        if any(k in heading_lower for k in illegal_keywords):
            bullets = re.findall(r"^[\-\*]\s+(.+)$", body, re.MULTILINE)
            for bullet in bullets:
                conditions.append(IllegalCondition(
                    description=bullet.strip(),
                    section=heading,
                ))

    return conditions
