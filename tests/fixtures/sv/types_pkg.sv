// packed struct, enum, typedef, package + import, parameterized module.
package types_pkg;
    typedef enum logic [1:0] { IDLE, RUN, DONE } state_e;

    typedef struct packed {
        logic [7:0] addr;
        logic [7:0] data;
        logic       valid;
    } bus_t;

    parameter int WIDTH = 8;
endpackage

module typed_dut #(
    parameter int WIDTH = 8
) (
    input  logic              clk,
    input  logic              rst_n,
    input  types_pkg::bus_t   in_bus,
    output types_pkg::state_e state,
    output logic [WIDTH-1:0]  out_data
);
    import types_pkg::*;

    state_e cur, nxt;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) cur <= IDLE;
        else        cur <= nxt;
    end

    always_comb begin
        nxt = cur;
        case (cur)
            IDLE: if (in_bus.valid) nxt = RUN;
            RUN:  nxt = DONE;
            DONE: nxt = IDLE;
            default: nxt = IDLE;
        endcase
    end

    assign state    = cur;
    assign out_data = in_bus.data[WIDTH-1:0];
endmodule
