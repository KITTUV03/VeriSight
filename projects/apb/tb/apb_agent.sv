`ifndef APB_AGENT_SV
`define APB_AGENT_SV

class apb_agent extends uvm_agent;
    `uvm_component_utils(apb_agent)

    apb_driver    driver;
    apb_sequencer sequencer;
    apb_monitor   monitor;

    uvm_analysis_port #(apb_trans) ap;

    function new(string name = "apb_agent", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        ap = new("ap", this);
        monitor = apb_monitor::type_id::create("monitor", this);

        if (get_is_active() == UVM_ACTIVE) begin
            driver    = apb_driver::type_id::create("driver", this);
            sequencer = apb_sequencer::type_id::create("sequencer", this);
        end
    endfunction

    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        if (get_is_active() == UVM_ACTIVE) begin
            driver.seq_item_port.connect(sequencer.seq_item_export);
        end
        monitor.item_collected_port.connect(ap);
    endfunction
endclass

`endif // APB_AGENT_SV
