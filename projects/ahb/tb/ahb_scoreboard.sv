`ifndef AHB_SCOREBOARD_SV
`define AHB_SCOREBOARD_SV

class ahb_scoreboard extends uvm_scoreboard;
    `uvm_component_utils(ahb_scoreboard)

    uvm_analysis_imp #(ahb_trans, ahb_scoreboard) item_collected_export;

    // Golden memory model for registers
    bit [31:0] golden_mem [bit [31:0]];

    int match_count = 0;
    int mismatch_count = 0;
    int protocol_error_count = 0;

    function new(string name = "ahb_scoreboard", uvm_component parent = null);
        super.new(name, parent);
        item_collected_export = new("item_collected_export", this);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        golden_mem[`AHB_ADDR_CTRL]      = 32'h0000_0000;
        golden_mem[`AHB_ADDR_STATUS]    = 32'h0000_0002;
        golden_mem[`AHB_ADDR_DATA0]     = 32'h0000_0000;
        golden_mem[`AHB_ADDR_DATA1]     = 32'h0000_0000;
        golden_mem[`AHB_ADDR_BURST_CNT] = 32'h0000_0000;
    endfunction

    virtual function void write(ahb_trans tr);
        if (tr.hwrite) begin
            // Write Checking
            if (tr.haddr == `AHB_ADDR_STATUS) begin
                // Check Read-Only write protection
                if (tr.hresp == `AHB_RESP_ERROR) begin
                    `uvm_info("AHB_SCB", "WRITE RO STATUS PASS: Correctly asserted HRESP=1", UVM_LOW)
                end else begin
                    `uvm_error("AHB_SCB", $sformatf("PROTOCOL MISMATCH | Write to Read-Only STATUS register (0x04) did not assert HRESP! Expected HRESP=1 Actual HRESP=%0b", tr.hresp))
                    protocol_error_count++;
                end
            end else if (tr.haddr > `AHB_ADDR_BURST_CNT) begin
                // Unmapped address write
                if (tr.hresp == `AHB_RESP_ERROR) begin
                    `uvm_info("AHB_SCB", "UNMAPPED ADDR WRITE PASS: Correctly asserted HRESP=1", UVM_LOW)
                end else begin
                    `uvm_error("AHB_SCB", $sformatf("UNMAPPED ADDR MISMATCH | Write to unmapped address (0x%08h) did not assert HRESP! Expected HRESP=1 Actual=%0b", tr.haddr, tr.hresp))
                    protocol_error_count++;
                end
            end else begin
                golden_mem[tr.haddr] = tr.hwdata;
                `uvm_info("AHB_SCB", $sformatf("WRITE RECORDED | ADDR=0x%08h DATA=0x%08h", tr.haddr, tr.hwdata), UVM_LOW)
            end
        end else begin
            // Read Checking
            bit [31:0] expected_data;
            if (golden_mem.exists(tr.haddr)) begin
                expected_data = golden_mem[tr.haddr];
                if (tr.hrdata === expected_data) begin
                    `uvm_info("AHB_SCB", $sformatf("READ DATA PASS | ADDR=0x%08h Expected=0x%08h Actual=0x%08h", tr.haddr, expected_data, tr.hrdata), UVM_LOW)
                    match_count++;
                end else begin
                    `uvm_error("AHB_SCB", $sformatf("READ DATA MISMATCH | ADDR=0x%08h Expected=0x%08h Actual=0x%08h", tr.haddr, expected_data, tr.hrdata))
                    mismatch_count++;
                end
            end
        end
    endfunction

    function void report_phase(uvm_phase phase);
        super.report_phase(phase);
        `uvm_info("AHB_SCB", "--------------------------------------------------------", UVM_LOW)
        `uvm_info("AHB_SCB", "             AHB SCOREBOARD VERIFICATION SUMMARY        ", UVM_LOW)
        `uvm_info("AHB_SCB", "--------------------------------------------------------", UVM_LOW)
        `uvm_info("AHB_SCB", $sformatf("Total Matches Verified       : %0d", match_count), UVM_LOW)
        `uvm_info("AHB_SCB", $sformatf("Total Mismatches Detected    : %0d", mismatch_count), UVM_LOW)
        `uvm_info("AHB_SCB", $sformatf("Protocol Error Checks Failed : %0d", protocol_error_count), UVM_LOW)
        `uvm_info("AHB_SCB", "--------------------------------------------------------", UVM_LOW)
    endfunction
endclass

`endif // AHB_SCOREBOARD_SV
