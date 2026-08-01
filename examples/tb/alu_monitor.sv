// =============================================================================
// ALU Monitor
// =============================================================================

class alu_monitor extends uvm_monitor;
    `uvm_component_utils(alu_monitor)

    virtual alu_if vif;
    uvm_analysis_port #(alu_seq_item) ap;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        ap = new("ap", this);
        if (!uvm_config_db#(virtual alu_if)::get(this, "", "vif", vif))
            `uvm_fatal("MON", "Failed to get virtual interface")
    endfunction

    virtual task run_phase(uvm_phase phase);
        alu_seq_item txn;
        forever begin
            @(posedge vif.clk);
            txn = alu_seq_item::type_id::create("txn");
            txn.operand_a = vif.operand_a;
            txn.operand_b = vif.operand_b;
            txn.op_sel    = vif.op_sel;
            @(posedge vif.clk);  // Sample outputs one cycle later
            txn.result = vif.result;
            txn.carry  = vif.carry;
            txn.zero   = vif.zero;
            ap.write(txn);
            `uvm_info("MON", $sformatf("Observed: %s", txn.convert2string()), UVM_HIGH)
        end
    endtask
endclass
