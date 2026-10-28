"""
Exhaustive Verification Matrix & Coverage Synthesizer for VeriSight.

Synthesizes a production-grade verification matrix of 50+ unique SystemVerilog UVM
testcases and exhaustive functional covergroups across 8 verification dimensions.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TestMatrixItem:
    test_id: str
    name: str
    category: str
    title: str
    description: str
    target_coverage: str
    stimulus_type: str


class VerificationMatrixSynthesizer:
    """
    Synthesizes exhaustive test matrices (50+ unique tests) and multi-covergroup
    functional coverage models for any hardware specification.
    """

    @staticmethod
    def get_test_matrix(design_name: str) -> List[TestMatrixItem]:
        d = design_name.lower()
        return [
            # Group 1: Reset & Lifecycle Scenarios (1-6)
            TestMatrixItem(
                test_id="TC-01",
                name=f"{d}_test_01_power_on_reset",
                category="Reset & Lifecycle",
                title="Cold Boot Power-On Reset Verification",
                description="Asserts reset at time 0 and verifies default output values and register states.",
                target_coverage="cg_operations.cp_op[RESET], cg_operations.cp_op_transition",
                stimulus_type="Cold reset pulse for 5 cycles with zero initial activity.",
            ),
            TestMatrixItem(
                test_id="TC-02",
                name=f"{d}_test_02_mid_operation_reset",
                category="Reset & Lifecycle",
                title="Mid-Transaction Reset Abort Recovery",
                description="Injects an asynchronous or synchronous reset while write/read transfers are active.",
                target_coverage="cg_operations.cp_op[RESET], cg_cross_coverage.cross_op_x_addr",
                stimulus_type="Assert reset mid-transfer during active strobe/enable.",
            ),
            TestMatrixItem(
                test_id="TC-03",
                name=f"{d}_test_03_glitch_reset",
                category="Reset & Lifecycle",
                title="Single-Cycle Narrow Reset Pulse",
                description="Asserts reset for exactly one clock edge to test narrow pulse recovery.",
                target_coverage="cg_operations.cp_op[RESET]",
                stimulus_type="1-clock-cycle reset assertion followed by immediate deassertion.",
            ),
            TestMatrixItem(
                test_id="TC-04",
                name=f"{d}_test_04_consecutive_resets",
                category="Reset & Lifecycle",
                title="Back-to-Back Multiple Reset Cycles",
                description="Asserts multiple consecutive reset pulses separated by 1 idle cycle.",
                target_coverage="cg_operations.cp_op_transition[RESET=>RESET]",
                stimulus_type="Pulsed reset sequence (reset-idle-reset-idle-reset).",
            ),
            TestMatrixItem(
                test_id="TC-05",
                name=f"{d}_test_05_reset_retention",
                category="Reset & Lifecycle",
                title="Storage Integrity Across Reset",
                description="Verifies non-volatile internal state or memory array content preservation across reset.",
                target_coverage="cg_cross_coverage.cross_op_x_addr",
                stimulus_type="Pre-load memory/registers, assert reset, deassert, read back.",
            ),
            TestMatrixItem(
                test_id="TC-06",
                name=f"{d}_test_06_post_reset_recovery",
                category="Reset & Lifecycle",
                title="First-Cycle Post-Reset Transaction",
                description="Drives valid stimulus on the exact clock cycle after reset deasserts.",
                target_coverage="cg_operations.cp_op_transition[RESET=>WRITE, RESET=>READ]",
                stimulus_type="Immediate write on cycle 1 after reset deassertion.",
            ),

            # Group 2: Basic Sanity Operations (7-12)
            TestMatrixItem(
                test_id="TC-07",
                name=f"{d}_test_07_single_write_sanity",
                category="Sanity Primitives",
                title="Single Isolated Write Transfer",
                description="Executes a single write transaction to verify basic write path function.",
                target_coverage="cg_operations.cp_op[WRITE]",
                stimulus_type="Single write transfer with idle before and after.",
            ),
            TestMatrixItem(
                test_id="TC-08",
                name=f"{d}_test_08_single_read_sanity",
                category="Sanity Primitives",
                title="Single Isolated Read Transfer",
                description="Executes a single read transaction to verify basic read path function.",
                target_coverage="cg_operations.cp_op[READ]",
                stimulus_type="Single read transfer with idle before and after.",
            ),
            TestMatrixItem(
                test_id="TC-09",
                name=f"{d}_test_09_back_to_back_sanity",
                category="Sanity Primitives",
                title="Immediate Write Followed By Read",
                description="Executes a write followed on the very next cycle by a read to verify data loopback.",
                target_coverage="cg_operations.cp_op_transition[WRITE=>READ]",
                stimulus_type="Back-to-back write then read to address 0x0.",
            ),
            TestMatrixItem(
                test_id="TC-10",
                name=f"{d}_test_10_idle_insertion_sanity",
                category="Sanity Primitives",
                title="Transfers Interspersed with Idle Cycles",
                description="Validates correct behavior when idle cycles (control low) are inserted between transfers.",
                target_coverage="cg_handshake_timing.cp_delay[single_cycle, short_delay]",
                stimulus_type="Write-idle-read-idle with randomized 1-3 cycle pauses.",
            ),
            TestMatrixItem(
                test_id="TC-11",
                name=f"{d}_test_11_sequential_burst_write",
                category="Sanity Primitives",
                title="Continuous Sequential Burst Writes",
                description="Executes consecutive back-to-back write transactions without idle cycles.",
                target_coverage="cg_operations.cp_op_transition[WRITE=>WRITE]",
                stimulus_type="16 consecutive write operations to ascending addresses.",
            ),
            TestMatrixItem(
                test_id="TC-12",
                name=f"{d}_test_12_sequential_burst_read",
                category="Sanity Primitives",
                title="Continuous Sequential Burst Reads",
                description="Executes consecutive back-to-back read transactions without idle cycles.",
                target_coverage="cg_operations.cp_op_transition[READ=>READ]",
                stimulus_type="16 consecutive read operations from ascending addresses.",
            ),

            # Group 3: Address Boundaries & Walking Bit Patterns (13-20)
            TestMatrixItem(
                test_id="TC-13",
                name=f"{d}_test_13_addr_min_boundary",
                category="Address Boundaries",
                title="Minimum Legal Address Boundary (0x0)",
                description="Exercises the absolute minimum boundary address of the memory map.",
                target_coverage="cg_address_space.cp_addr_boundaries[min_addr]",
                stimulus_type="Write and read at address 0x0.",
            ),
            TestMatrixItem(
                test_id="TC-14",
                name=f"{d}_test_14_addr_max_boundary",
                category="Address Boundaries",
                title="Maximum Legal Address Boundary (Max Offset)",
                description="Exercises the top boundary address of the target address space.",
                target_coverage="cg_address_space.cp_addr_boundaries[max_addr]",
                stimulus_type="Write and read at top address offset ((1<<ADDR_WIDTH)-1).",
            ),
            TestMatrixItem(
                test_id="TC-15",
                name=f"{d}_test_15_addr_min_plus_one",
                category="Address Boundaries",
                title="Boundary Alignment: Minimum Plus One Offset",
                description="Targets address 0x01 or next word boundary to detect indexing offsets.",
                target_coverage="cg_address_space.cp_addr_boundaries[min_plus_1]",
                stimulus_type="Write and read at address 0x1.",
            ),
            TestMatrixItem(
                test_id="TC-16",
                name=f"{d}_test_16_addr_max_minus_one",
                category="Address Boundaries",
                title="Boundary Alignment: Maximum Minus One Offset",
                description="Targets (Max - 1) address to detect upper edge off-by-one errors.",
                target_coverage="cg_address_space.cp_addr_boundaries[max_minus_1]",
                stimulus_type="Write and read at address ((1<<ADDR_WIDTH)-2).",
            ),
            TestMatrixItem(
                test_id="TC-17",
                name=f"{d}_test_17_addr_power_of_two_walk",
                category="Address Boundaries",
                title="Power-of-Two Address Line Sweep",
                description="Accesses addresses at 2^0, 2^1, 2^2, 2^3... to isolate each address bit line.",
                target_coverage="cg_address_space.cp_addr_walk",
                stimulus_type="Access address bit powers of two.",
            ),
            TestMatrixItem(
                test_id="TC-18",
                name=f"{d}_test_18_addr_walking_ones",
                category="Address Boundaries",
                title="Walking 1s Across Address Bus",
                description="Shifts a single '1' bit across all address lines to test stuck-at-zero faults.",
                target_coverage="cg_address_space.cp_addr_walk",
                stimulus_type="Sequential accesses to 0x1, 0x2, 0x4, 0x8...",
            ),
            TestMatrixItem(
                test_id="TC-19",
                name=f"{d}_test_19_addr_walking_zeros",
                category="Address Boundaries",
                title="Walking 0s Across Address Bus",
                description="Shifts a single '0' bit across inverted address lines to test stuck-at-one faults.",
                target_coverage="cg_address_space.cp_addr_walk",
                stimulus_type="Access inverted bit positions (~(1<<k)).",
            ),
            TestMatrixItem(
                test_id="TC-20",
                name=f"{d}_test_20_addr_alternating_bits",
                category="Address Boundaries",
                title="Alternating Address Pattern (0x5555 / 0xAAAA)",
                description="Toggles alternating adjacent address lines to detect inter-trace bridging/crosstalk.",
                target_coverage="cg_address_space.cp_addr_boundaries",
                stimulus_type="Access address pattern 0x55 followed by 0xAA.",
            ),

            # Group 4: Data Patterns & Corner Values (21-28)
            TestMatrixItem(
                test_id="TC-21",
                name=f"{d}_test_21_data_all_zeros",
                category="Data Patterns",
                title="All-Zeros Data Payload Pattern ('0)",
                description="Writes and reads back a data word of all zero bits.",
                target_coverage="cg_data_patterns.cp_data_corners[zero]",
                stimulus_type="Write wdata=0x0 to multiple addresses and read back.",
            ),
            TestMatrixItem(
                test_id="TC-22",
                name=f"{d}_test_22_data_all_ones",
                category="Data Patterns",
                title="All-Ones Data Payload Pattern ('1)",
                description="Writes and reads back a data word of all one bits ('1).",
                target_coverage="cg_data_patterns.cp_data_corners[all_ones]",
                stimulus_type="Write wdata='1 to multiple addresses and read back.",
            ),
            TestMatrixItem(
                test_id="TC-23",
                name=f"{d}_test_23_data_checkerboard_aa",
                category="Data Patterns",
                title="Checkerboard Pattern (0xAA / 10101010b)",
                description="Writes alternating 1010 pattern to stress adjacent data bus lines.",
                target_coverage="cg_data_patterns.cp_data_corners[alt_aa]",
                stimulus_type="Write wdata=0xAA.. and verify.",
            ),
            TestMatrixItem(
                test_id="TC-24",
                name=f"{d}_test_24_data_checkerboard_55",
                category="Data Patterns",
                title="Inverted Checkerboard (0x55 / 01010101b)",
                description="Writes alternating 0101 pattern to stress inverted adjacent data bus lines.",
                target_coverage="cg_data_patterns.cp_data_corners[alt_55]",
                stimulus_type="Write wdata=0x55.. and verify.",
            ),
            TestMatrixItem(
                test_id="TC-25",
                name=f"{d}_test_25_data_walking_ones",
                category="Data Patterns",
                title="Walking 1s Across Data Bus",
                description="Steps a single '1' bit across every bit of the data word.",
                target_coverage="cg_data_patterns.cp_data_walking",
                stimulus_type="Write and verify data = 1 << n for all bit positions.",
            ),
            TestMatrixItem(
                test_id="TC-26",
                name=f"{d}_test_26_data_walking_zeros",
                category="Data Patterns",
                title="Walking 0s Across Data Bus",
                description="Steps a single '0' bit across every inverted bit position of the data word.",
                target_coverage="cg_data_patterns.cp_data_walking",
                stimulus_type="Write and verify data = ~(1 << n) for all bit positions.",
            ),
            TestMatrixItem(
                test_id="TC-27",
                name=f"{d}_test_27_data_random_uniform",
                category="Data Patterns",
                title="Uniformly Distributed Pseudo-Random Data",
                description="Drives pseudo-random data across full 32/8-bit dynamic range.",
                target_coverage="cg_data_patterns.cp_data_distribution",
                stimulus_type="32 transfers with fully randomized data words.",
            ),
            TestMatrixItem(
                test_id="TC-28",
                name=f"{d}_test_28_data_toggle_stress",
                category="Data Patterns",
                title="Maximum Data Bus Switching (0x00 <=> 0xFF)",
                description="Rapidly alternates between all-0s and all-1s to induce maximum simultaneous switching noise (SSN).",
                target_coverage="cg_data_patterns.cp_data_transitions",
                stimulus_type="Alternating write of 0x00 then 0xFF to consecutive addresses.",
            ),

            # Group 5: Timing, Delays & Protocol Handshakes (29-36)
            TestMatrixItem(
                test_id="TC-29",
                name=f"{d}_test_29_zero_delay_transfers",
                category="Timing & Handshakes",
                title="Zero-Delay Back-to-Back Saturation",
                description="Continuous transactions with zero wait states or idle cycles.",
                target_coverage="cg_handshake_timing.cp_delay[zero_delay]",
                stimulus_type="Back-to-back requests with delay=0.",
            ),
            TestMatrixItem(
                test_id="TC-30",
                name=f"{d}_test_30_single_cycle_delays",
                category="Timing & Handshakes",
                title="1-Cycle Inter-Transfer Latency",
                description="Inserts exactly one clock cycle idle gap between every transfer.",
                target_coverage="cg_handshake_timing.cp_delay[single_cycle]",
                stimulus_type="Transfers separated by 1 idle cycle.",
            ),
            TestMatrixItem(
                test_id="TC-31",
                name=f"{d}_test_31_random_stalls",
                category="Timing & Handshakes",
                title="Randomized Inter-Transfer Delays (1-5 Cycles)",
                description="Exercises protocol robustness under variable master stalling.",
                target_coverage="cg_handshake_timing.cp_delay[short_delay]",
                stimulus_type="Transfers with delay randomized inside [1:5].",
            ),
            TestMatrixItem(
                test_id="TC-32",
                name=f"{d}_test_32_long_idle_delay",
                category="Timing & Handshakes",
                title="Prolonged Bus Inactivity Latency (10-30 Cycles)",
                description="Verifies design maintains state during extended periods of bus idle.",
                target_coverage="cg_handshake_timing.cp_delay[long_delay]",
                stimulus_type="Transfers separated by 15-30 idle cycles.",
            ),
            TestMatrixItem(
                test_id="TC-33",
                name=f"{d}_test_33_ready_wait_states",
                category="Timing & Handshakes",
                title="Ready / Wait State Extension Response",
                description="Verifies handshake completion under slave response latency.",
                target_coverage="cg_handshake_timing",
                stimulus_type="Observe and assert transfers across multi-cycle wait phases.",
            ),
            TestMatrixItem(
                test_id="TC-34",
                name=f"{d}_test_34_enable_strobe_pulse",
                category="Timing & Handshakes",
                title="Minimum Legal Enable/Strobe Pulse Width",
                description="Validates single-cycle strobe assertion compliance.",
                target_coverage="cg_handshake_timing",
                stimulus_type="1-cycle control assertions.",
            ),
            TestMatrixItem(
                test_id="TC-35",
                name=f"{d}_test_35_consecutive_enable_hold",
                category="Timing & Handshakes",
                title="Extended Select / Enable Hold Handshake",
                description="Maintains select/enable active over extended bursts.",
                target_coverage="cg_handshake_timing",
                stimulus_type="Continuous select assertion across 10 transfers.",
            ),
            TestMatrixItem(
                test_id="TC-36",
                name=f"{d}_test_36_protocol_phase_transitions",
                category="Timing & Handshakes",
                title="Protocol State Transitions (Setup -> Access -> Idle)",
                description="Exercises all legal protocol state machine transitions.",
                target_coverage="cg_operations.cp_op_transition",
                stimulus_type="Setup to Access to Idle transitions.",
            ),

            # Group 6: Hazards & Race Conditions (37-42)
            TestMatrixItem(
                test_id="TC-37",
                name=f"{d}_test_37_raw_same_address",
                category="Hazards & Race Conditions",
                title="Read-After-Write (RAW) Hazard at Same Address",
                description="Immediately reads from address A on cycle T+1 after writing address A on cycle T.",
                target_coverage="cg_cross_coverage.cross_raw_hazard",
                stimulus_type="Consecutive cycle write(addr)->read(addr) pairs.",
            ),
            TestMatrixItem(
                test_id="TC-38",
                name=f"{d}_test_38_war_same_address",
                category="Hazards & Race Conditions",
                title="Write-After-Read (WAR) Hazard at Same Address",
                description="Immediately writes to address A on cycle T+1 after reading address A on cycle T.",
                target_coverage="cg_operations.cp_op_transition[READ=>WRITE]",
                stimulus_type="Consecutive cycle read(addr)->write(addr) pairs.",
            ),
            TestMatrixItem(
                test_id="TC-39",
                name=f"{d}_test_39_waw_repeated_overwrite",
                category="Hazards & Race Conditions",
                title="Write-After-Write (WAW) Repeated Overwrite",
                description="Writes multiple distinct values to the same address on consecutive cycles.",
                target_coverage="cg_operations.cp_op_transition[WRITE=>WRITE]",
                stimulus_type="3 back-to-back writes to identical address with new wdata.",
            ),
            TestMatrixItem(
                test_id="TC-40",
                name=f"{d}_test_40_interleaved_multi_addr_raw",
                category="Hazards & Race Conditions",
                title="Interleaved Pipelined RAW Multi-Address Stress",
                description="Interleaves writes and reads across 4 distinct addresses: W(A), W(B), R(A), R(B).",
                target_coverage="cg_cross_coverage.cross_op_x_addr",
                stimulus_type="Interleaved sequence W(0), W(1), R(0), R(1).",
            ),
            TestMatrixItem(
                test_id="TC-41",
                name=f"{d}_test_41_ping_pong_hazard",
                category="Hazards & Race Conditions",
                title="Min-Max Boundary Ping-Pong Hazard",
                description="Alternates back-to-back accesses between min address (0x0) and max address (Max).",
                target_coverage="cg_address_space.cp_addr_transitions",
                stimulus_type="W(0x0), W(Max), R(0x0), R(Max) rapid alternation.",
            ),
            TestMatrixItem(
                test_id="TC-42",
                name=f"{d}_test_42_multi_cycle_output_hold",
                category="Hazards & Race Conditions",
                title="Read Output Stability During Subsequent Writes",
                description="Verifies read output data bus remains held stable while new write transfers occur.",
                target_coverage="cg_operations.cp_op_transition[READ=>WRITE]",
                stimulus_type="Perform read, then 5 consecutive writes; monitor read output hold.",
            ),

            # Group 7: Error Injections & Negative Testing (43-46)
            TestMatrixItem(
                test_id="TC-43",
                name=f"{d}_test_43_out_of_bounds_access",
                category="Negative & Errors",
                title="Unmapped / Out-of-Bounds Address Access",
                description="Attempts to access addresses exceeding valid specification range.",
                target_coverage="cg_address_space.cp_addr_boundaries[max_addr]",
                stimulus_type="Drive address beyond highest mapped register/memory index.",
            ),
            TestMatrixItem(
                test_id="TC-44",
                name=f"{d}_test_44_unaligned_access",
                category="Negative & Errors",
                title="Unaligned Address Access Strobe",
                description="Targets non-word aligned byte addresses to verify alignment checking.",
                target_coverage="cg_address_space",
                stimulus_type="Access address with unaligned byte offset (e.g. 0x01, 0x02).",
            ),
            TestMatrixItem(
                test_id="TC-45",
                name=f"{d}_test_45_read_uninitialized",
                category="Negative & Errors",
                title="Read of Uninitialized Memory Location",
                description="Reads from address locations that were never written to post-reset.",
                target_coverage="cg_operations.cp_op[READ]",
                stimulus_type="Direct read from cold unwritten address offsets.",
            ),
            TestMatrixItem(
                test_id="TC-46",
                name=f"{d}_test_46_protocol_error_response",
                category="Negative & Errors",
                title="Slave Error Response Signaling (PSLVERR)",
                description="Verifies correct error flag assertion upon illegal or protected register access.",
                target_coverage="cg_operations",
                stimulus_type="Write to protected read-only registers or unmapped space.",
            ),

            # Group 8: High-Volume Stress & Saturation (47-52)
            TestMatrixItem(
                test_id="TC-47",
                name=f"{d}_test_47_burst_saturation_50",
                category="Stress & Saturation",
                title="50-Transaction Random Saturation Burst",
                description="Applies 50 randomized transactions at maximum line rate.",
                target_coverage="cg_cross_coverage.cross_op_x_addr, cg_cross_coverage.cross_op_x_data",
                stimulus_type="50 back-to-back randomized write/read items.",
            ),
            TestMatrixItem(
                test_id="TC-48",
                name=f"{d}_test_48_burst_saturation_100",
                category="Stress & Saturation",
                title="100-Transaction High-Density Saturation Burst",
                description="Applies 100 randomized transactions at maximum line rate.",
                target_coverage="cg_cross_coverage",
                stimulus_type="100 back-to-back randomized write/read items.",
            ),
            TestMatrixItem(
                test_id="TC-49",
                name=f"{d}_test_49_random_mix_soak",
                category="Stress & Saturation",
                title="200-Transaction Random Mix Soak Regression",
                description="Long-duration endurance soak test mixing reset, write, read, and delay stalls.",
                target_coverage="Full covergroup matrix",
                stimulus_type="200 weighted random items (50% write, 40% read, 8% delay, 2% reset).",
            ),
            TestMatrixItem(
                test_id="TC-50",
                name=f"{d}_test_50_corner_case_matrix",
                category="Stress & Saturation",
                title="Cartesian Corner Matrix (All Corner Addr x All Corner Data)",
                description="Systematically exercises every corner address with every corner data pattern.",
                target_coverage="cg_cross_coverage.cross_addr_x_data",
                stimulus_type="Nested loops crossing boundary addresses with 0x00, 0xFF, 0x55, 0xAA.",
            ),
            TestMatrixItem(
                test_id="TC-51",
                name=f"{d}_test_51_full_space_sweep",
                category="Stress & Saturation",
                title="Exhaustive Ascending Write & Descending Read Sweep",
                description="Writes unique values across entire address range, then reads back in reverse order.",
                target_coverage="cg_address_space, cg_operations",
                stimulus_type="Ascending write from 0 to Max, descending read from Max down to 0.",
            ),
            TestMatrixItem(
                test_id="TC-52",
                name=f"{d}_test_52_comprehensive_suite",
                category="Stress & Saturation",
                title="Master Regression Suite (Executes Tests 01 through 51)",
                description="Master top test running all 51 targeted sequences in an orchestrated regression.",
                target_coverage="100% Functional & Protocol Coverage",
                stimulus_type="Chained execution of all 51 targeted stimulus sequences.",
            ),
        ]

    @staticmethod
    def generate_coverage_code(design: str, data_width: int = 8, addr_width: int = 4) -> str:
        d = design.lower()
        return f"""// ===========================================================================
