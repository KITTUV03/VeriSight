"""
Coverage Report Parser for VeriSight.

Parses text-based coverage reports and extracts functional, code,
and assertion coverage metrics.

This is a deterministic parser — no LLM calls.
"""

import re
from pathlib import Path
from typing import List, Dict

from verisight.schemas.knowledge_schema import CoverageData
from verisight.utils.file_utils import read_file
from verisight.utils.logger import get_logger

logger = get_logger("coverage_parser")


def parse_coverage(filepath: str) -> CoverageData:
    """
    Parse a text-based coverage report.

    Args:
        filepath: Path to the coverage report file.

    Returns:
        CoverageData Pydantic model.
    """
    logger.info(f"Parsing coverage report: {filepath}")
    content = read_file(filepath)
    if not content:
        logger.warning(f"Empty or unreadable coverage file: {filepath}")
        return CoverageData()

    coverage = CoverageData(raw_report=content)

    # Extract code coverage metrics
    coverage.code_coverage = _extract_code_coverage(content)

    # Extract functional coverage
    coverage.functional_coverage = _extract_functional_coverage(content)

    # Extract assertion coverage
    coverage.assertion_coverage = _extract_assertion_coverage(content)

    # Extract uncovered bins
    coverage.uncovered_bins = _extract_uncovered_bins(content)

    logger.info(
        f"Coverage parsed: {len(coverage.code_coverage)} code metrics, "
        f"{len(coverage.functional_coverage)} functional metrics, "
        f"{len(coverage.uncovered_bins)} uncovered bins"
    )
    return coverage


def _extract_code_coverage(content: str) -> Dict[str, float]:
    """Extract code coverage metrics (line, branch, toggle, etc.)."""
    metrics: Dict[str, float] = {}

    # Common coverage report patterns
    patterns = [
        (r"(?:line|statement)\s+coverage\s*[=:]\s*([\d.]+)%", "line_coverage"),
        (r"(?:branch|conditional)\s+coverage\s*[=:]\s*([\d.]+)%", "branch_coverage"),
        (r"toggle\s+coverage\s*[=:]\s*([\d.]+)%", "toggle_coverage"),
        (r"fsm\s+(?:state\s+)?coverage\s*[=:]\s*([\d.]+)%", "fsm_coverage"),
        (r"(?:condition|expression)\s+coverage\s*[=:]\s*([\d.]+)%", "condition_coverage"),
        (r"(?:total|overall)\s+(?:code\s+)?coverage\s*[=:]\s*([\d.]+)%", "total_coverage"),
    ]

    for pattern, key in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            metrics[key] = float(match.group(1))

    # Also try table format: | Metric | Coverage |
    table_pattern = re.compile(
        r"\|\s*(\w[\w\s]*?)\s*\|\s*([\d.]+)%?\s*\|",
        re.MULTILINE
    )
    for match in table_pattern.finditer(content):
        metric_name = match.group(1).strip().lower().replace(" ", "_")
        if "coverage" in content[max(0, match.start()-100):match.start()].lower():
            metrics[metric_name] = float(match.group(2))

    return metrics


def _extract_functional_coverage(content: str) -> Dict[str, float]:
    """Extract functional coverage metrics."""
    metrics: Dict[str, float] = {}

    # Covergroup patterns
    cg_pattern = re.compile(
        r"(?:covergroup|Covergroup|COVERGROUP)\s+(\w+)\s*.*?"
        r"(?:coverage|Coverage)\s*[=:]\s*([\d.]+)%",
        re.MULTILINE | re.IGNORECASE
    )
    for match in cg_pattern.finditer(content):
        metrics[match.group(1)] = float(match.group(2))

    # Overall functional coverage
    func_pattern = re.search(
        r"(?:functional|func)\s+coverage\s*[=:]\s*([\d.]+)%",
        content, re.IGNORECASE
    )
    if func_pattern:
        metrics["functional_total"] = float(func_pattern.group(1))

    return metrics


def _extract_assertion_coverage(content: str) -> Dict[str, float]:
    """Extract assertion coverage metrics."""
    metrics: Dict[str, float] = {}

    assert_pattern = re.compile(
        r"(?:assertion|assert)\s+(\w+)\s*.*?"
        r"(?:coverage|pass_rate)\s*[=:]\s*([\d.]+)%",
        re.MULTILINE | re.IGNORECASE
    )
    for match in assert_pattern.finditer(content):
        metrics[match.group(1)] = float(match.group(2))

    # Overall assertion coverage
    overall = re.search(
        r"assertion\s+coverage\s*[=:]\s*([\d.]+)%",
        content, re.IGNORECASE
    )
    if overall:
        metrics["assertion_total"] = float(overall.group(1))

    return metrics


def _extract_uncovered_bins(content: str) -> List[str]:
    """Extract uncovered bins from the report."""
    uncovered = []

    # Pattern: bin_name: 0 hits or UNCOVERED
    bin_pattern = re.compile(
        r"(\w+)\s*:\s*(?:0\s+hits?|UNCOVERED|uncovered|NOT_COVERED)",
        re.MULTILINE
    )
    for match in bin_pattern.finditer(content):
        uncovered.append(match.group(1))

    return uncovered
