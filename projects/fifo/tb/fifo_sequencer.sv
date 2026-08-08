`ifndef SQR
`define SQR

class fifo_sequencer extends uvm_sequencer#(fifo_trans);
  `uvm_component_utils(fifo_sequencer)
  `COMP_CNSTR(fifo_sequencer)
endclass
  
  
`endif