module ram_rtl #(
  parameter DATA_WIDTH = 8,
  parameter ADDR_WIDTH = 4   // Depth = 2^ADDR_WIDTH
)(
  input  logic                     clk,
  input  logic                     rst_n,
  input  logic                     we,      // write enable
  input  logic [ADDR_WIDTH-1:0]    addr,
  input  logic [DATA_WIDTH-1:0]    wdata,
  output logic [DATA_WIDTH-1:0]    rdata
);

  // Memory declaration
  logic [DATA_WIDTH-1:0] mem [0:(1<<ADDR_WIDTH)-1];

  // Sequential logic
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      rdata <= '0;
    end
    else begin
      // Write operation
      if (we) begin
        mem[addr] <= wdata;
      end
      else begin

      // Read operation (synchronous read)
        rdata <= mem[addr+1];
      end
    end
  end

endmodule
