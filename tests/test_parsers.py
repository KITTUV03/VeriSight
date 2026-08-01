"""
Unit tests for VeriSight parsers.

Tests the deterministic parsers (spec, RTL, UVM, log) against
the ALU example inputs.
"""

import pytest
from pathlib import Path

# Get paths to example files
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SPEC_PATH = EXAMPLES_DIR / "specs" / "alu_spec.md"
RTL_PATH = EXAMPLES_DIR / "rtl"
TB_PATH = EXAMPLES_DIR / "tb"
LOG_PATH = EXAMPLES_DIR / "logs" / "sim.log"


class TestSpecParser:
    """Tests for spec_parser.py"""

    def test_parse_spec_returns_knowledge(self):
        from verisight.parsers.spec_parser import parse_spec
        result = parse_spec(str(SPEC_PATH))
        assert result is not None
        assert result.title != ""

    def test_spec_has_functional_requirements(self):
        from verisight.parsers.spec_parser import parse_spec
        result = parse_spec(str(SPEC_PATH))
        assert len(result.functional_requirements) > 0, "Should extract requirements"

    def test_spec_has_reset_behavior(self):
        from verisight.parsers.spec_parser import parse_spec
        result = parse_spec(str(SPEC_PATH))
        assert len(result.reset_behavior) > 0, "Should extract reset behavior"
        rst = result.reset_behavior[0]
        assert "rst" in rst.reset_signal.lower() or "reset" in rst.reset_signal.lower()

    def test_spec_has_corner_cases(self):
        from verisight.parsers.spec_parser import parse_spec
        result = parse_spec(str(SPEC_PATH))
        assert len(result.corner_cases) > 0, "Should extract corner cases"

    def test_spec_has_illegal_conditions(self):
        from verisight.parsers.spec_parser import parse_spec
        result = parse_spec(str(SPEC_PATH))
        assert len(result.illegal_conditions) > 0, "Should extract illegal conditions"

    def test_spec_raw_sections_populated(self):
        from verisight.parsers.spec_parser import parse_spec
        result = parse_spec(str(SPEC_PATH))
        assert len(result.raw_sections) > 0, "Should have raw sections"

    def test_parse_nonexistent_file(self):
        from verisight.parsers.spec_parser import parse_spec
        result = parse_spec("/nonexistent/file.md")
        assert result.title == ""
        assert len(result.functional_requirements) == 0


class TestRTLParser:
    """Tests for rtl_parser.py"""

    def test_parse_rtl_returns_knowledge(self):
        from verisight.parsers.rtl_parser import parse_rtl
        result = parse_rtl(str(RTL_PATH))
        assert result is not None
        assert len(result.modules) > 0

    def test_rtl_finds_alu_module(self):
        from verisight.parsers.rtl_parser import parse_rtl
        result = parse_rtl(str(RTL_PATH))
        module_names = [m.name for m in result.modules]
        assert "alu" in module_names, f"Should find 'alu' module, found: {module_names}"

    def test_rtl_extracts_ports(self):
        from verisight.parsers.rtl_parser import parse_rtl
        result = parse_rtl(str(RTL_PATH))
        alu = [m for m in result.modules if m.name == "alu"][0]
        port_names = [p.name for p in alu.ports]
        assert "clk" in port_names
        assert "rst_n" in port_names
        assert "operand_a" in port_names
        assert "result" in port_names

    def test_rtl_extracts_always_blocks(self):
        from verisight.parsers.rtl_parser import parse_rtl
        result = parse_rtl(str(RTL_PATH))
        alu = [m for m in result.modules if m.name == "alu"][0]
        assert len(alu.always_blocks) >= 2, "Should find at least 2 always blocks"

        # Check for combinational and sequential blocks
        types = [b.block_type for b in alu.always_blocks]
        assert "combinational" in types, "Should have combinational block"
        assert "sequential" in types, "Should have sequential block"

    def test_rtl_detects_sequential_block_with_reset(self):
        from verisight.parsers.rtl_parser import parse_rtl
        result = parse_rtl(str(RTL_PATH))
        alu = [m for m in result.modules if m.name == "alu"][0]
        seq_blocks = [b for b in alu.always_blocks if b.block_type == "sequential"]
        assert len(seq_blocks) > 0
        # The ALU has a sequential block with partial reset
        seq = seq_blocks[0]
        assert seq.clock_signal == "clk"

    def test_rtl_top_module_detection(self):
        from verisight.parsers.rtl_parser import parse_rtl
        result = parse_rtl(str(RTL_PATH))
        assert result.top_module == "alu"

    def test_rtl_file_list_populated(self):
        from verisight.parsers.rtl_parser import parse_rtl
        result = parse_rtl(str(RTL_PATH))
        assert len(result.file_list) > 0


