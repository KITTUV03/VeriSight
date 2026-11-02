`ifndef AHB_TRANS_SV
`define AHB_TRANS_SV

class ahb_trans extends uvm_sequence_item;
    rand bit [31:0] haddr;
    rand bit [1:0]  htrans;
    rand bit        hwrite;
    rand bit [2:0]  hsize;
    rand bit [2:0]  hburst;
    rand bit [31:0] hwdata;
    bit      [31:0] hrdata;
    bit             hresp;
    rand int        delay;

    constraint c_delay {
        delay inside {[0:2]};
    }

    constraint c_addr_aligned {
        haddr[1:0] == 2'b00;
    }

    constraint c_valid_range {
        haddr inside {32'h00, 32'h04, 32'h08, 32'h0C, 32'h10, 32'h20};
    }

    `uvm_object_utils_begin(ahb_trans)
        `uvm_field_int(haddr,  UVM_ALL_ON | UVM_HEX)
        `uvm_field_int(htrans, UVM_ALL_ON | UVM_BIN)
        `uvm_field_int(hwrite, UVM_ALL_ON | UVM_BIN)
        `uvm_field_int(hsize,  UVM_ALL_ON | UVM_BIN)
        `uvm_field_int(hwdata, UVM_ALL_ON | UVM_HEX)
        `uvm_field_int(hrdata, UVM_ALL_ON | UVM_HEX)
        `uvm_field_int(hresp,  UVM_ALL_ON | UVM_BIN)
        `uvm_field_int(delay,  UVM_ALL_ON | UVM_DEC)
    `uvm_object_utils_end

    function new(string name = "ahb_trans");
        super.new(name);
    endfunction

    virtual function string convert2string();
        return $sformatf("ADDR=0x%08h OP=%s TRANS=%0b WDATA=0x%08h RDATA=0x%08h HRESP=%0b",
                         haddr, (hwrite ? "WRITE" : "READ"), htrans, hwdata, hrdata, hresp);
    endfunction
endclass

`endif // AHB_TRANS_SV
