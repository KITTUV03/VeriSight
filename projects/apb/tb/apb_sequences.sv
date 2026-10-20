`ifndef APB_SEQUENCES_SV
`define APB_SEQUENCES_SV

// -----------------------------------------------------------------------------
// Base Sequence
// -----------------------------------------------------------------------------
class apb_base_seq extends uvm_sequence #(apb_trans);
    `uvm_object_utils(apb_base_seq)

    function new(string name = "apb_base_seq");
        super.new(name);
    endfunction
endclass

// -----------------------------------------------------------------------------
// Register Read/Write Integrity Sequence
// Exercises Control and Data registers
// -----------------------------------------------------------------------------
class apb_reg_access_seq extends apb_base_seq;
    `uvm_object_utils(apb_reg_access_seq)

    function new(string name = "apb_reg_access_seq");
        super.new(name);
    endfunction

    virtual task body();
        apb_trans tr;

        // 1. Write and Read REG_CTRL (0x00)
        `uvm_do_with(tr, { paddr == 32'h00; pwrite == 1; pwdata == 32'h0000_0005; })
        `uvm_do_with(tr, { paddr == 32'h00; pwrite == 0; })

        // 2. Write and Read REG_DATA0 (0x08) — Hits INTENTIONAL BUG 2!
        // Writing 32'hDEADBEEF. Since RTL masks upper 16 bits, read returns 32'h0000BEEF!
        `uvm_do_with(tr, { paddr == 32'h08; pwrite == 1; pwdata == 32'hDEAD_BEEF; })
        `uvm_do_with(tr, { paddr == 32'h08; pwrite == 0; })

        // 3. Write and Read REG_DATA1 (0x0C) — Clean register
        `uvm_do_with(tr, { paddr == 32'h0C; pwrite == 1; pwdata == 32'hCAFE_BABE; })
        `uvm_do_with(tr, { paddr == 32'h0C; pwrite == 0; })

        // 4. Repeated Data0 write with different 32-bit pattern — Hits BUG 2 again!
        `uvm_do_with(tr, { paddr == 32'h08; pwrite == 1; pwdata == 32'h1234_5678; })
        `uvm_do_with(tr, { paddr == 32'h08; pwrite == 0; })
    endtask
endclass

// -----------------------------------------------------------------------------
// Read-Only Register Violation Sequence
// Attempts to write to REG_STATUS (0x04) — Hits INTENTIONAL BUG 1!
// -----------------------------------------------------------------------------
class apb_ro_status_seq extends apb_base_seq;
    `uvm_object_utils(apb_ro_status_seq)

    function new(string name = "apb_ro_status_seq");
        super.new(name);
    endfunction

    virtual task body();
        apb_trans tr;

        // Attempt write to Read-Only STATUS register
        `uvm_do_with(tr, { paddr == 32'h04; pwrite == 1; pwdata == 32'hFFFF_FFFF; })
        // Read STATUS to verify contents unaltered
        `uvm_do_with(tr, { paddr == 32'h04; pwrite == 0; })
    endtask
endclass

// -----------------------------------------------------------------------------
// Unmapped Address Sequence
// -----------------------------------------------------------------------------
class apb_unmapped_seq extends apb_base_seq;
    `uvm_object_utils(apb_unmapped_seq)

    function new(string name = "apb_unmapped_seq");
        super.new(name);
    endfunction

    virtual task body();
        apb_trans tr;
        `uvm_do_with(tr, { paddr == 32'h20; pwrite == 1; pwdata == 32'hAAAA_BBBB; })
        `uvm_do_with(tr, { paddr == 32'h20; pwrite == 0; })
    endtask
endclass

// -----------------------------------------------------------------------------
// Master Virtual Sequence combining all scenarios
// -----------------------------------------------------------------------------
class apb_master_seq extends apb_base_seq;
    `uvm_object_utils(apb_master_seq)

    function new(string name = "apb_master_seq");
        super.new(name);
    endfunction

    virtual task body();
        apb_reg_access_seq reg_seq;
        apb_ro_status_seq  ro_seq;
        apb_unmapped_seq   unmap_seq;

        `uvm_info("APB_SEQ", "Starting APB Register Access Sequence...", UVM_LOW)
        `uvm_do(reg_seq)

        `uvm_info("APB_SEQ", "Starting APB Read-Only Protocol Test Sequence...", UVM_LOW)
        `uvm_do(ro_seq)

        `uvm_info("APB_SEQ", "Starting APB Unmapped Address Test Sequence...", UVM_LOW)
        `uvm_do(unmap_seq)
    endtask
endclass

`endif // APB_SEQUENCES_SV
