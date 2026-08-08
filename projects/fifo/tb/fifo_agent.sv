`ifndef AGENT
`define AGENT

class fifo_agent extends uvm_agent;
  `uvm_component_utils(fifo_agent)
  `COMP_CNSTR(fifo_agent)
  fifo_driver drv;
  fifo_monitor mon;
  fifo_sequencer sqr;
  uvm_active_passive_enum is_active;
  
  extern function void build_phase(uvm_phase phase);
  extern function void connect_phase(uvm_phase phase);
    
endclass

`endif
    
function void fifo_agent::build_phase(uvm_phase phase);
  super.build_phase(phase);
  
  if(!uvm_config_db #(uvm_active_passive_enum)::get(this," ","active_cfg",is_active)) begin
    `uvm_info(get_type_name(),"CFG RECEIVED",UVM_LOW)
  end
  
  if(is_active == UVM_ACTIVE) begin
      drv=fifo_driver::type_id::create("drv",this);
      sqr=fifo_sequencer::type_id::create("sqr",this);
  end
  
    mon=fifo_monitor::type_id::create("mon",this);

endfunction
    
function void fifo_agent::connect_phase(uvm_phase phase);
  super.connect_phase(phase);
  drv.seq_item_port.connect(sqr.seq_item_export);
endfunction