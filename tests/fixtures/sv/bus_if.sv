// SystemVerilog interface with modports and a clocking block.
interface bus_if (input logic clk);
    logic        valid;
    logic        ready;
    logic [31:0] data;

    clocking cb @(posedge clk);
        output valid, data;
        input  ready;
    endclocking

    modport master (output valid, data, input ready, clocking cb);
    modport slave  (input  valid, data, output ready);
endinterface
