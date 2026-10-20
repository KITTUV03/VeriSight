`timescale 1ns / 1ps

`include "uvm_macros.svh"
`include "apb_interface.sv"
`include "apb_package.sv"

module apb_tb;
    import uvm_pkg::*;
    import apb_pkg::*;

    logic pclk;
    logic presetn;

    // Clock Generation (50 MHz, 20ns period / 10ns half-period)
    initial begin
        pclk = 0;
        forever #10 pclk = ~pclk;
    end

    // Reset Generation
    initial begin
        presetn = 0;
        #35;
        presetn = 1;
    end

    // Interface Instantiation
    apb_if intf(pclk, presetn);

    // DUT Instantiation
    apb_slave #(
        .ADDR_WIDTH(32),
        .DATA_WIDTH(32)
    ) dut (
        .pclk    (pclk),
        .presetn (presetn),
        .paddr   (intf.paddr),
        .psel    (intf.psel),
        .penable (intf.penable),
        .pwrite  (intf.pwrite),
        .pwdata  (intf.pwdata),
        .pready  (intf.pready),
        .prdata  (intf.prdata),
        .pslverr (intf.pslverr)
    );

    initial begin
        uvm_config_db#(virtual apb_if)::set(null, "*", "vif", intf);
        run_test("apb_base_test");
    end

    // Simulation timeout safeguard
    initial begin
        #5000;
        $display("[TIMEOUT] Simulation reached max time limit.");
        $finish;
    end
endmodule
