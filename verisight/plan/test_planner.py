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

    def __init__(self):
        super().__init__("test_planner")

    def execute(self, features: List[FeatureItem], design_name: str = "DUT") -> List[TestScenario]:
        """Execute test plan generation."""
        return self.generate_test_plan(features, design_name)

    def generate_test_plan(
        self,
        features: List[FeatureItem],
        design_name: str = "DUT",
    ) -> List[TestScenario]:
        """
        Generate test scenarios mapped to feature items.

        Args:
            features: List of extracted FeatureItems.
            design_name: Name of the design under test.

        Returns:
            List of TestScenario objects.
        """
        logger.info(f"Generating test plan for {design_name} across {len(features)} features...")

        feature_summary = "\n".join(
            [f"- [{f.feature_id}] {f.title} ({f.category}, Priority: {f.priority}): {f.description}" for f in features]
        )

        prompt = f"""Generate an exhaustive UVM Test Plan for {design_name} based on the following features:

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
            tests = [TestScenario(**item) for item in test_data]
            if tests:
                logger.info(f"Successfully generated {len(tests)} test scenarios via LLM.")
                return tests
        except Exception as e:
            logger.warning(f"LLM test planning failed or offline ({e}). Using deterministic generator.")

        return self._deterministic_generate(features, design_name)

    def _deterministic_generate(
        self, features: List[FeatureItem], design_name: str
    ) -> List[TestScenario]:
        """Deterministic fallback test scenario generator."""
        tests = []
        test_idx = 1

        # 1. Reset Test
        tests.append(
            TestScenario(
                test_id=f"TEST-{test_idx:03d}",
                feature_ids=[features[0].feature_id] if features else ["FEAT-001"],
                title="Power-on Reset & Default State Verification",
                test_type="Directed",
                description="Verify all internal registers and outputs initialize to known defaults upon reset assertion.",
                stimulus="Assert reset for 10 clock cycles, deassert reset, monitor output signals.",
                expected_response="Outputs match specified reset values; no uninitialized X values observed.",
                priority="Critical",
            )
        )
        test_idx += 1

        # 2. Map features to directed and random tests
        for feat in features:
            tests.append(
                TestScenario(
                    test_id=f"TEST-{test_idx:03d}",
                    feature_ids=[feat.feature_id],
                    title=f"Directed Test: {feat.title}",
                    test_type="Directed",
                    description=f"Verify feature requirement: {feat.description}",
                    stimulus=f"Apply targeted stimulus exercising {feat.title} under nominal conditions.",
                    expected_response=f"Scoreboard validates output calculation according to {feat.title}.",
                    priority=feat.priority,
                )
            )
            test_idx += 1

            tests.append(
                TestScenario(
                    test_id=f"TEST-{test_idx:03d}",
                    feature_ids=[feat.feature_id],
                    title=f"Corner Case & Random Test: {feat.title}",
                    test_type="Corner_Case",
                    description=f"Stress boundary conditions for {feat.title}.",
                    stimulus=f"Randomize inputs with boundary constraints (zero, max values, sign toggle).",
                    expected_response="No arithmetic overflow corruption, correct status flag updates.",
                    priority="High",
                )
            )
            test_idx += 1

        return tests
