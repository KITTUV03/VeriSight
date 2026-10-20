`ifndef APB_TRANS_SV
`define APB_TRANS_SV

class apb_trans extends uvm_sequence_item;
    rand bit [31:0] paddr;
    rand bit        pwrite;
    rand bit [31:0] pwdata;
    bit      [31:0] prdata;
    bit             pslverr;
    rand int        delay;

    constraint c_delay {
        delay inside {[0:3]};
    }

    constraint c_addr_aligned {
        paddr[1:0] == 2'b00;
    }

    constraint c_valid_range {
        paddr inside {32'h00, 32'h04, 32'h08, 32'h0C, 32'h10, 32'h20};
    }

    `uvm_object_utils_begin(apb_trans)
        `uvm_field_int(paddr,   UVM_ALL_ON | UVM_HEX)
        `uvm_field_int(pwrite,  UVM_ALL_ON | UVM_BIN)
        `uvm_field_int(pwdata,  UVM_ALL_ON | UVM_HEX)
        `uvm_field_int(prdata,  UVM_ALL_ON | UVM_HEX)
        `uvm_field_int(pslverr, UVM_ALL_ON | UVM_BIN)
        `uvm_field_int(delay,   UVM_ALL_ON | UVM_DEC)
    `uvm_object_utils_end

    function new(string name = "apb_trans");
        super.new(name);
    endfunction

    virtual function string convert2string();
        return $sformatf("ADDR=0x%08h OP=%s WDATA=0x%08h RDATA=0x%08h PSLVERR=%0b",
                         paddr, (pwrite ? "WRITE" : "READ"), pwdata, prdata, pslverr);
    endfunction
endclass

`endif // APB_TRANS_SV
