`timescale 1ns / 1ps

interface apb_if (input logic pclk, input logic presetn);
    logic [31:0] paddr;
    logic        psel;
    logic        penable;
    logic        pwrite;
    logic [31:0] pwdata;
    logic        pready;
    logic [31:0] prdata;
    logic        pslverr;

    // Master Clocking Block
    clocking mck @(posedge pclk);
        default input #1step output #1;
        output paddr, psel, penable, pwrite, pwdata;
        input  pready, prdata, pslverr;
    endclocking

    // Monitor Clocking Block
    clocking mon_cb @(posedge pclk);
        default input #1step;
        input paddr, psel, penable, pwrite, pwdata, pready, prdata, pslverr;
    endclocking

    modport master (clocking mck, input pclk, input presetn);
    modport monitor (clocking mon_cb, input pclk, input presetn);

    // -------------------------------------------------------------------------
    // SystemVerilog Assertions (SVA) for APB Protocol Compliance
    // -------------------------------------------------------------------------

    // Property 1: PENABLE must follow PSEL in the next cycle (SETUP -> ACCESS)
    property p_penable_rise;
        @(posedge pclk) disable iff (!presetn)
        (psel && !penable) |=> penable;
    endproperty
    assert_penable_rise: assert property (p_penable_rise)
        else $error("Assertion APB_ERR_PENABLE_SEQUENCE failed at time %0t ns in apb_if: PENABLE did not follow PSEL", $time);

    // Property 2: Address must remain stable while PENABLE is asserted
    property p_addr_stable;
        @(posedge pclk) disable iff (!presetn)
        (psel && penable && !pready) |=> $stable(paddr);
    endproperty
    assert_addr_stable: assert property (p_addr_stable)
        else $error("Assertion APB_ERR_ADDR_UNSTABLE failed at time %0t ns in apb_if: PADDR changed during wait state", $time);

    // Property 3: Write to Read-Only STATUS register (0x04) must assert PSLVERR
    property p_pslverr_on_ro_write;
        @(posedge pclk) disable iff (!presetn)
        (psel && penable && pready && pwrite && (paddr == 32'h0000_0004)) |-> pslverr;
    endproperty
    assert_pslverr_on_ro_write: assert property (p_pslverr_on_ro_write)
        else $error("Assertion SVA_PSLVERR_ON_RO_WRITE_FAILED failed at time %0t ns in apb_if: Write to Read-Only register (0x04) failed to assert PSLVERR", $time);

endinterface
