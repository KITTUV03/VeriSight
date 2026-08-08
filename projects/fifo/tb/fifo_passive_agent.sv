`ifndef PAS_AGENT
`define PAS_AGENT

class fifo_passive_agent extends uvm_agent;
  `uvm_component_utils(fifo_passive_agent)
  `COMP_CNSTR(fifo_passive_agent)
  fifo_passive mon_p;
  
  extern function void build_phase(uvm_phase phase);
    
endclass

`endif
    
function void fifo_passive_agent::build_phase(uvm_phase phase);
  super.build_phase(phase);
  
    mon_p=fifo_passive::type_id::create("mon_p",this);

endfunction
    
