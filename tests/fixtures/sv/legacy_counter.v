// Legacy Verilog-2001 style (reg, non-ANSI-ish, always @) — must still parse.
module legacy_counter (clk, rst, en, count);
    input        clk;
    input        rst;
    input        en;
    output [3:0] count;

    reg [3:0] count;

    always @(posedge clk or posedge rst) begin
        if (rst)
            count <= 4'b0000;
        else if (en)
            count <= count + 1'b1;
    end
endmodule
