// Deliberately malformed: missing ')' and a dangling assign.
module bad_syntax (
    input logic clk,
    input logic a
;
    logic b;
    assign b = ;
    always_ff @(posedge clk) b <= a
endmodule
