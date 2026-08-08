`ifndef FIFO_ENV
`define FIFO_ENV

class fifo_env extends uvm_env;
  `uvm_component_utils(fifo_env)
  `COMP_CNSTR(fifo_env)
  
  fifo_agent agt;
   fifo_scoreboard scb;
  subscriber sub;
  fifo_passive_agent pass_agt;
  
  extern function void build_phase(uvm_phase phase);
  extern function void connect_phase(uvm_phase phase);

        
endclass

`endif
    
function void fifo_env::build_phase(uvm_phase phase);
  super.build_phase(phase);
  agt=fifo_agent::type_id::create("agt",this);
  pass_agt=fifo_passive_agent::type_id::create("pass_agt",this);
  scb=fifo_scoreboard::type_id::create("scb",this);
  sub=subscriber::type_id::create("sub",this);
  uvm_config_db #(uvm_active_passive_enum)::set(this,"*","active_cfg",UVM_ACTIVE);

endfunction
    
function void fifo_env::connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    agt.mon.ap_port.connect(scb.ap_imp);
    agt.mon.ap_port.connect(sub.analysis_export);
    pass_agt.mon_p.pass_port.connect(scb.pass_imp);

endfunction