`ifndef APB_TEST_SV
`define APB_TEST_SV

class apb_base_test extends uvm_test;
    `uvm_component_utils(apb_base_test)

    apb_env env;

    function new(string name = "apb_base_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = apb_env::type_id::create("env", this);
    endfunction

    task run_phase(uvm_phase phase);
        apb_master_seq m_seq;
        phase.raise_objection(this);

        `uvm_info("APB_TEST", "==================================================", UVM_LOW)
        `uvm_info("APB_TEST", "   Starting APB Comprehensive Verification Test   ", UVM_LOW)
        `uvm_info("APB_TEST", "==================================================", UVM_LOW)

        m_seq = apb_master_seq::type_id::create("m_seq");
        m_seq.start(env.agent.sequencer);

        #100;
        phase.drop_objection(this);
    endtask
endclass

`endif // APB_TEST_SV
