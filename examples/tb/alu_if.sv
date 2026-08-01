// =============================================================================
// ALU Interface
// =============================================================================

interface alu_if (input logic clk, input logic rst_n);
    logic [7:0] operand_a;
    logic [7:0] operand_b;
    logic [3:0] op_sel;
    logic [7:0] result;
    logic       carry;
    logic       zero;

    // Driver clocking block
    clocking driver_cb @(posedge clk);
        default input #1 output #1;
        output operand_a;
        output operand_b;
        output op_sel;
        input  result;
        input  carry;
        input  zero;
    endclocking

    // Monitor clocking block
    clocking monitor_cb @(posedge clk);
        default input #1;
        input operand_a;
        input operand_b;
        input op_sel;
        input result;
        input carry;
        input zero;
    endclocking

    modport driver_mp (clocking driver_cb, input clk, input rst_n);
    modport monitor_mp (clocking monitor_cb, input clk, input rst_n);
endinterface
