`ifndef APB_DRIVER_SV
`define APB_DRIVER_SV

class apb_driver extends uvm_driver #(apb_trans);
    `uvm_component_utils(apb_driver)

    virtual apb_if vif;

    function new(string name = "apb_driver", uvm_component parent = null);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual apb_if)::get(this, "", "vif", vif)) begin
            `uvm_fatal("NO_VIF", "Virtual interface apb_if not bound to apb_driver")
        end
    endfunction

    task run_phase(uvm_phase phase);
        // Initialize bus to IDLE
        vif.mck.psel    <= 1'b0;
        vif.mck.penable <= 1'b0;
        vif.mck.pwrite  <= 1'b0;
        vif.mck.paddr   <= 32'h0;
        vif.mck.pwdata  <= 32'h0;

        @(posedge vif.presetn);
        @(vif.mck);

        forever begin
            seq_item_port.get_next_item(req);
            drive_transfer(req);
            seq_item_port.item_done();
        end
    endtask

    task drive_transfer(apb_trans tr);
        // Optional inter-transfer delay
        if (tr.delay > 0) begin
            repeat (tr.delay) @(vif.mck);
        end

        // 1. SETUP PHASE
        vif.mck.paddr   <= tr.paddr;
        vif.mck.pwrite  <= tr.pwrite;
        vif.mck.psel    <= 1'b1;
        vif.mck.penable <= 1'b0;
        if (tr.pwrite)
            vif.mck.pwdata <= tr.pwdata;
        else
            vif.mck.pwdata <= 32'h0;

        @(vif.mck);

        // 2. ACCESS PHASE
        vif.mck.penable <= 1'b1;
        @(vif.mck);

        while (!vif.mck.pready) begin
            @(vif.mck);
        end

        // Capture response
        tr.prdata  = vif.mck.prdata;
        tr.pslverr = vif.mck.pslverr;

        // 3. COMPLETE / IDLE
        vif.mck.psel    <= 1'b0;
        vif.mck.penable <= 1'b0;
        vif.mck.pwrite  <= 1'b0;
    endtask
endclass

`endif // APB_DRIVER_SV
