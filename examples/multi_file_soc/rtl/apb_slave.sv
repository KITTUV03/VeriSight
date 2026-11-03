// APB Slave register file
module apb_slave (
    input  logic        pclk,
    input  logic        presetn,
    input  logic [31:0] paddr,
    input  logic        psel,
    input  logic        penable,
    input  logic        pwrite,
    input  logic [31:0] pwdata,
    output logic [31:0] prdata,
    output logic        pready,
    output logic [31:0] reg_ctrl
);
    logic [31:0] storage [0:3];

    always_ff @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            storage[0] <= 32'h0;
            storage[1] <= 32'h0;
            storage[2] <= 32'h0;
            storage[3] <= 32'h0;
        end else if (psel && penable && pwrite) begin
            storage[paddr[3:2]] <= pwdata;
        end
    end

    assign prdata = (psel && !pwrite) ? storage[paddr[3:2]] : 32'h0;
    assign pready = 1'b1;
    assign reg_ctrl = storage[0];

endmodule

