`ifndef AHB_MONITOR_SV
`define AHB_MONITOR_SV

class ahb_monitor extends uvm_monitor;
    `uvm_component_utils(ahb_monitor)

    virtual ahb_if.MON vif;
    uvm_analysis_port #(ahb_trans) item_collected_port;

    function new(string name = "ahb_monitor", uvm_component parent = null);
        super.new(name, parent);
        item_collected_port = new("item_collected_port", this);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual ahb_if.MON)::get(this, "", "vif", vif))
            `uvm_fatal("NOVIF", "virtual interface must be set for ahb_monitor")
    endfunction

    task run_phase(uvm_phase phase);
        ahb_trans tr;
        wait(vif.HRESETn == 1'b1);
        @(vif.mon_cb);

        forever begin
            @(vif.mon_cb);
            if (vif.mon_cb.HSEL && vif.mon_cb.HREADY &&
               (vif.mon_cb.HTRANS == `AHB_TR_NONSEQ || vif.mon_cb.HTRANS == `AHB_TR_SEQ)) begin
                tr = ahb_trans::type_id::create("tr");
                tr.haddr  = vif.mon_cb.HADDR;
                tr.hwrite = vif.mon_cb.HWRITE;
                tr.htrans = vif.mon_cb.HTRANS;
                tr.hsize  = vif.mon_cb.HSIZE;
                tr.hburst = vif.mon_cb.HBURST;

                // Move to data phase
                @(vif.mon_cb);
                while (vif.mon_cb.HREADYOUT !== 1'b1) @(vif.mon_cb);

                if (tr.hwrite) tr.hwdata = vif.mon_cb.HWDATA;
                else           tr.hrdata = vif.mon_cb.HRDATA;
                tr.hresp = vif.mon_cb.HRESP;

                item_collected_port.write(tr);
            end
        end
    endtask
endclass

`endif // AHB_MONITOR_SV
