`timescale 1ns / 1ps

module ahb_tb;
    import uvm_pkg::*;
    import ahb_pkg::*;

    logic HCLK;
    logic HRESETn;

    initial begin
        HCLK = 0;
        forever #10 HCLK = ~HCLK;
    end

    initial begin
        HRESETn = 0;
        #35 HRESETn = 1;
    end

    ahb_if vif(HCLK, HRESETn);

    ahb_slave #(
        .ADDR_WIDTH(32),
        .DATA_WIDTH(32)
    ) dut (
        .HCLK      (vif.HCLK),
        .HRESETn   (vif.HRESETn),
        .HSEL      (vif.HSEL),
        .HADDR     (vif.HADDR),
        .HTRANS    (vif.HTRANS),
        .HWRITE    (vif.HWRITE),
        .HSIZE     (vif.HSIZE),
        .HBURST    (vif.HBURST),
        .HPROT     (vif.HPROT),
        .HWDATA    (vif.HWDATA),
        .HREADY    (vif.HREADY),
        .HREADYOUT (vif.HREADYOUT),
        .HRDATA    (vif.HRDATA),
        .HRESP     (vif.HRESP)
    );

    initial begin
        uvm_config_db#(virtual ahb_if.DRV)::set(null, "*", "vif", vif.DRV);
        uvm_config_db#(virtual ahb_if.MON)::set(null, "*", "vif", vif.MON);
        run_test("ahb_regression_test");
    end

    initial begin
        $dumpfile("projects/ahb/waves/dump.vcd");
        $dumpvars(0, ahb_tb);
    end
endmodule
