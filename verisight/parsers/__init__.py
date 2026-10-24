"""Deterministic parsers for VeriSight input files."""
from verisight.parsers.coverage_parser import parse_coverage, CoverageFormatError

__all__ = ["parse_coverage", "CoverageFormatError"]
