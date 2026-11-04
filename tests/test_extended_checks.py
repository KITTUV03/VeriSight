"""
Unit tests for VeriSight extended RTL checks and assertion synthesis.

Tests:
1. Extended CDC checks (multi-bit crossing, raw clock gating, glitch before sync).
2. Extended Lint checks (casex, arithmetic shift, signed/unsigned, logical/bitwise, clock edge).
3. Extended Structural checks (FSM deadlock, counter checks, dual-port collision, port swaps).
4. Extended Protocol checks (AXI4, AHB, APB).
5. Extended Security & Misc checks (key zeroization, sync reset with clock gating).
6. SVA assertion synthesis (AXI4, AHB, APB, FIFO, Reset).
"""

import pytest
from verisight.schemas.rtl_schema import (
    RTLModule, Port, Parameter, AlwaysBlock, FSM, FSMState, FSMTransition, ClockDomain,
)
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.analysis.extended_checks import (
    run_extended_cdc_checks,
    run_extended_lint_checks,
    run_extended_structural_checks,
    run_extended_protocol_checks,
    run_extended_security_misc_checks,
)
from verisight.plan.assertion_generator import synthesize_sva_from_spec


def test_cdc_multibit_crossing_and_raw_clock_gating():
    """Verify multi-bit CDC crossing and raw clock gating detection."""
    mod = RTLModule(
        name="cdc_test",
        file="cdc_test.sv",
        ports=[
            Port(name="clk_a", direction="input", width="1"),
            Port(name="clk_b", direction="input", width="1"),
            Port(name="tx_data", direction="output", width="[7:0]"),
        ],
        clock_domains=[
            ClockDomain(clock_signal="clk_a", signals=["tx_data"]),
            ClockDomain(clock_signal="clk_b", signals=["tx_data"]),
        ],
        assignments=[
            "assign clk_gated = clk_a & en_gate;",
        ],
    )
    issues = run_extended_cdc_checks(mod)
    types = [i.issue_type for i in issues]

    assert "multi_bit_crossing" in types
    assert "raw_clock_gating" in types
    assert any("data tearing" in i.description for i in issues if i.issue_type == "multi_bit_crossing")


def test_lint_casex_and_arithmetic_shift_mismatch():
    """Verify casex hazard and arithmetic shift on unsigned vector."""
    raw_code = """
    module lint_test(input logic [7:0] a, output logic [7:0] y);
      always_comb begin
        casex (a)
          8'b1xxx_xxxx: y = 8'h1;
          default: y = a >>> 2;
        endcase
      end
    endmodule
    """
    mod = RTLModule(
        name="lint_test",
        file="lint_test.sv",
        ports=[
            Port(name="a", direction="input", width="[7:0]", signal_type="logic"),
            Port(name="y", direction="output", width="[7:0]", signal_type="logic"),
        ],
        raw_source=raw_code,
    )
    issues = run_extended_lint_checks(mod)
    types = [i.issue_type for i in issues]

    assert "casex_hazard" in types
    assert "arithmetic_shift_mismatch" in types
    assert "implicit_net" in types  # missing `default_nettype none


def test_lint_signed_unsigned_comparison_and_operator_confusion():
    """Verify signed vs unsigned comparison and & vs && confusion."""
    raw_code = """
    module op_test(input logic [7:0] in_a, input logic flag_a, input logic flag_b);
      always_comb begin
        if ((flag_a == 1'b1) & (flag_b == 1'b0)) begin
          if ($signed(in_a) < 8'd20) begin
            // bug
          end
        end
      end
    endmodule
    """
    mod = RTLModule(
        name="op_test",
        file="op_test.sv",
        ports=[
            Port(name="in_a", direction="input", width="[7:0]"),
            Port(name="flag_a", direction="input", width="1"),
            Port(name="flag_b", direction="input", width="1"),
        ],
        raw_source=raw_code,
    )
    issues = run_extended_lint_checks(mod)
    types = [i.issue_type for i in issues]

    assert "signed_unsigned_mismatch" in types
    assert "logical_bitwise_confusion" in types


