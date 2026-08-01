// =============================================================================
// ALU Scoreboard
// =============================================================================

class alu_scoreboard extends uvm_scoreboard;
    `uvm_component_utils(alu_scoreboard)

    uvm_analysis_imp #(alu_seq_item, alu_scoreboard) analysis_export;

    int pass_count = 0;
    int fail_count = 0;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        analysis_export = new("analysis_export", this);
    endfunction

    // Prediction and comparison logic
    virtual function void write(alu_seq_item txn);
        logic [8:0] expected_out;
        logic [7:0] expected_result;
        logic       expected_carry;
        logic       expected_zero;

        // Compute expected result
        case (txn.op_sel)
            4'b0000: expected_out = {1'b0, txn.operand_a} + {1'b0, txn.operand_b};
            4'b0001: expected_out = {1'b0, txn.operand_a} - {1'b0, txn.operand_b};
            4'b0010: expected_out = {1'b0, txn.operand_a & txn.operand_b};
            4'b0011: expected_out = {1'b0, txn.operand_a | txn.operand_b};
            4'b0100: expected_out = {1'b0, txn.operand_a ^ txn.operand_b};
            4'b0101: expected_out = {1'b0, ~txn.operand_a};
            4'b0110: expected_out = {1'b0, txn.operand_a} << txn.operand_b[2:0];
            4'b0111: expected_out = {1'b0, txn.operand_a >> txn.operand_b[2:0]};
            default: expected_out = 9'b0;
        endcase

        expected_result = expected_out[7:0];
        expected_carry  = expected_out[8];
        expected_zero   = (expected_result == 8'h00);

        // Compare
        if (txn.result !== expected_result ||
            txn.carry !== expected_carry ||
            txn.zero !== expected_zero) begin

            `uvm_error("SCB", $sformatf(
                "MISMATCH: op=%0h a=%0h b=%0h | expected result=%0h carry=%0b zero=%0b | actual result=%0h carry=%0b zero=%0b",
                txn.op_sel, txn.operand_a, txn.operand_b,
                expected_result, expected_carry, expected_zero,
                txn.result, txn.carry, txn.zero))
            fail_count++;
        end else begin
            `uvm_info("SCB", $sformatf("PASS: %s", txn.convert2string()), UVM_HIGH)
            pass_count++;
        end
    endfunction

    function void report_phase(uvm_phase phase);
        `uvm_info("SCB", $sformatf("Scoreboard Summary: PASS=%0d FAIL=%0d", pass_count, fail_count), UVM_LOW)
    endfunction
endclass
