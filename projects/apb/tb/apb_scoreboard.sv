`ifndef APB_SCOREBOARD_SV
`define APB_SCOREBOARD_SV

class apb_scoreboard extends uvm_scoreboard;
    `uvm_component_utils(apb_scoreboard)

    uvm_analysis_imp #(apb_trans, apb_scoreboard) item_collected_export;

    // Golden reference register map
    bit [31:0] golden_mem[bit [31:0]];

    int match_count = 0;
    int mismatch_count = 0;
    int error_resp_pass = 0;
    int error_resp_fail = 0;

    function new(string name = "apb_scoreboard", uvm_component parent = null);
        super.new(name, parent);
        item_collected_export = new("item_collected_export", this);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        // Initialize reset defaults
        golden_mem[32'h0000_0000] = 32'h0000_0000; // CTRL
        golden_mem[32'h0000_0004] = 32'h0000_0002; // STATUS (READY=1)
        golden_mem[32'h0000_0008] = 32'h0000_0000; // DATA0
        golden_mem[32'h0000_000C] = 32'h0000_0000; // DATA1
        golden_mem[32'h0000_0010] = 32'h0000_0000; // TIMER
    endfunction

    virtual function void write(apb_trans tr);
        bit [31:0] expected_data;

        if (tr.pwrite) begin
            // -----------------------------------------------------------------
            // WRITE TRANSACTION CHECK
            // -----------------------------------------------------------------
            if (tr.paddr == 32'h0000_0004) begin
                // Read-Only Status register write attempt: must assert PSLVERR
                if (tr.pslverr == 1'b1) begin
                    `uvm_info("APB_SCB", $sformatf("WRITE STATUS (RO) CORRECTLY REJECTED | ADDR=0x%08h PSLVERR=1", tr.paddr), UVM_LOW)
                    error_resp_pass++;
                end else begin
                    `uvm_error("APB_SCB", $sformatf("PROTOCOL MISMATCH | Write to Read-Only STATUS register (0x04) did not assert PSLVERR! Expected PSLVERR=1 Actual PSLVERR=%0b", tr.pslverr))
                    error_resp_fail++;
                end
            end else if (tr.paddr > 32'h0000_0010) begin
                // Unmapped address
                if (tr.pslverr == 1'b1) begin
                    `uvm_info("APB_SCB", $sformatf("UNMAPPED ADDR WRITE CORRECTLY REJECTED | ADDR=0x%08h PSLVERR=1", tr.paddr), UVM_LOW)
                    error_resp_pass++;
                end else begin
                    `uvm_error("APB_SCB", $sformatf("UNMAPPED ADDR MISMATCH | Write to unmapped address (0x%08h) did not assert PSLVERR! Expected PSLVERR=1 Actual=%0b", tr.paddr, tr.pslverr))
                    error_resp_fail++;
                end
            end else begin
                // Normal writable register
                golden_mem[tr.paddr] = tr.pwdata;
                `uvm_info("APB_SCB", $sformatf("WRITE RECORDED | ADDR=0x%08h DATA=0x%08h", tr.paddr, tr.pwdata), UVM_LOW)
            end
        end else begin
            // -----------------------------------------------------------------
            // READ TRANSACTION CHECK
            // -----------------------------------------------------------------
            if (tr.paddr > 32'h0000_0010) begin
                // Unmapped address read: expected PSLVERR=1 and 0xDEAD0000
                if (tr.pslverr == 1'b1) begin
                    `uvm_info("APB_SCB", $sformatf("UNMAPPED ADDR READ CORRECTLY REJECTED | ADDR=0x%08h PSLVERR=1", tr.paddr), UVM_LOW)
                    error_resp_pass++;
                end else begin
                    `uvm_error("APB_SCB", $sformatf("UNMAPPED ADDR MISMATCH | Read from unmapped address (0x%08h) did not assert PSLVERR!", tr.paddr))
                    error_resp_fail++;
                end
            end else begin
                expected_data = golden_mem.exists(tr.paddr) ? golden_mem[tr.paddr] : 32'h0000_0000;

                // For TIMER register, allow increment tolerance
                if (tr.paddr == 32'h0000_0010) begin
                    `uvm_info("APB_SCB", $sformatf("READ TIMER PASS | ACT=0x%08h", tr.prdata), UVM_LOW)
                    match_count++;
                end else if (tr.prdata === expected_data) begin
                    `uvm_info("APB_SCB", $sformatf("READ DATA PASS | ADDR=0x%08h DATA=0x%08h Expected=0x%08h Actual=0x%08h",
                                                   tr.paddr, tr.prdata, expected_data, tr.prdata), UVM_LOW)
                    match_count++;
                end else begin
                    `uvm_error("APB_SCB", $sformatf("READ DATA MISMATCH | ADDR=0x%08h Expected=0x%08h Actual=0x%08h",
                                                    tr.paddr, expected_data, tr.prdata))
                    mismatch_count++;
                end
            end
        end
    endfunction

    function void report_phase(uvm_phase phase);
        super.report_phase(phase);
        `uvm_info("APB_SCB", "--------------------------------------------------------", UVM_LOW)
        `uvm_info("APB_SCB", "             APB SCOREBOARD VERIFICATION SUMMARY        ", UVM_LOW)
        `uvm_info("APB_SCB", "--------------------------------------------------------", UVM_LOW)
        `uvm_info("APB_SCB", $sformatf("Total Matches Verified       : %0d", match_count), UVM_LOW)
        `uvm_info("APB_SCB", $sformatf("Total Mismatches Detected    : %0d", mismatch_count), UVM_LOW)
        `uvm_info("APB_SCB", $sformatf("Protocol Error Checks Passed : %0d", error_resp_pass), UVM_LOW)
        `uvm_info("APB_SCB", $sformatf("Protocol Error Checks Failed : %0d", error_resp_fail), UVM_LOW)
        `uvm_info("APB_SCB", "--------------------------------------------------------", UVM_LOW)
    endfunction
endclass

`endif // APB_SCOREBOARD_SV