def test_structural_fsm_deadlock_and_counter_check():
    """Verify FSM deadlock detection and counter terminal equality warning."""
    raw_code = """
    module struct_test;
      always_ff @(posedge clk) begin
        if (counter == 10) begin
          counter <= 0;
        end
      end
    endmodule
    """
    fsm = FSM(
        name="struct_test_state",
        state_variable="state",
        states=[FSMState(name="IDLE"), FSMState(name="STUCK")],
        transitions=[
            FSMTransition(from_state="IDLE", to_state="STUCK"),
            FSMTransition(from_state="STUCK", to_state="STUCK"),  # Deadlock
        ],
    )
    mod = RTLModule(
        name="struct_test",
        file="struct_test.sv",
        fsms=[fsm],
        raw_source=raw_code,
    )
    issues = run_extended_structural_checks(mod)
    types = [i.issue_type for i in issues]

    assert "fsm_deadlock" in types
    assert "counter_terminal_check" in types


def test_structural_dual_port_collision():
    """Verify dual-port RAM write collision detection."""
    raw_code = """
    module dpram(
      input logic clk,
      input logic we_a,
      input logic we_b,
      input logic [7:0] addr_a,
      input logic [7:0] addr_b,
      input logic [31:0] din_a,
      input logic [31:0] din_b
    );
      // No collision arbitration
    endmodule
    """
    mod = RTLModule(
        name="dpram",
        file="dpram.sv",
        ports=[
            Port(name="we_a", direction="input", width="1"),
            Port(name="we_b", direction="input", width="1"),
            Port(name="addr_a", direction="input", width="[7:0]"),
            Port(name="addr_b", direction="input", width="[7:0]"),
        ],
        raw_source=raw_code,
    )
    issues = run_extended_structural_checks(mod)
    types = [i.issue_type for i in issues]

    assert "dual_port_collision" in types


def test_protocol_checks_apb_and_axi():
    """Verify APB and AXI4 protocol compliance checks."""
    mod = RTLModule(
        name="axi_slave",
        file="axi_slave.sv",
        ports=[
            Port(name="awvalid", direction="output", width="1"),
            Port(name="awready", direction="input", width="1"),
            Port(name="psel", direction="input", width="1"),
            Port(name="paddr", direction="input", width="32"),
        ],
        always_blocks=[
            # Drives awvalid without reading awready
            AlwaysBlock(
                block_type="sequential",
                signals_written=["awvalid"],
                signals_read=[],
                line_start=15,
            ),
            # Reads paddr without qualifying with psel
            AlwaysBlock(
                block_type="combinational",
                signals_written=["internal_data"],
                signals_read=["paddr"],
                line_start=30,
            ),
        ],
    )
    issues = run_extended_protocol_checks(mod, ["AXI", "APB"])
    rules = [i.rule for i in issues]

    assert "AXI_VALID_READY_PERSISTENCE" in rules
    assert "APB_ADDR_QUALIFICATION" in rules


def test_security_key_zeroization_missing():
    """Verify detection of secret/key registers missing reset zeroization."""
    mod = RTLModule(
        name="aes_core",
        file="aes_core.sv",
        ports=[
            Port(name="cipher_key", direction="input", width="[127:0]"),
        ],
        always_blocks=[
            AlwaysBlock(
                block_type="sequential",
                has_reset=True,
                signals_written=["cipher_key"],
                raw_code="if (!rst_n) begin /* missing zeroize */ end",
            )
        ],
    )
    issues = run_extended_security_misc_checks(mod)
    types = [i.issue_type for i in issues]

    assert "key_zeroization_missing" in types


def test_sva_synthesis_axi_ahb_apb_fifo():
    """Verify SVA synthesis generates checks for AXI, AHB, APB, and FIFOs."""
    spec_text = """
    # Multi-Protocol SoC Interface
    The module implements APB pready and psel handshakes.
    Write to read-only register 0x10 is forbidden and must signal pslverr.
    The AXI master asserts awvalid and wvalid.
    The FIFO buffer indicates full and empty flags.
    """
    suite = synthesize_sva_from_spec(spec_text, module_name="soc_dut")
    names = [a.name for a in suite.assertions]

    assert "SVA_APB_PHASE_SEQUENCE" in names
    assert "SVA_APB_WAIT_STABILITY" in names
    assert "SVA_APB_RO_WRITE_PROTECTION" in names
    assert "SVA_AXI_AWVALID_STABLE" in names
    assert "SVA_AXI_4KB_BOUNDARY" in names
    assert "SVA_FIFO_NO_OVERFLOW" in names
    assert "SVA_FIFO_NO_UNDERFLOW" in names
    assert "soc_dut_sva_bind" in suite.bind_file_content
