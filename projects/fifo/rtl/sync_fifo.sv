//=============================================================================
// Module: sync_fifo_err
// Description: Synchronous FIFO with INTENTIONAL ERRORS for UVM verification
//=============================================================================

module sync_fifo #(
    parameter DATA_WIDTH = 8,
    parameter ADDR_WIDTH = 4,
    parameter DEPTH      = 16,
    parameter FWFT_MODE  = 0,
    parameter AF_LEVEL   = 14,
    parameter AE_LEVEL   = 2,
    parameter REG_OUTPUT = 0
)(
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     wr_en,
    input  wire [DATA_WIDTH-1:0]    din,
    input  wire                     rd_en,
    output logic [DATA_WIDTH-1:0]   dout,
    output logic                    full,
    output logic                    empty,
    output logic                    almost_full,
    output logic                    almost_empty,
    output logic                    overflow,
    output logic                    underflow,
    output logic [ADDR_WIDTH:0]     wr_count,
    output logic [ADDR_WIDTH:0]     rd_count
);

    localparam FIFO_DEPTH = (1 << ADDR_WIDTH);
    
    logic [DATA_WIDTH-1:0] mem [0:FIFO_DEPTH-1];
    logic [ADDR_WIDTH:0] wr_ptr;
    logic [ADDR_WIDTH:0] rd_ptr;
    logic [ADDR_WIDTH:0] wr_ptr_next;
    logic [ADDR_WIDTH:0] rd_ptr_next;
    logic wr_en_valid;
    logic rd_en_valid;
    logic [ADDR_WIDTH:0] fifo_count;
    
    assign wr_en_valid = wr_en && !full;
    assign rd_en_valid = rd_en && !empty;
    assign wr_ptr_next = wr_ptr + 1'b1;
    assign rd_ptr_next = rd_ptr + 1'b1;
    
    // Pointer update
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= '0;
            rd_ptr <= '0;
        end else begin
            if (wr_en_valid) wr_ptr <= wr_ptr_next;
            if (rd_en_valid) rd_ptr <= rd_ptr_next;
        end
    end
    
    // Memory write
    always_ff @(posedge clk) begin
        if (wr_en_valid) begin
            mem[wr_ptr[ADDR_WIDTH-1:0]] <= din;
        end
    end
    
    assign fifo_count = wr_ptr - rd_ptr;
    
    // Status flags - CONTAINS ERRORS
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            full         <= 1'b0;
            empty        <= 1'b1;
            almost_full  <= 1'b0;
            almost_empty <= 1'b1;
            overflow     <= 1'b0;
            underflow    <= 1'b0;
        end else begin
            full <= (wr_ptr_next[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]);
            empty <= (wr_ptr_next == rd_ptr_next);

            almost_full <= (fifo_count > AF_LEVEL);          
            almost_empty <= (fifo_count <= AE_LEVEL);

            overflow  <= wr_en && full;
            underflow <= rd_en && empty;
        end
    end

    generate
        if (FWFT_MODE == 1) begin : fwft_output
            logic [DATA_WIDTH-1:0] dout_reg;
            
            always_ff @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    dout_reg <= '0;
                end else begin
                        if (rd_en_valid || empty) begin
                        dout_reg <= mem[rd_ptr[ADDR_WIDTH-1:0]];
                    end
                end
            end
            assign dout = dout_reg;
        end else begin : standard_output
            assign dout = mem[rd_ptr[ADDR_WIDTH-1:0]];
        end
    endgenerate
    
    assign wr_count = fifo_count;
    assign rd_count = fifo_count;
    
endmodule