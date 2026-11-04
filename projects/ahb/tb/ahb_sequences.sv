`ifndef AHB_SEQUENCES_SV
`define AHB_SEQUENCES_SV

class ahb_base_sequence extends uvm_sequence #(ahb_trans);
    `uvm_object_utils(ahb_base_sequence)

    function new(string name = "ahb_base_sequence");
        super.new(name);
    endfunction
endclass

class ahb_reset_read_seq extends ahb_base_sequence;
    `uvm_object_utils(ahb_reset_read_seq)

    function new(string name = "ahb_reset_read_seq");
        super.new(name);
    endfunction

    task body();
        ahb_trans tr;
        `uvm_info("AHB_SEQ", "=== Scenario 1: Checking Register Reset Defaults ===", UVM_LOW)

        tr = ahb_trans::type_id::create("tr");
        start_item(tr);
        tr.haddr  = `AHB_ADDR_CTRL;
        tr.hwrite = 1'b0;
        tr.htrans = `AHB_TR_NONSEQ;
        finish_item(tr);

        tr = ahb_trans::type_id::create("tr");
        start_item(tr);
        tr.haddr  = `AHB_ADDR_STATUS;
        tr.hwrite = 1'b0;
        tr.htrans = `AHB_TR_NONSEQ;
        finish_item(tr);

        tr = ahb_trans::type_id::create("tr");
        start_item(tr);
        tr.haddr  = `AHB_ADDR_DATA0;
        tr.hwrite = 1'b0;
        tr.htrans = `AHB_TR_NONSEQ;
        finish_item(tr);
    endtask
endclass

class ahb_data_integrity_seq extends ahb_base_sequence;
    `uvm_object_utils(ahb_data_integrity_seq)

    function new(string name = "ahb_data_integrity_seq");
        super.new(name);
    endfunction

    task body();
        ahb_trans tr;
        `uvm_info("AHB_SEQ", "=== Scenario 2: DATA0 32-bit Data Integrity Test ===", UVM_LOW)

        // Write DATA0 with 32-bit word
        tr = ahb_trans::type_id::create("tr");
        start_item(tr);
        tr.haddr  = `AHB_ADDR_DATA0;
        tr.hwrite = 1'b1;
        tr.hwdata = 32'hDEAD_BEEF;
        tr.htrans = `AHB_TR_NONSEQ;
        finish_item(tr);

        // Read DATA0 back
        tr = ahb_trans::type_id::create("tr");
        start_item(tr);
        tr.haddr  = `AHB_ADDR_DATA0;
        tr.hwrite = 1'b0;
        tr.htrans = `AHB_TR_NONSEQ;
        finish_item(tr);
    endtask
endclass

class ahb_ro_protection_seq extends ahb_base_sequence;
    `uvm_object_utils(ahb_ro_protection_seq)

    function new(string name = "ahb_ro_protection_seq");
        super.new(name);
    endfunction

    task body();
        ahb_trans tr;
        `uvm_info("AHB_SEQ", "=== Scenario 3: Read-Only STATUS Register Write Protection Test ===", UVM_LOW)

        // Write to Read-Only STATUS register - expects HRESP = 1
        tr = ahb_trans::type_id::create("tr");
        start_item(tr);
        tr.haddr  = `AHB_ADDR_STATUS;
        tr.hwrite = 1'b1;
        tr.hwdata = 32'hFFFF_FFFF;
        tr.htrans = `AHB_TR_NONSEQ;
        finish_item(tr);
    endtask
endclass

`endif // AHB_SEQUENCES_SV
