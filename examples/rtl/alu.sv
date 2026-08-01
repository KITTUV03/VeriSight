// =============================================================================
// ALU RTL Design
// INTENTIONAL BUG: result register is NEVER reset — causes X propagation
// =============================================================================

module alu (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [7:0]  operand_a,
    input  logic [7:0]  operand_b,
    input  logic [3:0]  op_sel,
    output logic [7:0]  result,
    output logic        carry,
    output logic        zero
);

    // Internal combinational result
    logic [8:0] alu_out;  // 9-bit to capture carry
    logic       zero_next;

    // Combinational ALU logic
    always_comb begin
        alu_out = 9'b0;
        case (op_sel)
            4'b0000: alu_out = {1'b0, operand_a} + {1'b0, operand_b}; // ADD
            4'b0001: alu_out = {1'b0, operand_a} - {1'b0, operand_b}; // SUB
            4'b0010: alu_out = {1'b0, operand_a & operand_b};          // AND
            4'b0011: alu_out = {1'b0, operand_a | operand_b};          // OR
            4'b0100: alu_out = {1'b0, operand_a ^ operand_b};          // XOR
            4'b0101: alu_out = {1'b0, ~operand_a};                     // NOT
            4'b0110: alu_out = {1'b0, operand_a} << operand_b[2:0];    // SHL
            4'b0111: alu_out = {1'b0, operand_a >> operand_b[2:0]};    // SHR
            default: alu_out = 9'b0;
        endcase
        zero_next = (alu_out[7:0] == 8'h00);
    end

    // Sequential output register
    // BUG: Missing reset for 'result' register!
    // The spec requires result = 8'h00 on reset, but this block
    // does not reset 'result', causing X propagation from time 0.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // BUG: 'result' is NOT reset here!
            carry <= 1'b0;
            zero  <= 1'b0;
        end else begin
            result <= alu_out[7:0];
            carry  <= alu_out[8];
            zero   <= zero_next;
        end
    end

endmodule
