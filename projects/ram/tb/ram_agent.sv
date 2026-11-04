class ram_agent extends uvm_agent;
  `uvm_component_utils(ram_agent)
  `UVM_COMP_CTOR(ram_agent)
  ram_sequencer sqr;
  ram_driver drv;
  ram_monitor mon;
  
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    sqr=ram_sequencer::type_id::create("sqr",this);	      	      
    drv=ram_driver::type_id::create("drv",this);
    mon=ram_monitor::type_id::create("mon",this);
  endfunction
  
  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    drv.seq_item_port.connect(sqr.seq_item_export);
  endfunction
  
 
  
endclass
