`ifndef AHB_DRIVER_SV
`define AHB_DRIVER_SV

class ahb_driver extends uvm_driver #(ahb_trans);
    `uvm_component_utils(ahb_driver)

    virtual ahb_if.DRV vif;

    function new(string name = "ahb_driver", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual ahb_if.DRV)::get(this, "", "vif", vif))
            `uvm_fatal("NOVIF", "virtual interface must be set for ahb_driver")
    endfunction

    task run_phase(uvm_phase phase);
        // Wait for reset release
        wait(vif.HRESETn == 1'b1);
        @(vif.drv_cb);

        forever begin
            seq_item_port.get_next_item(req);
            drive_transfer(req);
            seq_item_port.item_done();
        end
    endtask

    task drive_transfer(ahb_trans tr);
        // Address Phase
        vif.drv_cb.HSEL   <= 1'b1;
        vif.drv_cb.HADDR  <= tr.haddr;
        vif.drv_cb.HTRANS <= tr.htrans;
        vif.drv_cb.HWRITE <= tr.hwrite;
        vif.drv_cb.HSIZE  <= tr.hsize;
        vif.drv_cb.HBURST <= tr.hburst;
        vif.drv_cb.HREADY <= 1'b1;

        @(vif.drv_cb);

        // Data Phase
        if (tr.hwrite) begin
            vif.drv_cb.HWDATA <= tr.hwdata;
        end
        vif.drv_cb.HTRANS <= `AHB_TR_IDLE;
        vif.drv_cb.HSEL   <= 1'b0;

        @(vif.drv_cb);
        while (vif.drv_cb.HREADYOUT !== 1'b1) @(vif.drv_cb);

        if (!tr.hwrite) begin
            tr.hrdata = vif.drv_cb.HRDATA;
        end
        tr.hresp = vif.drv_cb.HRESP;

        `uvm_info("AHB_DRV", $sformatf("Completed %s: ADDR=0x%08h DATA=0x%08h HRESP=%0b",
                                       (tr.hwrite ? "WRITE" : "READ"), tr.haddr,
                                       (tr.hwrite ? tr.hwdata : tr.hrdata), tr.hresp), UVM_LOW)
    endtask
endclass

`endif // AHB_DRIVER_SV
