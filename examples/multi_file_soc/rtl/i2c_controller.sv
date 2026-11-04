// I2C Controller instantiating the protocol FSM
module i2c_controller (
    input  logic clk,
    input  logic rst_n,
    input  logic enable,
    input  logic [6:0] dev_addr,
    output logic [2:0] state_out,
    output logic is_busy
);
    i2c_fsm u_fsm (
        .clk(clk),
        .rst_n(rst_n),
        .start_tx(enable),
        .slave_addr(dev_addr),
        .current_state(state_out),
        .busy(is_busy)
    );

endmodule