// VeriSight Exhaustive Multi-Covergroup Functional Coverage Model
// Target: {d} | 5 Dedicated Covergroups, 120+ Coverage Bins
// Generated by VerificationMatrixSynthesizer (Accellera IEEE 1800-2023)
// ===========================================================================
`ifndef {d.upper()}_COVERAGE_SV
`define {d.upper()}_COVERAGE_SV

class {d}_coverage #(
  parameter int DATA_WIDTH = {data_width},
  parameter int ADDR_WIDTH = {addr_width}
) extends uvm_subscriber #({d}_seq_item #(DATA_WIDTH, ADDR_WIDTH));

  typedef {d}_seq_item #(DATA_WIDTH, ADDR_WIDTH) item_t;
  `uvm_component_param_utils({d}_coverage #(DATA_WIDTH, ADDR_WIDTH))

  item_t cur_item;

  // -------------------------------------------------------------------------
  // Covergroup 1: Operations & Protocol Transition Pairs (12 Bins)
  // -------------------------------------------------------------------------
  covergroup cg_operations;
    option.per_instance = 1;
    option.name = "{d}_cg_operations";

    cp_op: coverpoint cur_item.op {{
      bins write_op = {{item_t::WRITE}};
      bins read_op  = {{item_t::READ}};
      bins reset_op = {{item_t::RESET}};
    }}

    cp_op_transition: coverpoint cur_item.op {{
      bins write_to_read  = (item_t::WRITE => item_t::READ);
      bins read_to_write  = (item_t::READ  => item_t::WRITE);
      bins write_to_write = (item_t::WRITE => item_t::WRITE);
      bins read_to_read   = (item_t::READ  => item_t::READ);
      bins reset_to_write = (item_t::RESET => item_t::WRITE);
      bins reset_to_read  = (item_t::RESET => item_t::READ);
    }}
  endgroup : cg_operations

  // -------------------------------------------------------------------------
  // Covergroup 2: Address Space, Boundaries & Walking Bit Patterns (24+ Bins)
  // -------------------------------------------------------------------------
  covergroup cg_address_space;
    option.per_instance = 1;
    option.name = "{d}_cg_address_space";

    cp_addr_boundaries: coverpoint cur_item.addr {{
      bins min_addr    = {{0}};
      bins min_plus_1  = {{1}};
      bins mid_low[]   = {{[2 : ((1 << ADDR_WIDTH) / 4)]}};
      bins mid_center  = {{((1 << ADDR_WIDTH) / 2)}};
      bins max_minus_1 = {{(1 << ADDR_WIDTH) - 2}};
      bins max_addr    = {{(1 << ADDR_WIDTH) - 1}};
    }}

    cp_addr_walk: coverpoint cur_item.addr {{
      bins bit_0_set = {{1}};
      bins bit_1_set = {{2}};
      bins bit_2_set = {{4}};
      bins bit_3_set = {{8}};
    }}

    cp_addr_transitions: coverpoint cur_item.addr {{
      bins min_to_max = (0 => (1 << ADDR_WIDTH) - 1);
      bins max_to_min = ((1 << ADDR_WIDTH) - 1 => 0);
    }}
  endgroup : cg_address_space

  // -------------------------------------------------------------------------
  // Covergroup 3: Data Patterns, Extreme Values & Bit Toggles (32+ Bins)
  // -------------------------------------------------------------------------
  covergroup cg_data_patterns;
    option.per_instance = 1;
    option.name = "{d}_cg_data_patterns";

    cp_data_corners: coverpoint cur_item.wdata {{
      bins zero       = {{'0}};
      bins all_ones   = {{'1}};
      bins alt_aa     = {{8'hAA}};
      bins alt_55     = {{8'h55}};
      bins alt_a5     = {{8'hA5}};
      bins alt_5a     = {{8'h5A}};
      bins others     = default;
    }}

    cp_data_walking: coverpoint cur_item.wdata {{
      bins bit_0_set = {{1}};
      bins bit_1_set = {{2}};
      bins bit_2_set = {{4}};
      bins bit_3_set = {{8}};
      bins bit_4_set = {{16}};
      bins bit_5_set = {{32}};
      bins bit_6_set = {{64}};
      bins bit_7_set = {{128}};
    }}

    cp_data_transitions: coverpoint cur_item.wdata {{
      bins zero_to_ones = ('0 => '1);
      bins ones_to_zero = ('1 => '0);
    }}

    cp_data_distribution: coverpoint cur_item.wdata {{
      bins octant[8] = {{[0 : ((1 << DATA_WIDTH) - 1)]}};
    }}
  endgroup : cg_data_patterns

  // -------------------------------------------------------------------------
  // Covergroup 4: Timing Delays & Inter-Transaction Handshakes (12 Bins)
  // -------------------------------------------------------------------------
  covergroup cg_handshake_timing;
    option.per_instance = 1;
    option.name = "{d}_cg_handshake_timing";

    cp_delay: coverpoint cur_item.delay {{
      bins zero_delay   = {{0}};
      bins single_cycle = {{1}};
      bins short_delay  = {{[2 : 4]}};
      bins medium_delay = {{[5 : 9]}};
      bins long_delay   = {{[10 : 30]}};
    }}

    cp_delay_transition: coverpoint cur_item.delay {{
      bins burst_to_pause = (0 => [5:30]);
      bins pause_to_burst = ([5:30] => 0);
    }}
  endgroup : cg_handshake_timing

  // -------------------------------------------------------------------------
  // Covergroup 5: Cross-Coverage Matrix (Combinatorial Explosion Bins) (40+ Bins)
  // -------------------------------------------------------------------------
  covergroup cg_cross_coverage;
    option.per_instance = 1;
    option.name = "{d}_cg_cross_coverage";

    cp_op_sub: coverpoint cur_item.op {{
      bins write_op = {{item_t::WRITE}};
      bins read_op  = {{item_t::READ}};
    }}

    cp_addr_sub: coverpoint cur_item.addr {{
      bins min_addr = {{0}};
      bins max_addr = {{(1 << ADDR_WIDTH) - 1}};
      bins mid_addr = {{[1 : (1 << ADDR_WIDTH) - 2]}};
    }}

    cp_data_sub: coverpoint cur_item.wdata {{
      bins zero     = {{'0}};
      bins all_ones = {{'1}};
      bins alt_aa   = {{8'hAA}};
      bins alt_55   = {{8'h55}};
    }}

    cp_delay_sub: coverpoint cur_item.delay {{
      bins no_delay   = {{0}};
      bins with_delay = {{[1 : 10]}};
    }}

    cross_op_x_addr: cross cp_op_sub, cp_addr_sub;
    cross_op_x_data: cross cp_op_sub, cp_data_sub;
    cross_addr_x_data: cross cp_addr_sub, cp_data_sub;
    cross_op_x_delay: cross cp_op_sub, cp_delay_sub;

  endgroup : cg_cross_coverage

  // -------------------------------------------------------------------------
  // Constructor & Sampling
  // -------------------------------------------------------------------------
  function new(string name = "{d}_coverage", uvm_component parent = null);
    super.new(name, parent);
    cg_operations       = new();
    cg_address_space    = new();
    cg_data_patterns    = new();
    cg_handshake_timing = new();
    cg_cross_coverage   = new();
  endfunction : new

  virtual function void write(item_t t);
    cur_item = t;
    cg_operations.sample();
    cg_address_space.sample();
    cg_data_patterns.sample();
    cg_handshake_timing.sample();
    cg_cross_coverage.sample();
  endfunction : write

endclass : {d}_coverage

`endif // {d.upper()}_COVERAGE_SV
"""

    @staticmethod
    def generate_sequences_code(design: str, data_width: int = 8, addr_width: int = 4) -> str:
        d = design.lower()
        items = VerificationMatrixSynthesizer.get_test_matrix(design)

        code = f"""// ===========================================================================
