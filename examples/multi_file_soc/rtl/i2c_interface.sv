// SystemVerilog Interface for I2C physical layer
interface i2c_interface(input logic clk, input logic rst_n);
    logic scl;
    logic sda_out;
    logic sda_in;
    logic sda_oe;

    modport master (
        input clk, rst_n, sda_in,
        output scl, sda_out, sda_oe
    );

    modport slave (
        input clk, rst_n, scl, sda_out, sda_oe,
        output sda_in
    );
endinterface

