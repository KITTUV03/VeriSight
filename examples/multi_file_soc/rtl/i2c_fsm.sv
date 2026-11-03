// I2C Finite State Machine implementing bus transaction states
import i2c_pkg::*;

module i2c_fsm (
    input  logic clk,
    input  logic rst_n,
    input  logic start_tx,
    input  logic [I2C_ADDR_WIDTH-1:0] slave_addr,
    output logic [2:0] current_state,
    output logic busy
);
    i2c_state_e state_q, state_d;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= I2C_IDLE;
        end else begin
            state_q <= state_d;
        end
    end

    always_comb begin
        state_d = state_q;
        case (state_q)
            I2C_IDLE: begin
                if (start_tx) state_d = I2C_START;
            end
            I2C_START: begin
                state_d = I2C_ADDR;
            end
            I2C_ADDR: begin
                state_d = I2C_ACK;
            end
            I2C_ACK: begin
                state_d = I2C_DATA;
            end
            I2C_DATA: begin
                state_d = I2C_STOP;
            end
            I2C_STOP: begin
                state_d = I2C_IDLE;
            end
            default: state_d = I2C_IDLE;
        endcase
    end

    assign current_state = state_q;
    assign busy = (state_q != I2C_IDLE);

endmodule

