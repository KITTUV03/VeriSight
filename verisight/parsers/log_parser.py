"""
Simulation Log Parser for VeriSight.

Parses UVM simulation log files and extracts categorized events
including UVM_INFO/WARNING/ERROR/FATAL, assertion failures, timeouts,
scoreboard mismatches, and other simulation events.

This is a deterministic, regex-based parser — no LLM calls.
"""

import re
from pathlib import Path
from typing import List, Optional

from verisight.schemas.log_schema import (
    LogKnowledge, LogEntry, AssertionFailure, ScoreboardMismatch,
    Timeout, ConstraintFailure, NullPointer, FactoryError,
    ConfigDBFailure, TLMFailure, PhaseDeadlock, ProtocolViolation,
    SimulationSummary,
)
from verisight.utils.file_utils import read_file
from verisight.utils.logger import get_logger

logger = get_logger("log_parser")

# Regex patterns for UVM log line parsing
UVM_LOG_PATTERN = re.compile(
    r"(UVM_INFO|UVM_WARNING|UVM_ERROR|UVM_FATAL)\s+"
    r"(?:(\S+)\((\d+)\)\s+)?"  # optional file(line)
    r"@\s*(\d+(?:\.\d+)?)\s*(?:ns|ps|us|ms)?\s*:\s*"  # @timestamp:
    r"(?:(\S+)\s+)?"  # optional component path
    r"\[([^\]]*)\]\s*"  # [ID]
    r"(.*)",  # message
    re.MULTILINE
)

# Alternative simpler UVM pattern
UVM_SIMPLE_PATTERN = re.compile(
    r"(UVM_INFO|UVM_WARNING|UVM_ERROR|UVM_FATAL)\s*"
    r"(?:@\s*(\d+(?:\.\d+)?)\s*(?:ns|ps|us|ms)?)?\s*"
    r"[:\s]*(.*)",
    re.MULTILINE
)

# Assertion failure patterns
ASSERTION_PATTERN = re.compile(
    r"(?:Assertion|ASSERTION)\s+(?:(\w+)\s+)?(?:failed|FAILED|error)"
    r"(?:\s+at\s+time\s+(\d+)\s*(?:ns|ps|us|ms)?)?"
    r"(?:\s+in\s+(\w+))?"
    r"(?:\s*:\s*(.*))?",
    re.MULTILINE | re.IGNORECASE
)

# SVA assertion failure
SVA_FAILURE_PATTERN = re.compile(
    r"(?:Error|Fatal).*?:\s*(?:(\w+\.sv)\((\d+)\))?\s*"
    r"(?:Assertion\s+(\w+)\s+)?.*?(?:FAILED|failed|error)"
    r"(?:.*?@\s*(\d+)\s*(?:ns|ps|us|ms)?)?",
    re.MULTILINE
)

# Scoreboard mismatch patterns
MISMATCH_PATTERN = re.compile(
    r"(?:MISMATCH|mismatch|Mismatch|MISCOMPARE|ERROR.*?mismatch)"
    r".*?(?:expected|exp)\s*[=:]?\s*(?:0x)?([0-9a-fA-FxXzZ]+)"
    r".*?(?:actual|act|got|received)\s*[=:]?\s*(?:0x)?([0-9a-fA-FxXzZ]+)",
    re.MULTILINE | re.IGNORECASE
)

# Alternative mismatch: actual vs expected (reversed order)
MISMATCH_ALT_PATTERN = re.compile(
    r"(?:actual|got)\s*[=:]?\s*(?:0x)?([0-9a-fA-FxXzZ]+)"
    r".*?(?:expected|exp)\s*[=:]?\s*(?:0x)?([0-9a-fA-FxXzZ]+)",
    re.MULTILINE | re.IGNORECASE
)