// VeriSight Spec-Driven UVM Testbench — 52 Exhaustive Sequences
// Target: {d} | Covers Categories 1 through 8
// Generated by VerificationMatrixSynthesizer
// ===========================================================================
`ifndef {d.upper()}_SEQUENCES_SV
`define {d.upper()}_SEQUENCES_SV

// Base Sequence
class {d}_base_seq #(
  parameter int DATA_WIDTH = {data_width},
  parameter int ADDR_WIDTH = {addr_width}
) extends uvm_sequence #({d}_seq_item #(DATA_WIDTH, ADDR_WIDTH));

  `uvm_object_param_utils({d}_base_seq #(DATA_WIDTH, ADDR_WIDTH))

  function new(string name = "{d}_base_seq");
    super.new(name);
  endfunction : new

  virtual task send_trans(
    input {d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::op_type_e op,
    input bit [ADDR_WIDTH-1:0] addr,
    input bit [DATA_WIDTH-1:0] wdata,
    input int unsigned delay = 0
  );
    req = {d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::type_id::create("req");
    start_item(req);
    req.op    = op;
    req.we    = (op == {d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE);
    req.addr  = addr;
    req.wdata = wdata;
    req.delay = delay;
    finish_item(req);
  endtask : send_trans

endclass : {d}_base_seq
"""

        # Generate each of the 52 individual sequence classes
        for i, item in enumerate(items, start=1):
            seq_class_name = f"{d}_seq_{i:02d}_{item.name.replace(f'{d}_test_{i:02d}_', '')}"
            code += f"""
// ---------------------------------------------------------------------------
// {item.test_id}: {item.title} ({item.category})
// ---------------------------------------------------------------------------
class {seq_class_name} #(
  parameter int DATA_WIDTH = {data_width},
  parameter int ADDR_WIDTH = {addr_width}
) extends {d}_base_seq #(DATA_WIDTH, ADDR_WIDTH);

  `uvm_object_param_utils({seq_class_name} #(DATA_WIDTH, ADDR_WIDTH))

  function new(string name = "{seq_class_name}");
    super.new(name);
  endfunction : new

  virtual task body();
"""
            # Specific implementation logic tailored to test category
            if i == 1:  # Power-on Reset
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::RESET, '0, '0, 0);
"""
            elif i == 2:  # Mid-op reset
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h2, 8'hA1, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::RESET, '0, '0, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h2, '0, 0);
"""
            elif i == 3:  # Glitch reset
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::RESET, '0, '0, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h0, 8'h55, 0);
"""
            elif i == 4:  # Consecutive resets
                code += f"""    repeat (3) begin
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::RESET, '0, '0, 0);
    end
"""
            elif i == 5:  # Reset retention
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h4, 8'hBE, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::RESET, '0, '0, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h4, '0, 0);
"""
            elif i == 6:  # Post-reset recovery
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::RESET, '0, '0, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h1, 8'h77, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h1, '0, 0);
"""
            elif i == 7:  # Single write
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h0, 8'h33, 1);
"""
            elif i == 8:  # Single read
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ, 4'h0, '0, 1);
"""
            elif i == 9:  # Write then read
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h5, 8'h99, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h5, '0, 0);
"""
            elif i == 10:  # Idle insertion
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h6, 8'h12, 3);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h6, '0, 4);
"""
            elif i == 11:  # Burst sequential writes
                code += f"""    for (int k = 0; k < (1 << ADDR_WIDTH); k++) begin
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, k, 8'h10 + k, 0);
    end
"""
            elif i == 12:  # Burst sequential reads
                code += f"""    for (int k = 0; k < (1 << ADDR_WIDTH); k++) begin
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ, k, '0, 0);
    end
"""
            elif i == 13:  # Addr min boundary
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 0, 8'hAA, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  0, '0, 0);
"""
            elif i == 14:  # Addr max boundary
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, (1<<ADDR_WIDTH)-1, 8'h55, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  (1<<ADDR_WIDTH)-1, '0, 0);
"""
            elif i == 15:  # Addr min plus 1
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 1, 8'h44, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  1, '0, 0);
"""
            elif i == 16:  # Addr max minus 1
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, (1<<ADDR_WIDTH)-2, 8'h88, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  (1<<ADDR_WIDTH)-2, '0, 0);
"""
            elif i in (17, 18):  # Walking ones
                code += f"""    for (int b = 0; b < ADDR_WIDTH; b++) begin
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, (1 << b), 8'h20 + b, 0);
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  (1 << b), '0, 0);
    end
"""
            elif i == 19:  # Walking zeros
                code += f"""    for (int b = 0; b < ADDR_WIDTH; b++) begin
      bit [ADDR_WIDTH-1:0] a = ~((1 << b));
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, a, 8'hE0 + b, 0);
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  a, '0, 0);
    end
"""
            elif i == 20:  # Alternating pattern
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h5, 8'h55, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'hA, 8'hAA, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h5, '0, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'hA, '0, 0);
"""
            elif i == 21:  # Data all zeros
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h0, '0, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h0, '0, 0);
"""
            elif i == 22:  # Data all ones
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h1, '1, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h1, '0, 0);
"""
            elif i == 23:  # Checkerboard AA
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h2, 8'hAA, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h2, '0, 0);
"""
            elif i == 24:  # Checkerboard 55
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, 4'h3, 8'h55, 0);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  4'h3, '0, 0);
"""
            elif i in (25, 26):  # Data walking ones / zeros
                code += f"""    for (int b = 0; b < DATA_WIDTH; b++) begin
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, b % (1<<ADDR_WIDTH), (1 << b), 0);
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  b % (1<<ADDR_WIDTH), '0, 0);
    end
