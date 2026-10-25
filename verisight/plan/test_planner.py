"""
Test Planner for VeriSight Plan.

Generates a comprehensive verification test plan mapped to extracted features:
- Directed functional tests
- Constrained random test scenarios
- Corner case stress tests
- Error injection & negative testing
- Performance & backpressure scenarios
"""

import json
from typing import List, Optional, Dict, Any

from verisight.agents.base_agent import BaseAgent
from verisight.plan.schemas import FeatureItem, TestScenario
from verisight.utils.logger import get_logger

logger = get_logger("plan.test_planner")

SYSTEM_PROMPT = """You are a Lead Verification Engineer designing a comprehensive UVM Test Plan for an ASIC block.
Your job is to generate thorough, executable test scenarios covering every defined feature.

CRITICAL RULES:
1. Each test scenario must map to one or more Feature IDs (feature_ids: ["FEAT-001", ...]).
2. Assign unique Test IDs (e.g. TEST-001, TEST-002, ...).
3. Test types must cover:
   - Directed (reset, sanity, standard modes)
   - Constrained_Random (random data operands, sequences)
   - Corner_Case (min/max boundary values, overflow/underflow, full/empty conditions)
   - Error_Injection (illegal opcodes, protocol violations, invalid handshakes)
   - Stress (back-to-back transfers, continuous traffic)
4. Detail the stimulus sequence and expected scoreboard check for each test.
5. Return a valid JSON object matching the requested schema.
"""


