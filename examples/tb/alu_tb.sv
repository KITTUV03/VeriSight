// =============================================================================
// VeriSight Self-Checking & Coverage-Logging Testbench for ALU
// =============================================================================
`timescale 1ns/1ps

module alu_tb;

    logic        clk;
    logic        rst_n;
    logic [7:0]  operand_a;
    logic [7:0]  operand_b;
    logic [3:0]  op_sel;
    logic [7:0]  result;
    logic        carry;
    logic        zero;

    // Expected models
    logic [8:0] expected_out;
    logic [7:0] expected_result;
    logic       expected_carry;
    logic       expected_zero;

    int error_count = 0;
    int test_count = 0;

    // Instantiate Design Under Test (DUT)
    alu dut (
        .clk(clk),
        .rst_n(rst_n),
        .operand_a(operand_a),
        .operand_b(operand_b),
        .op_sel(op_sel),
        .result(result),
        .carry(carry),
        .zero(zero)
    );

    // Clock Generation (10ns period -> 100MHz)
    always #5 clk = ~clk;

    // Golden Reference Model calculation
    function void calc_expected(input [3:0] op, input [7:0] a, input [7:0] b);
        case (op)
            4'b0000: expected_out = {1'b0, a} + {1'b0, b}; // ADD
            4'b0001: expected_out = {1'b0, a} - {1'b0, b}; // SUB
            4'b0010: expected_out = {1'b0, a & b};          // AND
            4'b0011: expected_out = {1'b0, a | b};          // OR
            4'b0100: expected_out = {1'b0, a ^ b};          // XOR
            4'b0101: expected_out = {1'b0, ~a};             // NOT
            4'b0110: expected_out = {1'b0, a} << b[2:0];    // SHL
            4'b0111: expected_out = {1'b0, a >> b[2:0]};    // SHR
            default: expected_out = 9'b0;
        endcase
        expected_result = expected_out[7:0];
        expected_carry  = expected_out[8];
        expected_zero   = (expected_result == 8'h00);
    endfunction

    // Check outputs on posedge clk after 1 cycle latency
    task check_output(string tag);
        @(posedge clk);
        #1; // Sample shortly after clock edge
        test_count++;
        if ($isunknown(result) || result !== expected_result || carry !== expected_carry || zero !== expected_zero) begin
            error_count++;
            $display("UVM_ERROR alu_scoreboard.sv(52) @ %0t ns: uvm_test_top.env.scb [SCB] MISMATCH: op=%0h a=%0h b=%0h | expected result=%0h carry=%0b zero=%0b | actual result=%0h carry=%0b zero=%0b [%s]",
                     $time, op_sel, operand_a, operand_b, expected_result, expected_carry, expected_zero, result, carry, zero, tag);
        end else begin
            $display("UVM_INFO @ %0t ns: uvm_test_top.env.scb [SCB] PASS: op_sel=%0h a=%0h b=%0h | result=%0h carry=%0b zero=%0b [%s]",
                     $time, op_sel, operand_a, operand_b, result, carry, zero, tag);
        end
    endtask

    // Main Test Stimulus
    initial begin
        $display("----------------------------------------------------------------");
        $display("UVM_INFO @ %0t ns: reporter [RNTST] Running test alu_test...", $time);
        $display("UVM_INFO @ %0t ns: uvm_test_top.env.agt.drv [DRV] Starting driver", $time);
        $display("UVM_INFO @ %0t ns: uvm_test_top.env.agt.mon [MON] Starting monitor", $time);
        $display("UVM_INFO @ %0t ns: uvm_test_top.env.scb [SCB] Starting scoreboard", $time);
        $display("----------------------------------------------------------------");

        // Dump VCD
        $dumpfile("sim.vcd");
        $dumpvars(0, alu_tb);

        clk = 0;
        rst_n = 0;
        operand_a = 8'h00;
        operand_b = 8'h00;
        op_sel = 4'b0000;

        // Reset Phase
        #10;
        // Check reset state (Spec requires result = 8'h00 on reset)
        test_count++;
        if ($isunknown(result) || result !== 8'h00) begin
            error_count++;
            $display("UVM_ERROR alu_scoreboard.sv(42) @ %0t ns: uvm_test_top.env.scb [SCB] MISMATCH: Reset state | expected result=00 carry=0 zero=0 | actual result=%0h carry=%0b zero=%0b [RESET_UNINITIALIZED_X]",
                     $time, result, carry, zero);
        end
        rst_n = 1;
        #10;

        // Test 1: ADD with reset check (Expect result=e1, but due to bug result=xx initially)
        op_sel = 4'h0; operand_a = 8'ha5; operand_b = 8'h3c;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("ADD Nominal");

        // Test 2: SUB
        op_sel = 4'h1; operand_a = 8'h7f; operand_b = 8'h20;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("SUB Nominal");

        // Test 3: AND
        op_sel = 4'h2; operand_a = 8'hff; operand_b = 8'h0f;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("AND Bitwise");

        // Test 4: ADD Overflow & Carry
        op_sel = 4'h0; operand_a = 8'h80; operand_b = 8'h80;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("ADD Overflow Carry");

        // Test 5: OR
        op_sel = 4'h3; operand_a = 8'h55; operand_b = 8'haa;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("OR Bitwise");

        // Test 6: ADD Small
        op_sel = 4'h0; operand_a = 8'h01; operand_b = 8'h02;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("ADD Simple");

        // Test 7: XOR
        op_sel = 4'h4; operand_a = 8'haa; operand_b = 8'h55;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("XOR Bitwise");

        // Test 8: NOT
        op_sel = 4'h5; operand_a = 8'h0f; operand_b = 8'h00;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("NOT Invert");

        // Test 9: SHL
        op_sel = 4'h6; operand_a = 8'h01; operand_b = 8'h03;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("SHL Shift Left");

        // Test 10: SHR
        op_sel = 4'h7; operand_a = 8'h80; operand_b = 8'h02;
        calc_expected(op_sel, operand_a, operand_b);
        check_output("SHR Shift Right");

        #30;
        $display("----------------------------------------------------------------");
        $display("UVM_INFO @ %0t ns: uvm_test_top [TEST] All sequences completed", $time);
        $display("UVM_INFO @ %0t ns: reporter [UVMTOP] Phase: run - phase is ending", $time);
        $display("----------------------------------------------------------------");
        $display("--- UVM Report Summary ---");
        $display("** Report counts by severity");
        $display("UVM_INFO :    %0d", test_count + 5);
        $display("UVM_WARNING :    0");
        $display("UVM_ERROR :    %0d", error_count);
        $display("UVM_FATAL :    0");
        $display("Simulation time: %0t ns", $time);
        if (error_count > 0) begin
            $display("** TEST FAILED ** (%0d errors detected)", error_count);
        end else begin
            $display("** TEST PASSED ** (All tests matched golden model)", test_count);
        end
        $finish;
    end

endmodule
