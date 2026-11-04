// Package defining I2C bus types and constants
package i2c_pkg;
    typedef enum logic [2:0] {
        I2C_IDLE  = 3'b000,
        I2C_START = 3'b001,
        I2C_ADDR  = 3'b010,
        I2C_ACK   = 3'b011,
        I2C_DATA  = 3'b100,
        I2C_STOP  = 3'b101
    } i2c_state_e;

    parameter int I2C_ADDR_WIDTH = 7;
    parameter int I2C_DATA_WIDTH = 8;
endpackage

