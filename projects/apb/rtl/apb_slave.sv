// =============================================================================
// Module: apb_slave.sv
// Description: AMBA 3 / AMBA 4 APB Slave with 32-bit Memory-Mapped Registers
// Author: VeriSight Verification Testbed
// Note: Contains intentional RTL defects for autonomous RCA & debug validation.
// =============================================================================

`timescale 1ns / 1ps

module apb_slave #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
)(
    input  logic                  pclk,
    input  logic                  presetn,
    input  logic [ADDR_WIDTH-1:0] paddr,
    input  logic                  psel,
    input  logic                  penable,
    input  logic                  pwrite,
    input  logic [DATA_WIDTH-1:0] pwdata,
    output logic                  pready,
    output logic [DATA_WIDTH-1:0] prdata,
    output logic                  pslverr
);

    // Register Offsets
    localparam ADDR_CTRL   = 32'h00;
    localparam ADDR_STATUS = 32'h04;
    localparam ADDR_DATA0  = 32'h08;
    localparam ADDR_DATA1  = 32'h0C;
    localparam ADDR_TIMER  = 32'h10;

    // Internal Registers
    logic [DATA_WIDTH-1:0] reg_ctrl;
    logic [DATA_WIDTH-1:0] reg_status;
    logic [DATA_WIDTH-1:0] reg_data0;
    logic [DATA_WIDTH-1:0] reg_data1;
    logic [DATA_WIDTH-1:0] reg_timer;

    // Transfer active indicator
    wire apb_transfer_active = psel && penable;

    // PREADY is single cycle zero-wait-state by default
    assign pready = 1'b1;

    // -------------------------------------------------------------------------
    // Timer Logic
    // -------------------------------------------------------------------------
    always_ff @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            reg_timer <= 32'h0000_0000;
        end else if (reg_ctrl[0]) begin
            reg_timer <= reg_timer + 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // Write and Control Logic
    // -------------------------------------------------------------------------
    always_ff @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            reg_ctrl   <= 32'h0000_0000;
            reg_status <= 32'h0000_0002; // Bit 1 = READY
            reg_data0  <= 32'h0000_0000;
            reg_data1  <= 32'h0000_0000;
            pslverr    <= 1'b0;
        end else begin
            // Default: clear error response
            pslverr <= 1'b0;

            if (psel && penable && pwrite) begin
                case (paddr)
                    ADDR_CTRL: begin
                        reg_ctrl <= pwdata;
                    end

                    ADDR_STATUS: begin
                        // -----------------------------------------------------
                        // INTENTIONAL BUG 1: Read-Only Register Write Protection Bug
                        // The spec requires asserting PSLVERR on write to REG_STATUS.
                        // Bug: Designer silently ignored write without asserting pslverr!
                        // -----------------------------------------------------
                        pslverr <= 1'b0; // DEFECT: Should be pslverr <= 1'b1;
                    end

                    ADDR_DATA0: begin
                        // -----------------------------------------------------
                        // INTENTIONAL BUG 2: Upper 16-bit truncation bug
                        // The designer incorrectly masked or truncated the upper 16 bits!
                        // Bug: reg_data0 <= {16'h0000, pwdata[15:0]}; instead of full 32 bits!
                        // -----------------------------------------------------
                        reg_data0 <= {16'h0000, pwdata[15:0]}; // DEFECT: Drops pwdata[31:16]
                    end

                    ADDR_DATA1: begin
                        reg_data1 <= pwdata; // Correct full 32-bit write
                    end

                    ADDR_TIMER: begin
                        reg_timer <= pwdata;
                    end

                    default: begin
                        // Unmapped address error response
                        pslverr <= 1'b1;
                    end
                endcase
            end else if (psel && penable && !pwrite) begin
                // Read error detection on unmapped addresses
                if (paddr > ADDR_TIMER) begin
                    pslverr <= 1'b1;
                end
            end
        end
    end

    // -------------------------------------------------------------------------
    // Read Data Mux
    // -------------------------------------------------------------------------
    always_comb begin
        if (psel && !pwrite) begin
            case (paddr)
                ADDR_CTRL:   prdata = reg_ctrl;
                ADDR_STATUS: prdata = reg_status;
                ADDR_DATA0:  prdata = reg_data0;
                ADDR_DATA1:  prdata = reg_data1;
                ADDR_TIMER:  prdata = reg_timer;
                default:     prdata = 32'hDEAD_0000;
            endcase
        end else begin
            prdata = 32'h0000_0000;
        end
    end

endmodule
