`ifndef RAM_INF
`define RAM_INF
interface ram_if(input clk);
  logic rst_n;
  logic we;
  logic [`ADDR_WIDTH-1:0] addr;
  logic [`DATA_WIDTH-1:0] wdata;
  logic [`DATA_WIDTH-1:0] rdata;
  
  
  clocking drv_cb @(posedge clk);
    default input #1 output #0;
    output we,addr,wdata,rst_n;
    input rdata;
  endclocking
  
   clocking mon_cb @(posedge clk);
    default input #1 output #0;
    input we,addr,wdata;
    input rdata,rst_n;
  endclocking
  
  
endinterface
`endif