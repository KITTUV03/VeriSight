"""
Root-Cause-Bench Hardware Evaluation Suite.

Inspired by:
Towards LLM-based Root Cause Analysis of Hardware Design Failures (IEEE COINS 2025 / arXiv:2507.06512)
https://github.com/llm4hw/root-cause-bench
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from verisight.utils.logger import get_logger

logger = get_logger("root_cause_bench")


class BenchmarkScenario(BaseModel):
    """A standard hardware failure benchmark scenario."""
    scenario_id: str
    design_type: str  # e.g., ALU, FIFO, RAM, APB, AHB
    failure_type: str  # simulation_runtime, synthesis_elaboration, protocol_violation
    bug_category: str  # data_truncation, ro_protection, x_propagation, cdc, fsm_deadlock
    expected_root_cause_keyword: str
    description: str


# Standard scenarios aligned with Root-Cause-Bench dataset
STANDARD_SCENARIOS: List[BenchmarkScenario] = [
    BenchmarkScenario(
        scenario_id="RCB_SIM_01",
        design_type="APB",
        failure_type="protocol_violation",
        bug_category="ro_protection",
        expected_root_cause_keyword="pslverr",
        description="Write to read-only register fails to assert PSLVERR protocol error response.",
    ),
    BenchmarkScenario(
        scenario_id="RCB_SIM_02",
        design_type="APB",
        failure_type="simulation_runtime",
        bug_category="data_truncation",
        expected_root_cause_keyword="truncat",
        description="Upper 16 bits of 32-bit data register masked or truncated during write.",
    ),
    BenchmarkScenario(
        scenario_id="RCB_SIM_03",
        design_type="RAM",
        failure_type="simulation_runtime",
        bug_category="x_propagation",
        expected_root_cause_keyword="uninitialized",
        description="Uninitialized memory array or address registers propagate X states.",
    ),
    BenchmarkScenario(
        scenario_id="RCB_SIM_04",
        design_type="AHB",
        failure_type="protocol_violation",
        bug_category="ro_protection",
        expected_root_cause_keyword="hresp",
        description="Write to read-only register fails to assert HRESP error response on AHB bus.",
    ),
    BenchmarkScenario(
        scenario_id="RCB_SIM_05",
        design_type="AHB",
        failure_type="simulation_runtime",
        bug_category="data_truncation",
        expected_root_cause_keyword="truncat",
        description="DATA0 register drops upper 16 bits during 32-bit AHB write transaction.",
    ),
]


class BenchmarkEvaluationResult(BaseModel):
    """Result of benchmark execution."""
    total_scenarios: int
    passed_scenarios: int
    pass_rate: float
    results_by_scenario: Dict[str, bool] = Field(default_factory=dict)
    summary: str = ""


def evaluate_diagnosis_accuracy(
    predicted_cause: str,
    scenario: BenchmarkScenario,
) -> bool:
    """Evaluates if the predicted root cause matches the benchmark gold standard."""
    kw = scenario.expected_root_cause_keyword.lower()
    cat = scenario.bug_category.lower().replace("_", " ")
    pred_lower = predicted_cause.lower()

    return kw in pred_lower or cat in pred_lower
