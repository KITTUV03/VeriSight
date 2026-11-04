class ram_test extends uvm_test;
  `uvm_component_utils(ram_test)
  `UVM_COMP_CTOR(ram_test)

  ram_env env;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    env = ram_env::type_id::create("env", this);
  endfunction

  task run_phase(uvm_phase phase);
    ram_write_seq w_seq;
    ram_read_seq  r_seq;
    ram_reset     reset_seq;

    phase.raise_objection(this);

    reset_seq = ram_reset::type_id::create("reset_seq");
    reset_seq.start(env.agt.sqr);

    w_seq = ram_write_seq::type_id::create("w_seq");
    r_seq = ram_read_seq::type_id::create("r_seq");

    w_seq.start(env.agt.sqr);
    r_seq.start(env.agt.sqr);

    phase.drop_objection(this);
  endtask
endclass
