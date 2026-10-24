`ifndef AHB_SUBSCRIBER_SV
`define AHB_SUBSCRIBER_SV

class ahb_subscriber extends uvm_subscriber #(ahb_trans);
    `uvm_component_utils(ahb_subscriber)

    ahb_trans tr;

    covergroup ahb_cg;
        cp_addr: coverpoint tr.haddr {
            bins ctrl      = {`AHB_ADDR_CTRL};
            bins status    = {`AHB_ADDR_STATUS};
            bins data0     = {`AHB_ADDR_DATA0};
            bins data1     = {`AHB_ADDR_DATA1};
            bins burst_cnt = {`AHB_ADDR_BURST_CNT};
            bins unmapped  = {`AHB_ADDR_UNMAPPED};
        }
        cp_write: coverpoint tr.hwrite {
            bins read  = {1'b0};
            bins write = {1'b1};
        }
        cp_resp: coverpoint tr.hresp {
            bins okay  = {`AHB_RESP_OKAY};
            bins error = {`AHB_RESP_ERROR};
        }
        cross_addr_write: cross cp_addr, cp_write;
    endgroup

    function new(string name = "ahb_subscriber", uvm_component parent = null);
        super.new(name, parent);
        ahb_cg = new();
    endfunction

    function void write(ahb_trans t);
        tr = t;
        ahb_cg.sample();
    endfunction
endclass

`endif // AHB_SUBSCRIBER_SV
