`ifndef AHB_DEFINES_SVH
`define AHB_DEFINES_SVH

`define AHB_ADDR_CTRL      32'h00
`define AHB_ADDR_STATUS    32'h04
`define AHB_ADDR_DATA0     32'h08
`define AHB_ADDR_DATA1     32'h0C
`define AHB_ADDR_BURST_CNT 32'h10
`define AHB_ADDR_UNMAPPED  32'h20

`define AHB_TR_IDLE   2'b00
`define AHB_TR_BUSY   2'b01
`define AHB_TR_NONSEQ 2'b10
`define AHB_TR_SEQ    2'b11

`define AHB_RESP_OKAY  1'b0
`define AHB_RESP_ERROR 1'b1

`endif // AHB_DEFINES_SVH