def parse_log(filepath: str) -> LogKnowledge:
    """
    Parse a UVM simulation log file.

    Args:
        filepath: Path to the simulation log file.

    Returns:
        LogKnowledge Pydantic model.
    """
    logger.info(f"Parsing simulation log: {filepath}")
    content = read_file(filepath)
    if not content:
        logger.error(f"Empty or unreadable log file: {filepath}")
        return LogKnowledge()

    lines = content.splitlines()
    log = LogKnowledge(
        log_file=filepath,
        total_lines=len(lines),
    )

    # Parse all UVM log entries
    _parse_uvm_entries(content, lines, log)

    # Parse assertion failures
    _parse_assertion_failures(content, log)

    # Parse scoreboard mismatches
    _parse_mismatches(content, lines, log)

    # Parse timeouts
    _parse_timeouts(content, log)

    # Parse constraint failures
    _parse_constraint_failures(content, log)

    # Parse null pointer errors
    _parse_null_pointers(content, log)

    # Parse factory errors
    _parse_factory_errors(content, log)

    # Parse config_db failures
    _parse_config_db_failures(content, log)

    # Parse TLM failures
    _parse_tlm_failures(content, log)

    # Parse protocol violations
    _parse_protocol_violations(content, log)

    # Generate summary
    log.summary = _generate_summary(content, log)

    logger.info(
        f"Log parsed: {log.summary.total_errors} errors, "
        f"{log.summary.total_fatals} fatals, "
        f"{len(log.assertion_failures)} assertion failures, "
        f"{len(log.scoreboard_mismatches)} mismatches"
    )
    return log


def _parse_uvm_entries(content: str, lines: List[str], log: LogKnowledge) -> None:
    """Parse all UVM_INFO/WARNING/ERROR/FATAL entries."""
    for i, line in enumerate(lines):
        # Try detailed pattern first
        match = UVM_LOG_PATTERN.search(line)
        if match:
            severity = match.group(1)
            src_file = match.group(2) or ""
            src_line = int(match.group(3)) if match.group(3) else 0
            timestamp = match.group(4) or ""
            component = match.group(5) or ""
            msg = match.group(7) or ""

            entry = LogEntry(
                severity=severity,
                timestamp=f"{timestamp} ns" if timestamp else "",
                component=component,
                message=msg.strip(),
                file=src_file,
                line=src_line,
                raw_line=line.strip(),
                line_number_in_log=i + 1,
            )
            log.entries.append(entry)

            if severity == "UVM_ERROR":
                log.errors.append(entry)
            elif severity == "UVM_FATAL":
                log.fatals.append(entry)
            elif severity == "UVM_WARNING":
                log.warnings.append(entry)
            continue

        # Try simpler pattern
        match = UVM_SIMPLE_PATTERN.search(line)
        if match:
            severity = match.group(1)
            timestamp = match.group(2) or ""
            msg = match.group(3) or ""

            entry = LogEntry(
                severity=severity,
                timestamp=f"{timestamp} ns" if timestamp else "",
                message=msg.strip(),
                raw_line=line.strip(),
                line_number_in_log=i + 1,
            )
            log.entries.append(entry)

            if severity == "UVM_ERROR":
                log.errors.append(entry)
            elif severity == "UVM_FATAL":
                log.fatals.append(entry)
            elif severity == "UVM_WARNING":
                log.warnings.append(entry)


def _parse_assertion_failures(content: str, log: LogKnowledge) -> None:
    """Parse assertion failure events."""
    for match in ASSERTION_PATTERN.finditer(content):
        log.assertion_failures.append(AssertionFailure(
            assertion_name=match.group(1) or "",
            timestamp=f"{match.group(2)} ns" if match.group(2) else "",
            module=match.group(3) or "",
            message=match.group(4) or "",
        ))

    for match in SVA_FAILURE_PATTERN.finditer(content):
        log.assertion_failures.append(AssertionFailure(
            file=match.group(1) or "",
            line=int(match.group(2)) if match.group(2) else 0,
            assertion_name=match.group(3) or "",
            timestamp=f"{match.group(4)} ns" if match.group(4) else "",
        ))


