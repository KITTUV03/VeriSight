`ifndef AHB_INTERFACE_SV
`define AHB_INTERFACE_SV

interface ahb_if(input logic HCLK, input logic HRESETn);
    logic        HSEL;
    logic [31:0] HADDR;
    logic [1:0]  HTRANS;
    logic        HWRITE;
    logic [2:0]  HSIZE;
    logic [2:0]  HBURST;
    logic [3:0]  HPROT;
    logic [31:0] HWDATA;
    logic        HREADY;
    logic        HREADYOUT;
    logic [31:0] HRDATA;
    logic        HRESP;

    // Clocking block for driver
    clocking drv_cb @(posedge HCLK);
        default input #1step output #1ns;
        output HSEL, HADDR, HTRANS, HWRITE, HSIZE, HBURST, HPROT, HWDATA, HREADY;
        input  HREADYOUT, HRDATA, HRESP;
    endclocking

    // Clocking block for monitor
    clocking mon_cb @(posedge HCLK);
        default input #1step;
        input HSEL, HADDR, HTRANS, HWRITE, HSIZE, HBURST, HPROT, HWDATA, HREADY, HREADYOUT, HRDATA, HRESP;
    endclocking

    modport DRV(clocking drv_cb, input HRESETn);
    modport MON(clocking mon_cb, input HRESETn);

    // SVA Assertions
    // Property 1: Write to Read-Only STATUS register (0x04) must assert HRESP = 1
    property p_ro_status_write_err;
        @(posedge HCLK) disable iff (!HRESETn)
        (HSEL && HREADY && (HTRANS == 2'b10 || HTRANS == 2'b11) && HWRITE && (HADDR == 32'h04))
        |=> ##[0:1] (HRESP == 1'b1);
    endproperty
    assert property (p_ro_status_write_err)
        else $error("Assertion SVA_HRESP_ON_RO_WRITE_FAILED FAILED: Write to Read-Only register (0x04) must assert HRESP");

    // Property 2: Ready must be stable during transfer
    property p_hready_asserted;
        @(posedge HCLK) disable iff (!HRESETn)
        HREADYOUT == 1'b1;
    endproperty
    assert property (p_hready_asserted)
        else $warning("Assertion SVA_HREADY_WAIT_STATE: Slave introduced wait states");

endinterface

`endif // AHB_INTERFACE_SV
