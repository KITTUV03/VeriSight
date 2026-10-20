`ifndef APB_MONITOR_SV
`define APB_MONITOR_SV

class apb_monitor extends uvm_monitor;
    `uvm_component_utils(apb_monitor)

    virtual apb_if vif;
    uvm_analysis_port #(apb_trans) item_collected_port;

    function new(string name = "apb_monitor", uvm_component parent = null);
        super.new(name, parent);
        item_collected_port = new("item_collected_port", this);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual apb_if)::get(this, "", "vif", vif)) begin
            `uvm_fatal("NO_VIF", "Virtual interface apb_if not bound to apb_monitor")
        end
    endfunction

    task run_phase(uvm_phase phase);
        apb_trans tr;
        @(posedge vif.presetn);

        forever begin
            @(vif.mon_cb);
            // APB transfer completes when PSEL=1, PENABLE=1, PREADY=1
            if (vif.mon_cb.psel && vif.mon_cb.penable && vif.mon_cb.pready) begin
                tr = apb_trans::type_id::create("tr");
                tr.paddr   = vif.mon_cb.paddr;
                tr.pwrite  = vif.mon_cb.pwrite;
                tr.pwdata  = vif.mon_cb.pwdata;
                tr.prdata  = vif.mon_cb.prdata;
                tr.pslverr = vif.mon_cb.pslverr;

                item_collected_port.write(tr);
            end
        end
    endtask
endclass

`endif // APB_MONITOR_SV
