// =============================================================================
// ALU Test
// =============================================================================

class alu_test extends uvm_test;
    `uvm_component_utils(alu_test)

    alu_env env;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = alu_env::type_id::create("env", this);
    endfunction

    virtual task run_phase(uvm_phase phase);
        alu_sequence seq;
        phase.raise_objection(this);
        seq = alu_sequence::type_id::create("seq");
        seq.num_transactions = 20;
        seq.start(env.agt.sqr);
        #100;
        phase.drop_objection(this);
    endtask
endclass
