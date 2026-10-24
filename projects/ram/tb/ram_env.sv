class ram_env extends uvm_env;
  `uvm_component_utils(ram_env)
  `UVM_COMP_CTOR(ram_env)
  ram_scoreboard scb;
  ram_agent agt;
  
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    scb=ram_scoreboard::type_id::create("scb",this);
    agt=ram_agent::type_id::create("agt",this);	      	      

  endfunction
  
  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    agt.mon.mon_ap.connect(scb.mon_imp);
  endfunction
  
 
  
endclass
