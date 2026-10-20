`ifndef APB_SUBSCRIBER_SV
`define APB_SUBSCRIBER_SV

class apb_subscriber extends uvm_subscriber #(apb_trans);
    `uvm_component_utils(apb_subscriber)

    apb_trans tr;

    covergroup apb_cov;
        option.per_instance = 1;
        option.name = "apb_coverage_model";

        cp_addr: coverpoint tr.paddr {
            bins ctrl   = {32'h00};
            bins status = {32'h04};
            bins data0  = {32'h08};
            bins data1  = {32'h0C};
            bins timer  = {32'h10};
            bins unmapped = {[32'h14:$]};
        }

        cp_op: coverpoint tr.pwrite {
            bins read  = {1'b0};
            bins write = {1'b1};
        }

        cp_slverr: coverpoint tr.pslverr {
            bins ok  = {1'b0};
            bins err = {1'b1};
        }

        cross_addr_op: cross cp_addr, cp_op;
    endgroup

    function new(string name = "apb_subscriber", uvm_component parent = null);
        super.new(name, parent);
        apb_cov = new();
    endfunction

    virtual function void write(apb_trans t);
        tr = t;
        apb_cov.sample();
    endfunction
endclass

`endif // APB_SUBSCRIBER_SV
