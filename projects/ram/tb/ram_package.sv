`ifndef RAM_PKG_SV
`define RAM_PKG_SV

`include "uvm_macros.svh"
`include "ram_define.sv" 
`include "ram_interface.sv"
package ram_pkg;
  import uvm_pkg::*;
  `include "ram_sequence_item.sv"
  `include "write_sequence.sv"
  `include "read_seq.sv"
  `include "ram_sim_rw.sv"
  `include "ram_reset.sv"
  `include "ram_sequencer.sv"
  `include "ram_driver.sv"
  `include "ram_monitor.sv"
  `include "ram_agent.sv"
  `include "ram_scoeboard.sv"
  `include "ram_env.sv"
  `include "ram_test.sv"
endpackage

`endif
