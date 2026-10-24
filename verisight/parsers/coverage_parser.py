"""
Coverage Report Parser for VeriSight.

Parses text-based coverage reports and extracts functional, code,
and assertion coverage metrics. Converts binary coverage databases
(.ucdb, .vdb) via vendor CLI utilities (vcover, urg) when available.

This is a deterministic parser — no LLM calls.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

from verisight.schemas.knowledge_schema import CoverageData
from verisight.utils.logger import get_logger

logger = get_logger("coverage_parser")


class CoverageFormatError(RuntimeError):
    """Raised when a coverage file format is unsupported, binary without tools, or conversion fails."""
    pass


def _is_binary_file(filepath: Path) -> bool:
    """Detect if file contains null bytes or non-text binary data."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
            chunk.decode("utf-8")
            return False
    except UnicodeDecodeError:
        return True
    except Exception:
        return False


def _convert_ucdb(filepath: Path) -> str:
    """Convert .ucdb database to text using Siemens Questa vcover."""
    vcover_bin = shutil.which("vcover")
    if not vcover_bin:
        raise CoverageFormatError(
            f"Cannot parse binary UCDB database '{filepath}': Siemens/Questa 'vcover' is not installed or not found on PATH. "
            f"Please run 'vcover report -details -all \"{filepath}\"' to generate a readable text coverage report."
        )

    cmd = [vcover_bin, "report", "-details", "-all", str(filepath)]
    logger.info(f"Converting UCDB with vcover: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        raise CoverageFormatError(f"vcover execution failed for '{filepath}': {exc}") from exc

    if proc.returncode != 0:
        raise CoverageFormatError(
            f"vcover conversion failed for '{filepath}' (exit code {proc.returncode}):\n"
            f"{proc.stderr or proc.stdout}"
        )

    if not proc.stdout.strip():
        raise CoverageFormatError(
            f"vcover reported success but emitted empty output for '{filepath}':\n{proc.stderr}"
        )

    return proc.stdout


def _convert_vdb(dirpath: Path) -> str:
    """Convert .vdb directory to text using Synopsys VCS urg."""
    urg_bin = shutil.which("urg")
    if not urg_bin:
        raise CoverageFormatError(
            f"Cannot parse VCS coverage database directory '{dirpath}': Synopsys 'urg' is not installed or not found on PATH. "
            f"Please run 'urg -dir \"{dirpath}\" -format text' to generate a readable text coverage report."
        )

    with tempfile.TemporaryDirectory(prefix="verisight_urg_") as tmp_dir:
        report_dir = Path(tmp_dir) / "urgReport"
        cmd = [urg_bin, "-dir", str(dirpath), "-format", "text", "-report", str(report_dir)]
        logger.info(f"Converting VDB with urg: {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as exc:
            raise CoverageFormatError(f"urg execution failed for '{dirpath}': {exc}") from exc

        if proc.returncode != 0:
            raise CoverageFormatError(
                f"urg conversion failed for '{dirpath}' (exit code {proc.returncode}):\n"
                f"{proc.stderr or proc.stdout}"
            )

        text_parts = []
        if report_dir.exists():
            for report_file in sorted(report_dir.glob("*.txt")):
                try:
                    text_parts.append(report_file.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    pass

        if text_parts:
            return "\n\n".join(text_parts)

        if proc.stdout.strip():
            return proc.stdout

        raise CoverageFormatError(
            f"urg reported success but generated no text reports for '{dirpath}':\n{proc.stderr}"
        )


def parse_coverage(filepath: str) -> CoverageData:
    """
    Parse a text-based coverage report or convert a binary database (.ucdb, .vdb)
    if vendor tools are available.

    Args:
        filepath: Path to the coverage report file or .vdb directory.

    Returns:
        CoverageData Pydantic model.

    Raises:
        FileNotFoundError: If filepath does not exist.
        CoverageFormatError: If binary data cannot be converted or format is invalid.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Coverage file or directory not found: {filepath}")

    logger.info(f"Parsing coverage report: {filepath}")

    if path.is_dir():
        if path.suffix.lower() == ".vdb" or "vdb" in path.name.lower():
            content = _convert_vdb(path)
        else:
            raise CoverageFormatError(
                f"Directory '{filepath}' is not a recognized coverage database (.vdb)."
            )
    else:
        if path.suffix.lower() == ".ucdb":
            if _is_binary_file(path):
                content = _convert_ucdb(path)
            else:
                try:
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = _convert_ucdb(path)
        elif _is_binary_file(path):
            raise CoverageFormatError(
                f"Binary coverage data detected in '{filepath}'. "
                "Unable to decode as UTF-8 text coverage report. "
                "Please export as text coverage report or provide a supported format."
            )
        else:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise CoverageFormatError(
                    f"Failed to decode coverage file '{filepath}' as UTF-8 text: {exc}. "
                    "Ensure the report is text-encoded."
                ) from exc

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