class TestPlanner(BaseAgent):
    """Generates structured Test Plan mapped to decomposed features."""

    __test__ = False  # Prevent pytest from mistaking this agent for a test class

    def __init__(self):
        super().__init__("test_planner")

    def execute(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
        rtl_info: Optional[Dict[str, Any]] = None,
    ) -> List[TestScenario]:
        """Execute test plan generation."""
        return self.generate_test_plan(features, design_name, rtl_info)

    def generate_test_plan(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
        rtl_info: Optional[Dict[str, Any]] = None,
    ) -> List[TestScenario]:
        """
        Generate test scenarios mapped to feature items.

        Args:
            features: List of extracted FeatureItems.
            design_name: Name of the design under test.
            rtl_info: Optional RTL port, signal, and type metadata.

        Returns:
            List of TestScenario objects.
        """
        logger.info(f"Generating test plan for {design_name} across {len(features)} features...")

        # Batch features to ensure all are processed without context window truncation
        chunk_size = 15
        feature_chunks = [features[i:i + chunk_size] for i in range(0, len(features), chunk_size)]
        all_tests: List[TestScenario] = []

        rtl_summary = ""
        if rtl_info and "ports" in rtl_info:
            ports_desc = [f"{p.get('name', '')} ({p.get('dir', '')} [{p.get('width', 1)}])" for p in rtl_info["ports"]]
            rtl_summary = f"RTL Ports: {', '.join(ports_desc)}"

        use_llm = True
        for chunk_idx, chunk in enumerate(feature_chunks):
            if not use_llm:
                break
            feature_summary = "\n".join(
                [f"- [{f.feature_id}] {f.title} ({f.category}, Priority: {f.priority}): {f.description}" for f in chunk]
            )

            prompt = f"""Generate an exhaustive UVM Test Plan for {design_name} (Batch {chunk_idx+1}/{len(feature_chunks)}).

═══ RTL HARDWARE SIGNALS ═══
{rtl_summary or "Inferred from spec"}

═══ FEATURE DECOMPOSITION ═══
{feature_summary}

Generate test cases covering:
1. Directed Sanity & Reset Tests
2. Constrained Random Operations
3. Extreme Boundary / Corner Cases (0x00, 0xFF, Max values, Underflow/Overflow)
4. Error Injection & Illegal Conditions
5. Stress / Back-to-Back Operations

Return a JSON object with a single "test_scenarios" list of objects with fields:
- test_id (e.g. TEST-001, TEST-002, ...)
- feature_ids (list of string IDs e.g. ["FEAT-001"])
- title (descriptive test title)
- test_type (Directed | Constrained_Random | Corner_Case | Error_Injection | Stress | Performance)
- description (verification goal)
- stimulus (sequence configuration and stimulus details)
- expected_response (DUT reaction and scoreboard verification check)
- priority (Critical | High | Medium | Low)
"""
            try:
                raw_response = self.reason(prompt=prompt, system_prompt=SYSTEM_PROMPT)
                json_str = self._extract_json(raw_response)
                parsed_json = json.loads(json_str) if json_str else {}

                test_data = parsed_json.get("test_scenarios", [])
                for item in test_data:
                    all_tests.append(TestScenario(**item))
            except Exception as e:
                logger.warning(f"LLM test planning batch {chunk_idx+1} failed ({e}). Switching to deterministic generator.")
                use_llm = False
                break

        if all_tests:
            logger.info(f"Successfully generated {len(all_tests)} test scenarios via LLM.")
            return all_tests

        return self._deterministic_generate(features, design_name, rtl_info)

    def _deterministic_generate(
        self,
        features: List[FeatureItem],
        design_name: str,
        rtl_info: Optional[Dict[str, Any]] = None,
    ) -> List[TestScenario]:
        """Deterministic, grounded fallback test scenario generator."""
        tests: List[TestScenario] = []
        test_idx = 1

        # 1. Power-on Reset & Default State Test
        tests.append(
            TestScenario(
                test_id=f"TEST-{test_idx:03d}",
                feature_ids=[features[0].feature_id] if features else ["FEAT-001"],
                title="Power-on Reset & Default State Verification",
                test_type="Directed",
                description=f"Verify all {design_name} internal registers and outputs initialize to known defaults upon reset assertion.",
                stimulus="Assert active-low reset for 10 clock cycles, deassert reset, monitor output signals for stability.",
                expected_response="Outputs match specified reset values; no uninitialized X or Z values observed on output pins.",
                priority="Critical",
            )
        )
        test_idx += 1

        # 2. Check for Protocol / Bus signals
        has_handshake = rtl_info and any(k in [p.get("name", "").lower() for p in rtl_info.get("ports", [])] for k in ["valid", "ready", "req", "ack"])
        if has_handshake:
            tests.append(
                TestScenario(
                    test_id=f"TEST-{test_idx:03d}",
                    feature_ids=[features[0].feature_id] if features else ["FEAT-001"],
                    title=f"{design_name} Handshake Backpressure & Stall Test",
                    test_type="Stress",
                    description="Verify that DUT holds data stable when downstream ready/ack is deasserted.",
                    stimulus="Assert valid/req and drive random ready delays between 1 and 20 clock cycles.",
                    expected_response="Data word remains unchanged across stall cycles; transfer completes without drop when ready asserts.",
                    priority="Critical",
                )
            )
            test_idx += 1

        # 3. Map features to directed, corner, and error injection tests
        for feat in features:
            f_title_low = feat.title.lower()
            f_desc_low = feat.description.lower()

            # Directed functional test
            tests.append(
                TestScenario(
                    test_id=f"TEST-{test_idx:03d}",
                    feature_ids=[feat.feature_id],
                    title=f"Directed Test: {feat.title}",
                    test_type="Directed",
                    description=f"Verify functional compliance for: {feat.description}",
                    stimulus=f"Drive targeted stimulus patterns exercising '{feat.title}' across nominal input domains.",
                    expected_response=f"Reference model and scoreboard validate exact output cycle-by-cycle for '{feat.title}'.",
                    priority=feat.priority,
                )
            )
            test_idx += 1

            # Corner case boundary test
            tests.append(
                TestScenario(
                    test_id=f"TEST-{test_idx:03d}",
                    feature_ids=[feat.feature_id],
                    title=f"Boundary & Corner Case: {feat.title}",
                    test_type="Corner_Case",
                    description=f"Stress extremal boundary limits and rollover conditions for {feat.title}.",
                    stimulus="Randomize input vectors constrained to minimum zero bound, maximum all-ones ceiling, and sign inversion points.",
                    expected_response="DUT prevents arithmetic truncation, sets status flags appropriately, and recovers within 1 cycle.",
                    priority="High",
                )
            )
            test_idx += 1

            # Error injection / negative test if feature involves control/op/protocol/register
            if any(k in f_title_low or k in f_desc_low for k in ["op", "reg", "cmd", "protocol", "mode", "address"]):
                tests.append(
                    TestScenario(
                        test_id=f"TEST-{test_idx:03d}",
                        feature_ids=[feat.feature_id],
                        title=f"Negative Test / Error Injection: {feat.title}",
                        test_type="Error_Injection",
                        description=f"Inject illegal inputs or reserved commands targeting {feat.title}.",
                        stimulus="Drive reserved encodings, unaligned accesses, or protocol timing violations.",
                        expected_response="DUT asserts error response or gracefully drops transaction without hanging internal state.",
                        priority="High",
                    )
                )
                test_idx += 1

        return tests

