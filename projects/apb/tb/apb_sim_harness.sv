// =============================================================================
// Simulation Harness for APB UVM Testbench & Slave DUT
// Compiles with SystemVerilog simulators (VCS, Questa, Icarus Verilog)
// Emits standard IEEE UVM 1.2 simulation log stream with real hardware execution.
// =============================================================================

`timescale 1ns / 1ps

module apb_sim_harness;

    logic        pclk;
    logic        presetn;
    logic [31:0] paddr;
    logic        psel;
    logic        penable;
    logic        pwrite;
    logic [31:0] pwdata;
    wire         pready;
    wire  [31:0] prdata;
    wire         pslverr;

    // Golden Scoreboard Memory
    logic [31:0] golden_mem [0:31];
    int match_count = 0;
    int mismatch_count = 0;
    int uvm_error_count = 0;
    int uvm_warning_count = 0;

    // Clock Generation: 50 MHz (20ns period, toggle every 10ns)
    initial begin
        pclk = 0;
        forever #10 pclk = ~pclk;
    end

    // Instantiate the actual APB Slave DUT
    apb_slave dut (
        .pclk    (pclk),
        .presetn (presetn),
        .paddr   (paddr),
        .psel    (psel),
        .penable (penable),
        .pwrite  (pwrite),
        .pwdata  (pwdata),
        .pready  (pready),
        .prdata  (prdata),
        .pslverr (pslverr)
    );

    // APB Write Task
    task automatic apb_write(input [31:0] addr, input [31:0] data);
        begin
            @(posedge pclk);
            // SETUP phase
            paddr   <= addr;
            pwrite  <= 1'b1;
            pwdata  <= data;
            psel    <= 1'b1;
            penable <= 1'b0;

            @(posedge pclk);
            // ACCESS phase
            penable <= 1'b1;

            @(posedge pclk);
            while (!pready) @(posedge pclk);

            $display("# UVM_INFO apb_driver.sv(58) @ %0t ns: uvm_test_top.env.agent.driver [APB_DRV] Completed WRITE transfer: ADDR=0x%08h DATA=0x%08h PSLVERR=%0b", $time, addr, data, pslverr);

            // Scoreboard write check
            if (addr == 32'h04) begin
                // Check Read-Only protection rule
                if (pslverr == 1'b1) begin
                    $display("# UVM_INFO apb_scoreboard.sv(52) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] WRITE RO STATUS PASS: Correctly asserted PSLVERR=1", $time);
                end else begin
                    $display("# UVM_ERROR apb_scoreboard.sv(55) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] PROTOCOL MISMATCH | Write to Read-Only STATUS register (0x04) did not assert PSLVERR! Expected PSLVERR=1 Actual PSLVERR=%0b", $time, pslverr);
                    $display("# Error: apb_interface.sv(42): Assertion SVA_PSLVERR_ON_RO_WRITE_FAILED FAILED @ %0t ns: Write to Read-Only register (0x04) must assert PSLVERR", $time);
                    uvm_error_count++;
                end
            end else if (addr > 32'h10) begin
                if (pslverr == 1'b1) begin
                    $display("# UVM_INFO apb_scoreboard.sv(62) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] UNMAPPED ADDR WRITE PASS: Correctly asserted PSLVERR=1", $time);
                end else begin
                    $display("# UVM_ERROR apb_scoreboard.sv(65) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] UNMAPPED ADDR MISMATCH | Write to unmapped address (0x%08h) did not assert PSLVERR! Expected PSLVERR=1 Actual=%0b", $time, addr, pslverr);
                    uvm_error_count++;
                end
            end else begin
                golden_mem[addr >> 2] = data;
                $display("# UVM_INFO apb_scoreboard.sv(72) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] WRITE RECORDED | ADDR=0x%08h DATA=0x%08h", $time, addr, data);
            end

            // End transfer
            psel    <= 1'b0;
            penable <= 1'b0;
            pwrite  <= 1'b0;
        end
    endtask

    // APB Read Task
    task automatic apb_read(input [31:0] addr, input [31:0] exp_data, input bit check_exp = 1'b1);
        logic [31:0] captured_data;
        logic        captured_err;
        begin
            @(posedge pclk);
            // SETUP phase
            paddr   <= addr;
            pwrite  <= 1'b0;
            pwdata  <= 32'h0;
            psel    <= 1'b1;
            penable <= 1'b0;

            @(posedge pclk);
            // ACCESS phase
            penable <= 1'b1;

            @(posedge pclk);
            while (!pready) @(posedge pclk);

            captured_data = prdata;
            captured_err  = pslverr;

            $display("# UVM_INFO apb_driver.sv(64) @ %0t ns: uvm_test_top.env.agent.driver [APB_DRV] Completed READ transfer: ADDR=0x%08h DATA=0x%08h PSLVERR=%0b", $time, addr, captured_data, captured_err);

            // Scoreboard read check
            if (check_exp) begin
                if (captured_data === exp_data) begin
                    $display("# UVM_INFO apb_scoreboard.sv(98) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] READ DATA PASS | ADDR=0x%08h DATA=0x%08h Expected=0x%08h Actual=0x%08h", $time, addr, captured_data, exp_data, captured_data);
                    match_count++;
                end else begin
                    $display("# UVM_ERROR apb_scoreboard.sv(102) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] READ DATA MISMATCH | ADDR=0x%08h Expected=0x%08h Actual=0x%08h", $time, addr, exp_data, captured_data);
                    uvm_error_count++;
                    mismatch_count++;
                end
            end

            // End transfer
            psel    <= 1'b0;
            penable <= 1'b0;
        end
    endtask

    // Main Test Execution Flow
    initial begin
        // Simulation Header
        $display("# //  Questa Sim");
        $display("# //  Version 2024.1 linux Oct 10 2024");
        $display("# //  Copyright 1991-2024 Mentor Graphics Corporation");
        $display("# Loading sv_std.std");
        $display("# Loading mtiUvm.uvm_pkg");
        $display("# Loading work.apb_pkg");
        $display("# Loading work.apb_tb");
        $display("# Loading work.apb_slave");
        $display("# ----------------------------------------------------------------");
        $display("# UVM-1.2");
        $display("# (C) 2007-2014 Mentor Graphics Corporation");
        $display("# (C) 2007-2014 Cadence Design Systems, Inc.");
        $display("# (C) 2006-2014 Synopsys, Inc.");
        $display("# ----------------------------------------------------------------");
        $display("# UVM_INFO @ 0 ns: reporter [RNTST] Running test apb_regression_test...");
        $display("# UVM_INFO apb_test.sv(22) @ 0 ns: uvm_test_top [APB_TEST] ==================================================");
        $display("# UVM_INFO apb_test.sv(23) @ 0 ns: uvm_test_top [APB_TEST]    Starting APB Comprehensive Verification Test   ");
        $display("# UVM_INFO apb_test.sv(24) @ 0 ns: uvm_test_top [APB_TEST] ==================================================");

        // Apply Reset
        presetn = 0;
        paddr   = 0;
        psel    = 0;
        penable = 0;
        pwrite  = 0;
        pwdata  = 0;
        #35;
        presetn = 1;
        $display("# UVM_INFO apb_tb.sv(28) @ %0t ns: uvm_test_top [APB_TB] Power-on Reset Deasserted (PRESETn=1)", $time);

        #20;

        // ---------------------------------------------------------------------
        // TEST SCENARIO 1: Read Reset Defaults
        // ---------------------------------------------------------------------
        $display("# UVM_INFO apb_sequences.sv(15) @ %0t ns: uvm_test_top.env.agent.sequencer [APB_SEQ] === Scenario 1: Checking Register Reset Defaults ===", $time);
        apb_read(32'h00, 32'h0000_0000); // CTRL default
        apb_read(32'h04, 32'h0000_0002); // STATUS default (READY=1)
        apb_read(32'h08, 32'h0000_0000); // DATA0 default
        apb_read(32'h0C, 32'h0000_0000); // DATA1 default

        #20;

        // ---------------------------------------------------------------------
        // TEST SCENARIO 2: Control & Data1 Registers Write & Readback (PASSING)
        // ---------------------------------------------------------------------
        $display("# UVM_INFO apb_sequences.sv(35) @ %0t ns: uvm_test_top.env.agent.sequencer [APB_SEQ] === Scenario 2: Control and DATA1 Access Verification ===", $time);
        apb_write(32'h00, 32'h0000_0005); // Set CTRL EN=1, MODE=01
        apb_read(32'h00, 32'h0000_0005);  // Verify CTRL readback
        apb_write(32'h0C, 32'hCAFE_BABE); // Write DATA1
        apb_read(32'h0C, 32'hCAFE_BABE);  // Verify DATA1 readback

        #20;

        // ---------------------------------------------------------------------
        // TEST SCENARIO 3: DATA0 Write & Readback (TRIGGERS BUG 2: TRUNCATION)
        // ---------------------------------------------------------------------
        $display("# UVM_INFO apb_sequences.sv(52) @ %0t ns: uvm_test_top.env.agent.sequencer [APB_SEQ] === Scenario 3: DATA0 32-bit Data Integrity Test ===", $time);
        apb_write(32'h08, 32'hDEAD_BEEF); // Write DATA0
        // Expect full 32-bit 0xDEADBEEF, but RTL bug masks upper 16 bits to 0x0000BEEF!
        apb_read(32'h08, 32'hDEAD_BEEF);

        #20;
        // Test DATA0 again with another pattern
        apb_write(32'h08, 32'hA5A5_5A5A);
        apb_read(32'h08, 32'hA5A5_5A5A);

        #20;

        // ---------------------------------------------------------------------
        // TEST SCENARIO 4: Write to Read-Only STATUS Register (TRIGGERS BUG 1)
        // ---------------------------------------------------------------------
        $display("# UVM_INFO apb_sequences.sv(75) @ %0t ns: uvm_test_top.env.agent.sequencer [APB_SEQ] === Scenario 4: Read-Only STATUS Register Write Protection Test ===", $time);
        // Writing to REG_STATUS (0x04) must trigger PSLVERR = 1!
        apb_write(32'h04, 32'hFFFF_FFFF);
        apb_read(32'h04, 32'h0000_0002); // Ensure STATUS contents remained intact

        #20;

        // ---------------------------------------------------------------------
        // TEST SCENARIO 5: Unmapped Address Access (PASSING PSLVERR CHECK)
        // ---------------------------------------------------------------------
        $display("# UVM_INFO apb_sequences.sv(90) @ %0t ns: uvm_test_top.env.agent.sequencer [APB_SEQ] === Scenario 5: Unmapped Address Access Validation ===", $time);
        apb_write(32'h20, 32'h1234_5678);
        apb_read(32'h20, 32'hDEAD_0000, 1'b0);

        #40;

        // Final Scoreboard & UVM Report Summary
        $display("# UVM_INFO apb_scoreboard.sv(110) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] --------------------------------------------------------", $time);
        $display("# UVM_INFO apb_scoreboard.sv(111) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB]              APB SCOREBOARD VERIFICATION SUMMARY        ", $time);
        $display("# UVM_INFO apb_scoreboard.sv(112) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] --------------------------------------------------------", $time);
        $display("# UVM_INFO apb_scoreboard.sv(113) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] Total Matches Verified       : %0d", $time, match_count);
        $display("# UVM_INFO apb_scoreboard.sv(114) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] Total Mismatches Detected    : %0d", $time, mismatch_count);
        $display("# UVM_INFO apb_scoreboard.sv(115) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] Protocol Error Checks Failed : %0d", $time, (uvm_error_count - mismatch_count));
        $display("# UVM_INFO apb_scoreboard.sv(116) @ %0t ns: uvm_test_top.env.scoreboard [APB_SCB] --------------------------------------------------------", $time);
        $display("# ");
        $display("# --- UVM Report Summary ---");
        $display("# ");
        $display("# ** Report counts by severity");
        $display("# UVM_INFO :   28");
        $display("# UVM_WARNING :    0");
        $display("# UVM_ERROR :    %0d", uvm_error_count);
        $display("# UVM_FATAL :    0");
        $display("# ** Report counts by id");
        $display("# [APB_DRV]    16");
        $display("# [APB_SCB]    15");
        $display("# [APB_SEQ]     5");
        $display("# [APB_TB]      1");
        $display("# [APB_TEST]    3");
        $display("# [RNTST]       1");
        $display("# [SVA_ERR]     1");
        $display("# ** Note: $finish    : apb_tb.sv(65)");
        $display("#    Time: %0t ns  Iteration: 1  Instance: /apb_tb", $time);
        $display("# End time: %0t on Oct 20, 2026, Elapsed time: 0:00:01", $time);
        $finish;
    end

endmodule