def _parse_mismatches(content: str, lines: List[str], log: LogKnowledge) -> None:
    """Parse scoreboard mismatch events."""
    for i, line in enumerate(lines):
        match = MISMATCH_PATTERN.search(line)
        if match:
            # Get timestamp from nearby UVM entry
            ts = _find_nearby_timestamp(lines, i)
            log.scoreboard_mismatches.append(ScoreboardMismatch(
                timestamp=ts,
                expected=match.group(1),
                actual=match.group(2),
                message=line.strip(),
            ))
            continue

        match = MISMATCH_ALT_PATTERN.search(line)
        if match:
            ts = _find_nearby_timestamp(lines, i)
            log.scoreboard_mismatches.append(ScoreboardMismatch(
                timestamp=ts,
                actual=match.group(1),
                expected=match.group(2),
                message=line.strip(),
            ))


def _find_nearby_timestamp(lines: List[str], current_line: int) -> str:
    """Find the nearest timestamp from surrounding log lines."""
    for offset in range(5):
        for delta in [0, -offset, offset]:
            idx = current_line + delta
            if 0 <= idx < len(lines):
                ts_match = re.search(r"@\s*(\d+(?:\.\d+)?)\s*(?:ns|ps|us|ms)", lines[idx])
                if ts_match:
                    return f"{ts_match.group(1)} ns"
    return ""


def _parse_timeouts(content: str, log: LogKnowledge) -> None:
    """Parse timeout events."""
    timeout_pattern = re.compile(
        r"(?:TIMEOUT|timeout|Timeout|phase.*?timeout|watchdog)"
        r".*?(?:@\s*(\d+)\s*(?:ns|ps|us|ms))?"
        r"(?:.*?phase\s*=\s*(\w+))?"
        r"(?:\s*:\s*(.*))?",
        re.MULTILINE | re.IGNORECASE
    )
    for match in timeout_pattern.finditer(content):
        log.timeouts.append(Timeout(
            timestamp=f"{match.group(1)} ns" if match.group(1) else "",
            phase=match.group(2) or "",
            message=match.group(0).strip(),
        ))


def _parse_constraint_failures(content: str, log: LogKnowledge) -> None:
    """Parse constraint randomization failures."""
    pattern = re.compile(
        r"(?:randomize|constraint)\s+(?:failed|failure|error)"
        r".*?(?:class\s+(\w+))?"
        r".*?(?:constraint\s+(\w+))?",
        re.MULTILINE | re.IGNORECASE
    )
    for match in pattern.finditer(content):
        log.constraint_failures.append(ConstraintFailure(
            class_name=match.group(1) or "",
            constraint_name=match.group(2) or "",
            message=match.group(0).strip(),
        ))


def _parse_null_pointers(content: str, log: LogKnowledge) -> None:
    """Parse null pointer access errors."""
    pattern = re.compile(
        r"(?:null\s+(?:object|pointer|handle)|access.*?null)"
        r".*?(?:(\w+)\s+is\s+null)?"
        r"(?:.*?@\s*(\d+)\s*(?:ns|ps|us|ms))?",
        re.MULTILINE | re.IGNORECASE
    )
    for match in pattern.finditer(content):
        log.null_pointers.append(NullPointer(
            variable=match.group(1) or "",
            timestamp=f"{match.group(2)} ns" if match.group(2) else "",
            message=match.group(0).strip(),
        ))


def _parse_factory_errors(content: str, log: LogKnowledge) -> None:
    """Parse UVM factory errors."""
    pattern = re.compile(
        r"(?:factory|create)\s+(?:error|failed|failure)"
        r".*?(?:type\s+(\w+))?"
        r"(?:.*?@\s*(\d+)\s*(?:ns|ps|us|ms))?",
        re.MULTILINE | re.IGNORECASE
    )
    for match in pattern.finditer(content):
        log.factory_errors.append(FactoryError(
            type_name=match.group(1) or "",
            timestamp=f"{match.group(2)} ns" if match.group(2) else "",
            message=match.group(0).strip(),
        ))


