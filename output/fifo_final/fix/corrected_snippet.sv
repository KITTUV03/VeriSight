ram_dp_ar_aw #(DATA_WIDTH,ADDR_WIDTH) DP_RAM (
  .clk     (clk),
.address_0 (wr_pointer) , // address_0 input
.data_0    (data_in)    , // data_0 bi-directional
.cs_0      (wr_cs)      , // chip select
.we_0      (wr_valid)   , // write enable (qualified: wr_cs && wr_en && !full)
.oe_0      (1'b0)       , // output enable


.address_1 (rd_pointer) , // address_1 input
.data_1    (data_ram)   , // data_1 bi-directional
.cs_1      (rd_cs)      , // chip select
.we_1      (1'b0)       , // Read enable
.oe_1      (rd_valid)     // output enable (qualified: rd_cs && rd_en && !empty)
);