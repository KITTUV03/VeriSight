// =============================================================================
// Module: ahb_slave.sv
// Description: AMBA 3 AHB-Lite Slave with 32-bit Memory-Mapped Registers
// Author: VeriSight Verification Testbed
// Note: Contains intentional RTL defects for autonomous RCA & debug validation.
// =============================================================================

`timescale 1ns / 1ps

module ahb_slave #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
)(
    input  logic                  HCLK,
    input  logic                  HRESETn,
    input  logic                  HSEL,
    input  logic [ADDR_WIDTH-1:0] HADDR,
    input  logic [1:0]            HTRANS,
    input  logic                  HWRITE,
    input  logic [2:0]            HSIZE,
    input  logic [2:0]            HBURST,
    input  logic [3:0]            HPROT,
    input  logic [DATA_WIDTH-1:0] HWDATA,
    input  logic                  HREADY,
    output logic                  HREADYOUT,
    output logic [DATA_WIDTH-1:0] HRDATA,
    output logic                  HRESP
);

    // HTRANS Encoding
    localparam TR_IDLE   = 2'b00;
    localparam TR_BUSY   = 2'b01;
    localparam TR_NONSEQ = 2'b10;
    localparam TR_SEQ    = 2'b11;

    // Register Offsets
    localparam ADDR_CTRL      = 32'h00;
    localparam ADDR_STATUS    = 32'h04;
    localparam ADDR_DATA0     = 32'h08;
    localparam ADDR_DATA1     = 32'h0C;
    localparam ADDR_BURST_CNT = 32'h10;

    // Pipeline Registers for Address Phase -> Data Phase
    logic [ADDR_WIDTH-1:0] addr_phase_addr;
    logic                  addr_phase_write;
    logic                  addr_phase_active;
    logic [1:0]            addr_phase_trans;

    // Internal Storage Registers
    logic [DATA_WIDTH-1:0] reg_ctrl;
    logic [DATA_WIDTH-1:0] reg_status;
    logic [DATA_WIDTH-1:0] reg_data0;
    logic [DATA_WIDTH-1:0] reg_data1;
    logic [DATA_WIDTH-1:0] reg_burst_cnt;

    // Internal scratchpad buffer - intentionally uninitialized on reset (Bug 3: X-propagation source)
    logic [DATA_WIDTH-1:0] burst_buffer;

    // Single-cycle ready response for basic operations
    assign HREADYOUT = 1'b1;

    // Transfer active condition in address phase
    wire transfer_sampled = HSEL && HREADY && (HTRANS == TR_NONSEQ || HTRANS == TR_SEQ);

    // -------------------------------------------------------------------------
    // Address Phase Sampling & Pipeline State
    // -------------------------------------------------------------------------
    always_ff @(posedge HCLK or negedge HRESETn) begin
        if (!HRESETn) begin
            addr_phase_addr   <= 32'h0000_0000;
            addr_phase_write  <= 1'b0;
            addr_phase_active <= 1'b0;
            addr_phase_trans  <= TR_IDLE;
        end else if (HREADY) begin
            if (transfer_sampled) begin
                addr_phase_addr   <= HADDR;
                addr_phase_write  <= HWRITE;
                addr_phase_active <= 1'b1;
                addr_phase_trans  <= HTRANS;
            end else begin
                addr_phase_active <= 1'b0;
                addr_phase_trans  <= TR_IDLE;
            end
        end
    end

    // -------------------------------------------------------------------------
    // Data Phase: Register Write and Error Response Logic
    // -------------------------------------------------------------------------
    always_ff @(posedge HCLK or negedge HRESETn) begin
        if (!HRESETn) begin
            reg_ctrl      <= 32'h0000_0000;
            reg_status    <= 32'h0000_0002; // Bit 1 = READY (default active)
            reg_data0     <= 32'h0000_0000;
            reg_data1     <= 32'h0000_0000;
            reg_burst_cnt <= 32'h0000_0000;
            HRESP         <= 1'b0;
            // DEFECT 3: burst_buffer is NOT reset here, causing uninitialized register X propagation!
        end else begin
            // Default response: OKAY
            HRESP <= 1'b0;

            if (addr_phase_active && addr_phase_write) begin
                case (addr_phase_addr)
                    ADDR_CTRL: begin
                        reg_ctrl <= HWDATA;
                    end

                    ADDR_STATUS: begin
                        // -----------------------------------------------------
                        // INTENTIONAL BUG 1: Read-Only Register Write Protection Defect
                        // The specification requires asserting HRESP=1 (ERROR) on write to REG_STATUS.
                        // Bug: The designer silently dropped the write without asserting HRESP!
                        // -----------------------------------------------------
                        HRESP <= 1'b0; // DEFECT: Should be HRESP <= 1'b1;
                    end

                    ADDR_DATA0: begin
                        // -----------------------------------------------------
                        // INTENTIONAL BUG 2: Upper 16-bit Truncation Defect
                        // The designer incorrectly masked or truncated the upper 16 bits!
                        // Bug: reg_data0 <= {16'h0000, HWDATA[15:0]}; instead of full 32 bits!
                        // -----------------------------------------------------
                        reg_data0 <= {16'h0000, HWDATA[15:0]}; // DEFECT: Drops HWDATA[31:16]
                    end

                    ADDR_DATA1: begin
                        reg_data1 <= HWDATA; // Correct 32-bit retention
                    end

                    ADDR_BURST_CNT: begin
                        reg_burst_cnt <= HWDATA;
                    end

                    default: begin
                        // Unmapped address error response on write
                        HRESP <= 1'b1;
                    end
                endcase
            end else if (addr_phase_active && !addr_phase_write) begin
                if (addr_phase_addr > ADDR_BURST_CNT) begin
                    HRESP <= 1'b1;
                end
            end
        end
    end

    // -------------------------------------------------------------------------
    // Data Phase: Read Data Multiplexer
    // -------------------------------------------------------------------------
    always_comb begin
        if (addr_phase_active && !addr_phase_write) begin
            case (addr_phase_addr)
                ADDR_CTRL:      HRDATA = reg_ctrl;
                ADDR_STATUS:    HRDATA = reg_status;
                ADDR_DATA0:     HRDATA = reg_data0;
                ADDR_DATA1:     HRDATA = reg_data1;
                ADDR_BURST_CNT: HRDATA = reg_burst_cnt;
                default:        HRDATA = 32'hDEAD_0000;
            endcase
        end else begin
            HRDATA = 32'h0000_0000;
        end
    end

endmodule
