// Top-level SoC integrating APB Master, APB Slave, and I2C Controller
module top (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        trigger_apb,
    input  logic [31:0] host_addr,
    input  logic [31:0] host_wdata,
    output logic [31:0] host_rdata,
    input  logic        trigger_i2c,
    input  logic [6:0]  target_i2c_addr,
    output logic [2:0]  i2c_status,
    output logic        i2c_busy,
    output logic        pwr_iso_en,
    output logic        pwr_gate_en
);
    logic [31:0] paddr;
    logic        psel;
    logic        penable;
    logic        pwrite;
    logic [31:0] pwdata;
    logic [31:0] prdata;
    logic        pready;
    logic [31:0] reg_ctrl;

    // Power control signals
    assign pwr_iso_en  = reg_ctrl[0];
    assign pwr_gate_en = reg_ctrl[1];

    // APB Master Instance
    apb_master u_apb_master (
        .clk(clk),
        .rst_n(rst_n),
        .start_xfer(trigger_apb),
        .in_addr(host_addr),
        .in_wdata(host_wdata),
        .paddr(paddr),
        .psel(psel),
        .penable(penable),
        .pwrite(pwrite),
        .pwdata(pwdata),
        .prdata(prdata),
        .pready(pready),
        .out_rdata(host_rdata)
    );

    // APB Slave Instance
    apb_slave u_apb_slave (
        .pclk(clk),
        .presetn(rst_n),
        .paddr(paddr),
        .psel(psel),
        .penable(penable),
        .pwrite(pwrite),
        .pwdata(pwdata),
        .prdata(prdata),
        .pready(pready),
        .reg_ctrl(reg_ctrl)
    );

    // I2C Subsystem Instance
    i2c_controller u_i2c (
        .clk(clk),
        .rst_n(rst_n),
        .enable(trigger_i2c),
        .dev_addr(target_i2c_addr),
        .state_out(i2c_status),
        .is_busy(i2c_busy)
    );

endmodule

