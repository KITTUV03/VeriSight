// NOTE: the original version of this interface used `clocking`/`modport
// clocking` blocks (drv_cb/mon_cb) to get input-skew-#1/output-skew-#0
// sampling relative to `posedge CLK`. Icarus Verilog (the default
// --simulate backend) doesn't support modport clocking declarations, so
// this was rewritten to plain signals. Driver/monitor reproduce the same
// timing directly: the driver still drives with `<=` at the clock edge
// (equivalent to output #0), and the monitor samples `#1` after the edge
// (equivalent to input #1) to avoid the same driver/DUT race the
// clocking block existed to prevent.
interface intf(input CLK,input RST);
  logic WR_CS;
  logic WR_EN;
  logic RD_CS;
  logic RD_EN;
  logic [`DATA_WIDTH-1:0] DATA_IN;
  logic [`DATA_WIDTH-1:0] DATA_OUT;
  logic EMPTY;
  logic FULL;
endinterface