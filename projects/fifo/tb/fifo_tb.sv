// ██╗  ██╗██╗████████╗████████╗██╗   ██╗
// ██║ ██╔╝██║╚══██╔══╝╚══██╔══╝██║   ██║
// █████╔╝ ██║   ██║      ██║   ██║   ██║
// ██╔═██╗ ██║   ██║      ██║   ██║   ██║
// ██║  ██╗██║   ██║      ██║   ╚██████╔╝
// ╚═╝  ╚═╝╚═╝   ╚═╝      ╚═╝    ╚═════╝
//
//                 ██████╗  █████╗ ████████╗███████╗██╗
//                 ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║
//                 ██████╔╝███████║   ██║   █████╗  ██║
//                 ██╔═══╝ ██╔══██║   ██║   ██╔══╝  ██║
//                 ██║     ██║  ██║   ██║   ███████╗███████╗
//                 ╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝

 `include "sync_fifo.sv"
//`include "assertion.sv"
`include "uvm_macros.svh"
`include "fifo_package.sv"

module tb;
  import uvm_pkg::*;
  import fifo_pkg::*;

  bit CLK;
  bit RST;

  always #((`TIME_PERIOD)/2) CLK = ~CLK;

  intf inf(CLK,RST);

  syn_fifo dut(.clk(CLK),.rst(RST),.wr_cs(inf.WR_CS),.rd_cs(inf.RD_CS),.data_in(inf.DATA_IN),.rd_en(inf.RD_EN),.wr_en(inf.WR_EN),.data_out(inf.DATA_OUT),.empty(inf.EMPTY),.full(inf.FULL));
  
//   bind syn_fifo fifo_checker #(
//   .DEPTH      (`DEPTH),
//   .ADDR_WIDTH (`ADDR_WIDTH)
// ) u_fifo_checker (
//   .clk   (CLOCK),
//   .rst   (RST),
//   .wr_cs (WR_CS),
//   .wr_en (WR_EN),
//   .rd_cs (RD_CS),
//   .rd_en (RD_EN),
//   .full  (FULL),
//   .empty (EMPTY)
// );

  task apply_reset;
    RST=1'b1;
    repeat(2) `CLOCK_DELAY
    RST=1'b0;
  endtask

  initial begin
    uvm_config_db #(virtual intf)::set(null,"*","vif",inf);
  end

  initial begin
    apply_reset;
    #30;
    apply_reset;
  end

  initial begin
    `WAVEFORM
  end

  initial begin
    run_test("base_test");
  end

//   initial begin
//     forever begin
//       wait(reset_event.triggered());
//       apply_reset;
//     end
//   end



endmodule