// =============================================================================
// ALU Driver
// =============================================================================

class alu_driver extends uvm_driver #(alu_seq_item);
    `uvm_component_utils(alu_driver)

    virtual alu_if vif;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual alu_if)::get(this, "", "vif", vif))
            `uvm_fatal("DRV", "Failed to get virtual interface")
    endfunction

    virtual task run_phase(uvm_phase phase);
        alu_seq_item txn;
        forever begin
            seq_item_port.get_next_item(txn);
            drive_transaction(txn);
            seq_item_port.item_done();
        end
    endtask

    virtual task drive_transaction(alu_seq_item txn);
        @(posedge vif.clk);
        vif.operand_a <= txn.operand_a;
        vif.operand_b <= txn.operand_b;
        vif.op_sel    <= txn.op_sel;
        @(posedge vif.clk);  // Wait for result
    endtask
endclass