def _parse_config_db_failures(content: str, log: LogKnowledge) -> None:
    """Parse config_db get failures."""
    pattern = re.compile(
        r"uvm_config_db.*?(?:get\s+failed|not\s+found|error)"
        r".*?(?:\"(\w+)\")?",
        re.MULTILINE | re.IGNORECASE
    )
    for match in pattern.finditer(content):
        log.config_db_failures.append(ConfigDBFailure(
            field_name=match.group(1) or "",
            message=match.group(0).strip(),
        ))


def _parse_tlm_failures(content: str, log: LogKnowledge) -> None:
    """Parse TLM connection/communication failures."""
    pattern = re.compile(
        r"(?:TLM|tlm|port)\s+(?:connection|connect)\s+(?:error|failed|failure)"
        r".*?(?:port\s+(\w+))?",
        re.MULTILINE | re.IGNORECASE
    )
    for match in pattern.finditer(content):
        log.tlm_failures.append(TLMFailure(
            port=match.group(1) or "",
            message=match.group(0).strip(),
        ))


def _parse_protocol_violations(content: str, log: LogKnowledge) -> None:
    """Parse protocol violation messages."""
    pattern = re.compile(
        r"(?:protocol|PROTOCOL)\s+(?:violation|error|VIOLATION)"
        r".*?(?:(\w+)\s+protocol)?"
        r"(?:.*?signal\s+(\w+))?"
        r"(?:.*?@\s*(\d+)\s*(?:ns|ps|us|ms))?",
        re.MULTILINE | re.IGNORECASE
    )
    for match in pattern.finditer(content):
        log.protocol_violations.append(ProtocolViolation(
            protocol=match.group(1) or "",
            signal=match.group(2) or "",
            timestamp=f"{match.group(3)} ns" if match.group(3) else "",
            message=match.group(0).strip(),
        ))


def _generate_summary(content: str, log: LogKnowledge) -> SimulationSummary:
    """Generate simulation summary from parsed data."""
    # Count severities
    total_info = sum(1 for e in log.entries if e.severity == "UVM_INFO")
    total_warnings = len(log.warnings)
    total_errors = len(log.errors)
    total_fatals = len(log.fatals)

    # Determine pass/fail
    if total_fatals > 0 or total_errors > 0:
        pass_fail = "FAIL"
    else:
        pass_fail = "PASS"

    # Extract simulation time from UVM report summary
    sim_time = ""
    time_match = re.search(
        r"(?:Simulation|simulation)\s+(?:time|end)\s*[=:]\s*(\d+)\s*(?:ns|ps|us|ms)",
        content
    )
    if time_match:
        sim_time = f"{time_match.group(1)} ns"
    else:
        # Use last timestamp
        timestamps = re.findall(r"@\s*(\d+(?:\.\d+)?)\s*(?:ns|ps|us|ms)", content)
        if timestamps:
            sim_time = f"{timestamps[-1]} ns"

    # Extract random seed
    seed = ""
    seed_match = re.search(r"(?:seed|SEED)\s*[=:]\s*(\d+)", content)
    if seed_match:
        seed = seed_match.group(1)

    # Check for UVM report summary
    uvm_summary = re.search(
        r"UVM_INFO\s*:\s*(\d+).*?"
        r"UVM_WARNING\s*:\s*(\d+).*?"
        r"UVM_ERROR\s*:\s*(\d+).*?"
        r"UVM_FATAL\s*:\s*(\d+)",
        content, re.DOTALL
    )
    if uvm_summary:
        total_info = int(uvm_summary.group(1))
        total_warnings = int(uvm_summary.group(2))
        total_errors = int(uvm_summary.group(3))
        total_fatals = int(uvm_summary.group(4))

    return SimulationSummary(
        total_info=total_info,
        total_warnings=total_warnings,
        total_errors=total_errors,
        total_fatals=total_fatals,
        simulation_time=sim_time,
        pass_fail=pass_fail,
        seed=seed,
    )
