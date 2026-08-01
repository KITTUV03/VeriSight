// =============================================================================
// ALU Sequence
// =============================================================================

class alu_sequence extends uvm_sequence #(alu_seq_item);
    `uvm_object_utils(alu_sequence)

    int num_transactions = 20;

    function new(string name = "alu_sequence");
        super.new(name);
    endfunction

    virtual task body();
        alu_seq_item txn;
        repeat (num_transactions) begin
            txn = alu_seq_item::type_id::create("txn");
            start_item(txn);
            if (!txn.randomize()) begin
                `uvm_fatal("SEQ", "Randomization failed")
            end
            finish_item(txn);
        end
    endtask
endclass