class TestUVMParser:
    """Tests for uvm_parser.py"""

    def test_parse_uvm_returns_knowledge(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert result is not None

    def test_uvm_finds_driver(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.drivers) > 0, "Should find at least one driver"
        driver_names = [d.name for d in result.drivers]
        assert "alu_driver" in driver_names, f"Should find alu_driver, found: {driver_names}"

    def test_uvm_finds_monitor(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.monitors) > 0, "Should find at least one monitor"

    def test_uvm_finds_scoreboard(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.scoreboards) > 0, "Should find at least one scoreboard"

    def test_uvm_finds_sequences(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.sequences) > 0, "Should find at least one sequence"

    def test_uvm_finds_transactions(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.transactions) > 0, "Should find at least one transaction"

    def test_uvm_finds_interface(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.interfaces) > 0, "Should find interface"

    def test_uvm_finds_config_db(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.config_db_entries) > 0, "Should find config_db entries"

    def test_uvm_file_list(self):
        from verisight.parsers.uvm_parser import parse_uvm
        result = parse_uvm(str(TB_PATH))
        assert len(result.file_list) >= 5, "Should find multiple TB files"


class TestLogParser:
    """Tests for log_parser.py"""

    def test_parse_log_returns_knowledge(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log(str(LOG_PATH))
        assert result is not None

    def test_log_finds_errors(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log(str(LOG_PATH))
        assert len(result.errors) > 0, "Should find UVM_ERROR entries"
        assert result.summary.total_errors == 4, f"Should find 4 errors, got {result.summary.total_errors}"

    def test_log_finds_mismatches(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log(str(LOG_PATH))
        assert len(result.scoreboard_mismatches) > 0, "Should find scoreboard mismatches"

    def test_log_detects_x_values(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log(str(LOG_PATH))
        # Check that mismatches with 'xx' are found
        x_mismatches = [
            m for m in result.scoreboard_mismatches
            if "xx" in m.actual.lower() or "xx" in m.message.lower()
        ]
        assert len(x_mismatches) > 0, "Should detect X values in mismatches"

    def test_log_summary(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log(str(LOG_PATH))
        assert result.summary.pass_fail == "FAIL"
        assert result.summary.total_errors > 0

    def test_log_simulation_time(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log(str(LOG_PATH))
        assert result.summary.simulation_time != "", "Should extract simulation time"

    def test_log_entry_timestamps(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log(str(LOG_PATH))
        # Check that entries have timestamps
        entries_with_ts = [e for e in result.entries if e.timestamp]
        assert len(entries_with_ts) > 0, "Should have entries with timestamps"

    def test_parse_nonexistent_log(self):
        from verisight.parsers.log_parser import parse_log
        result = parse_log("/nonexistent/sim.log")
        assert result.total_lines == 0


class TestSVLexer:
    """Tests for sv_lexer.py"""

    def test_tokenize_simple(self):
        from verisight.utils.sv_lexer import tokenize, TokenType
        tokens = tokenize("module test; endmodule")
        keywords = [t for t in tokens if t.type == TokenType.KEYWORD]
        assert len(keywords) >= 2

    def test_strip_comments(self):
        from verisight.utils.sv_lexer import strip_comments
        result = strip_comments("logic a; // comment\nlogic b; /* block */")
        assert "//" not in result
        assert "/*" not in result
        assert "logic a" in result
        assert "logic b" in result

    def test_tokenize_numbers(self):
        from verisight.utils.sv_lexer import tokenize, TokenType
        tokens = tokenize("8'hFF 4'b0101 32")
        numbers = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(numbers) >= 2


class TestSchemas:
    """Tests for Pydantic schema validation."""

    def test_spec_knowledge_creation(self):
        from verisight.schemas.spec_schema import SpecKnowledge
        spec = SpecKnowledge(title="Test")
        assert spec.title == "Test"
        assert len(spec.functional_requirements) == 0

    def test_classification_creation(self):
        from verisight.schemas.classification import Classification
        c = Classification(
            classification="RTL Bug",
            confidence=95,
            reason="Test reason",
        )
        assert c.classification == "RTL Bug"
        assert c.confidence == 95

    def test_error_report_creation(self):
        from verisight.schemas.report_schema import ErrorReport
        r = ErrorReport(
            classification="RTL Bug",
            confidence=90,
            root_cause="Missing reset",
        )
        assert r.classification == "RTL Bug"
        assert r.severity == "medium"  # default

    def test_unified_knowledge_creation(self):
        from verisight.schemas.knowledge_schema import UnifiedKnowledge
        uk = UnifiedKnowledge()
        assert uk.spec is not None
        assert uk.rtl is not None
        assert uk.tb is not None
        assert uk.logs is not None
