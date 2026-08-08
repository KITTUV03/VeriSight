class base_test extends uvm_test;
  `uvm_component_utils(base_test)
  `COMP_CNSTR(base_test)
  
  fifo_env env;
  fifo_virtual_seq v_seq;
  
  extern function void build_phase(uvm_phase phase);
  extern task run_phase(uvm_phase phase);

endclass
    
function void base_test::build_phase(uvm_phase phase);
   env=fifo_env::type_id::create("env",this);
endfunction
    
task base_test::run_phase(uvm_phase phase);
  v_seq=fifo_virtual_seq::type_id::create("v_seq");

  phase.raise_objection(this);
  v_seq.start(env.agt.sqr);
  phase.drop_objection(this);
  phase.phase_done.set_drain_time(this,50ns);
  
endtask