// =============================================================================
// ALU Sequence Item
// =============================================================================

class alu_seq_item extends uvm_sequence_item;
    `uvm_object_utils(alu_seq_item)

    rand logic [7:0] operand_a;
    rand logic [7:0] operand_b;
    rand logic [3:0] op_sel;

    // Observed outputs
    logic [7:0] result;
    logic       carry;
    logic       zero;

    constraint valid_ops_c {
        op_sel inside {[0:7]};
    }

    function new(string name = "alu_seq_item");
        super.new(name);
    endfunction

    function string convert2string();
        return $sformatf("op_sel=%0h a=%0h b=%0h | result=%0h carry=%0b zero=%0b",
                         op_sel, operand_a, operand_b, result, carry, zero);
    endfunction
endclass
