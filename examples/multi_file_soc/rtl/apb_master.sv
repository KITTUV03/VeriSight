// APB Master interface generator
module apb_master (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        start_xfer,
    input  logic [31:0] in_addr,
    input  logic [31:0] in_wdata,
    output logic [31:0] paddr,
    output logic        psel,
    output logic        penable,
    output logic        pwrite,
    output logic [31:0] pwdata,
    input  logic [31:0] prdata,
    input  logic        pready,
    output logic [31:0] out_rdata
);
    typedef enum logic [1:0] {
        IDLE   = 2'b00,
        SETUP  = 2'b01,
        ACCESS = 2'b10
    } apb_state_e;

    apb_state_e state_q;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= IDLE;
            psel <= 1'b0;
            penable <= 1'b0;
            paddr <= 32'h0;
            pwdata <= 32'h0;
            pwrite <= 1'b0;
            out_rdata <= 32'h0;
        end else begin
            case (state_q)
                IDLE: begin
                    penable <= 1'b0;
                    if (start_xfer) begin
                        state_q <= SETUP;
                        psel <= 1'b1;
                        paddr <= in_addr;
                        pwdata <= in_wdata;
                        pwrite <= 1'b1;
                    end else begin
                        psel <= 1'b0;
                    end
                end
                SETUP: begin
                    state_q <= ACCESS;
                    penable <= 1'b1;
                end
                ACCESS: begin
                    if (pready) begin
                        state_q <= IDLE;
                        psel <= 1'b0;
                        penable <= 1'b0;
                        out_rdata <= prdata;
                    end
                end
                default: state_q <= IDLE;
            endcase
        end
    end

endmodule

