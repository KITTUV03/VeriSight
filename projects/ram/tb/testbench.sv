`include "uvm_macros.svh"
`include "ram_package.sv"
`include "ram_interface.sv"
module tb;
  import uvm_pkg::*;
  import ram_pkg::*;   // make sure package name is correct

  // Clock
  bit clk;
  always #5 clk = ~clk;

  // Interface
  ram_if inf();

  // Connect clock
  assign inf.clk = clk;

  ram_rtl dut (
    .clk   (inf.clk),
    .rst_n (inf.rst_n),
    .we    (inf.we),
    .addr  (inf.addr),
    .wdata (inf.wdata),
    .rdata (inf.rdata)
  );
  
  initial begin
    uvm_config_db #(virtual ram_if)::set(null,"*","inf",inf);
  end
 
  initial begin
//     inf.rst_n=1;
    run_test("ram_test");
  end
  
  initial begin
    $dumpfile("dump.vcd");
    $dumpvars;
  end

endmodule
