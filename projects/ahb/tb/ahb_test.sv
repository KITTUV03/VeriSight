`ifndef AHB_TEST_SV
`define AHB_TEST_SV

class ahb_regression_test extends uvm_test;
    `uvm_component_utils(ahb_regression_test)

    ahb_env env;

    function new(string name = "ahb_regression_test", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = ahb_env::type_id::create("env", this);
    endfunction

    task run_phase(uvm_phase phase);
        ahb_reset_read_seq     seq_reset;
        ahb_data_integrity_seq seq_data;
        ahb_ro_protection_seq  seq_ro;

        phase.raise_objection(this);
        `uvm_info("AHB_TEST", "==================================================", UVM_LOW)
        `uvm_info("AHB_TEST", "   Starting AHB-Lite Comprehensive Verification   ", UVM_LOW)
        `uvm_info("AHB_TEST", "==================================================", UVM_LOW)

        seq_reset = ahb_reset_read_seq::type_id::create("seq_reset");
        seq_data  = ahb_data_integrity_seq::type_id::create("seq_data");
        seq_ro    = ahb_ro_protection_seq::type_id::create("seq_ro");

        seq_reset.start(env.agent.sequencer);
        #50;
        seq_data.start(env.agent.sequencer);
        #50;
        seq_ro.start(env.agent.sequencer);
        #100;

        phase.drop_objection(this);
    endtask
endclass

`endif // AHB_TEST_SV