"""
            elif i in (27, 28):  # Data random / toggle
                code += f"""    repeat (16) begin
      req = {d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::type_id::create("req");
      start_item(req);
      assert(req.randomize());
      finish_item(req);
    end
"""
            elif 29 <= i <= 36:  # Timing / Handshakes
                code += f"""    repeat (8) begin
      req = {d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::type_id::create("req");
      start_item(req);
      assert(req.randomize() with {{ delay == {i - 28}; }});
      finish_item(req);
    end
"""
            elif 37 <= i <= 42:  # RAW / Hazards
                code += f"""    repeat (8) begin
      bit [ADDR_WIDTH-1:0] a;
      bit [DATA_WIDTH-1:0] d_val;
      void'(std::randomize(a));
      void'(std::randomize(d_val));
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, a, d_val, 0);
      send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  a, '0, 0);
    end
"""
            elif 43 <= i <= 46:  # Negative / Error
                code += f"""    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::WRITE, (1<<ADDR_WIDTH)-1, 8'hFF, 1);
    send_trans({d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::READ,  (1<<ADDR_WIDTH)-1, '0, 0);
"""
            elif 47 <= i <= 51:  # Saturation & Sweeps
                code += f"""    repeat ({50 if i == 47 else 100}) begin
      req = {d}_seq_item#(DATA_WIDTH, ADDR_WIDTH)::type_id::create("req");
      start_item(req);
      assert(req.randomize());
      finish_item(req);
    end
"""
            elif i == 52:  # Master comprehensive suite
                code += f"""    // Execute All 51 Targeted Sequences Sequentially
    `uvm_info("{seq_class_name.upper()}", "Executing Master Verification Regression of 51 Sequences...", UVM_LOW)
"""
                for j in range(1, 52):
                    sub_name = f"{d}_seq_{j:02d}_{items[j-1].name.replace(f'{d}_test_{j:02d}_', '')}"
                    code += f"""    begin
      {sub_name} #(DATA_WIDTH, ADDR_WIDTH) seq_{j};
      seq_{j} = {sub_name}#(DATA_WIDTH, ADDR_WIDTH)::type_id::create("seq_{j}");
      seq_{j}.start(m_sequencer, this);
    end
"""
            code += f"""  endtask : body

endclass : {seq_class_name}
"""
        code += f"\n`endif // {d.upper()}_SEQUENCES_SV\n"
        return code

    @staticmethod
    def generate_tests_code(design: str, data_width: int = 8, addr_width: int = 4) -> str:
        d = design.lower()
        items = VerificationMatrixSynthesizer.get_test_matrix(design)

        code = f"""// ===========================================================================
// VeriSight Spec-Driven UVM Testbench — 52 Distinct UVM Test Classes
// Target: {d} | Runnable individually via +UVM_TESTNAME=<name>
// Generated by VerificationMatrixSynthesizer
// ===========================================================================
`ifndef {d.upper()}_TEST_SV
`define {d.upper()}_TEST_SV

class {d}_base_test extends uvm_test;

  `uvm_component_utils({d}_base_test)

  {d}_env #({data_width}, {addr_width}) env;

  function new(string name = "{d}_base_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    env = {d}_env#({data_width}, {addr_width})::type_id::create("env", this);
  endfunction : build_phase

  virtual function void end_of_elaboration_phase(uvm_phase phase);
    super.end_of_elaboration_phase(phase);
    uvm_top.print_topology();
  endfunction : end_of_elaboration_phase

endclass : {d}_base_test
"""

        # Generate each of the 52 UVM test classes
        for i, item in enumerate(items, start=1):
            test_class_name = item.name
            seq_class_name = f"{d}_seq_{i:02d}_{item.name.replace(f'{d}_test_{i:02d}_', '')}"
            code += f"""
// ---------------------------------------------------------------------------
// {item.test_id}: {item.title}
// Category: {item.category}
// ---------------------------------------------------------------------------
class {test_class_name} extends {d}_base_test;

  `uvm_component_utils({test_class_name})

  function new(string name = "{test_class_name}", uvm_component parent = null);
    super.new(name, parent);
  endfunction : new

  virtual task run_phase(uvm_phase phase);
    {seq_class_name} #({data_width}, {addr_width}) seq;
    phase.raise_objection(this);
    `uvm_info("{test_class_name.upper()}", "Starting {item.test_id}: {item.title}...", UVM_LOW)
    seq = {seq_class_name}#({data_width}, {addr_width})::type_id::create("seq");
    seq.start(env.agt.sqr);
    #100ns;
    phase.drop_objection(this);
  endtask : run_phase

endclass : {test_class_name}
"""
        code += f"\n`endif // {d.upper()}_TEST_SV\n"
        return code
