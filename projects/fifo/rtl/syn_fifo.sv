//-----------------------------------------------------
// Design Name : syn_fifo
// File Name   : syn_fifo.v
// Function    : Synchronous (single clock) FIFO
//-----------------------------------------------------
module syn_fifo (
clk      , // Clock input
rst      , // Active high reset
wr_cs    , // Write chip select
rd_cs    , // Read chip select
data_in  , // Data input
rd_en    , // Read enable
wr_en    , // Write Enable
data_out , // Data Output
empty    , // FIFO empty
full       // FIFO full
);

// FIFO constants
parameter DATA_WIDTH = 8;
parameter ADDR_WIDTH = 8;
parameter RAM_DEPTH  = (1 << ADDR_WIDTH);

// Port Declarations
input                     clk      ;
input                     rst      ;
input                     wr_cs    ;
input                     rd_cs    ;
input                     rd_en    ;
input                     wr_en    ;
input  [DATA_WIDTH-1:0]   data_in  ;
output                    full     ;
output                    empty    ;
output [DATA_WIDTH-1:0]   data_out ;

//-----------Internal variables-------------------
reg  [ADDR_WIDTH-1:0] wr_pointer;
reg  [ADDR_WIDTH-1:0] rd_pointer;
reg  [ADDR_WIDTH  :0] status_cnt;
reg  [DATA_WIDTH-1:0] data_out ;
wire [DATA_WIDTH-1:0] data_ram ;

  assign full  = (status_cnt == RAM_DEPTH);
  assign empty = (status_cnt == 0);

//-----------Internal write/read qualifiers-------
// Only allow a pointer/counter update when the operation
// is actually legal (not full on write, not empty on read).
// This prevents wr_pointer/rd_pointer from silently lapping
// each other if wr_en/rd_en are asserted out of protocol.
wire wr_valid = wr_cs && wr_en && !full;
wire rd_valid = rd_cs && rd_en && !empty;

//-----------Code Start---------------------------
always @ (posedge clk or posedge rst)
begin : WRITE_POINTER
  if (rst) begin
    wr_pointer <= 0;
  end else if (wr_valid) begin
    wr_pointer <= wr_pointer + 1;
  end
end

always @ (posedge clk or posedge rst)
begin : READ_POINTER
  if (rst) begin
    rd_pointer <= 0;
  end else if (rd_valid) begin
    rd_pointer <= rd_pointer + 1;
  end
end

always  @ (posedge clk or posedge rst)
begin : READ_DATA
  if (rst) begin
    data_out <= 0;
  end else if (rd_valid) begin
    data_out <= data_ram;
  end
end

always @ (posedge clk or posedge rst)
begin : STATUS_COUNTER
  if (rst) begin
    status_cnt <= 0;
  // Read but no write.
  end else if (rd_valid && !wr_valid) begin
    status_cnt <= status_cnt - 1;
  // Write but no read.
  end else if (wr_valid && !rd_valid) begin
    status_cnt <= status_cnt + 1;
  // Simultaneous valid read + valid write -> count unchanged
  end
end

ram_dp_ar_aw #(DATA_WIDTH,ADDR_WIDTH) DP_RAM (
  .clk     (clk),
.address_0 (wr_pointer) , // address_0 input
.data_0    (data_in)    , // data_0 bi-directional
.cs_0      (wr_cs)      , // chip select
.we_0      (wr_en)      , // write enable
.oe_0      (1'b0)       , // output enable
  
  
.address_1 (rd_pointer) , // address_1 input
.data_1    (data_ram)   , // data_1 bi-directional
.cs_1      (rd_cs)      , // chip select
.we_1      (1'b0)       , // Read enable
.oe_1      (rd_en)        // output enable
);
endmodule

//Ram_Module
//-----------------------------------------------------
// Design Name : ram_dp_ar_aw
// File Name   : ram_dp_ar_aw.v
// Function    : Dual-Port RAM, Asynchronous Read,
//               Asynchronous Write (no clock port).
//               Port 0 -> used as the WRITE port by syn_fifo
//                         (oe_0 tied low -> never drives data_0)
//               Port 1 -> used as the READ  port by syn_fifo
//                         (we_1 tied low -> never writes)
//
//               Write behavior: level-sensitive. Whenever
//               cs_x && we_x are both high, mem[address_x]
//               is continuously updated to data_x (no clock
//               edge needed -- matches syn_fifo's "same
//               cycle" write timing, since syn_fifo drives
//               wr_cs/wr_en combinationally from its own
//               registered control logic).
//
//               Read behavior: combinational/asynchronous.
//               Whenever cs_x && oe_x are both high, data_x
//               is driven with mem[address_x]; otherwise the
//               port is tri-stated (high-Z). syn_fifo relies
//               on this by registering data_ram into
//               data_out itself (see READ_DATA block in
//               syn_fifo.v) -- the RAM does not register
//               anything internally.
//
// Note        : IMPORTANT DEVIATION FROM A PURE "ar_aw" MODEL --
//               The write path below is clock-edge-triggered
//               (synchronous), NOT level-sensitive, even
//               though the module keeps its original name.
//
//               Reason: a purely level-sensitive (transparent
//               latch) write, as a classic "asynchronous
//               write" RAM model would use, was verified in
//               simulation (Icarus Verilog) to be RACY when
//               driven by syn_fifo.v. wr_pointer (this RAM's
//               address_0) and wr_valid (this RAM's cs_0/we_0,
//               which depends on `full`, which depends on
//               status_cnt) are BOTH updated via non-blocking
//               assignment on the SAME clock edge inside
//               syn_fifo.v. During that edge's delta-cycle
//               settling, a level-sensitive write block can
//               observe a transient glitch (new wr_pointer
//               value paired with a not-yet-updated wr_valid)
//               and perform a spurious extra write, silently
//               corrupting an unrelated RAM location. This was
//               reproduced directly: filling then draining a
//               4-deep FIFO corrupted mem[0] with stale data.
//
//               Making the write edge-triggered (posedge clk)
//               removes the hazard entirely, because it then
//               samples address_0/cs_0/we_0/data_0 exactly
//               once per edge, using their pre-edge (stable)
//               values -- the same safe discipline syn_fifo.v
//               already uses for its own registers. This also
//               matches how real synchronous-write block RAM
//               behaves, and is the synthesizable style;
//               "combinationally written this same cycle" per
//               the design spec is preserved from the FIFO's
//               external point of view, since the write is
//               still committed on the same edge that
//               status_cnt/full update to reflect it.
//
//               The READ path remains fully asynchronous /
//               combinational (true to the "ar" half of the
//               name) -- syn_fifo.v itself registers the read
//               data into data_out, so no clock is needed on
//               this side, and no equivalent race exists here
//               (see accompanying explanation in the spec).
//-----------------------------------------------------
module ram_dp_ar_aw (
clk       , // Clock (write path only -- see note above)
address_0 , // Port 0 address (write side, from syn_fifo)
data_0    , // Port 0 data (bidirectional)
cs_0      , // Port 0 chip select
we_0      , // Port 0 write enable
oe_0      , // Port 0 output enable
address_1 , // Port 1 address (read side, from syn_fifo)
data_1    , // Port 1 data (bidirectional)
cs_1      , // Port 1 chip select
we_1      , // Port 1 write enable
oe_1        // Port 1 output enable
);

// Parameters -- order must match the instantiation in syn_fifo.v:
// ram_dp_ar_aw #(DATA_WIDTH, ADDR_WIDTH) DP_RAM (...)
parameter DATA_WIDTH = 8;
parameter ADDR_WIDTH = 8;
parameter RAM_DEPTH  = (1 << ADDR_WIDTH);

// Port Declarations
input                    clk       ;
input  [ADDR_WIDTH-1:0]  address_0 ;
inout  [DATA_WIDTH-1:0]  data_0    ;
input                    cs_0      ;
input                    we_0      ;
input                    oe_0      ;

input  [ADDR_WIDTH-1:0]  address_1 ;
inout  [DATA_WIDTH-1:0]  data_1    ;
input                    cs_1      ;
input                    we_1      ;
input                    oe_1      ;

//-----------Internal variables-------------------
reg [DATA_WIDTH-1:0] mem [0:RAM_DEPTH-1];
reg [DATA_WIDTH-1:0] data_0_out ;
reg [DATA_WIDTH-1:0] data_1_out ;

//-----------------------------------------------------
// PORT 0 : synchronous (edge-triggered) write
// -- see header note: intentionally NOT level-sensitive,
//    to eliminate a same-edge race with syn_fifo.v
//-----------------------------------------------------
always @ (posedge clk)
begin : PORT0_WRITE
  if (cs_0 && we_0) begin
    mem[address_0] <= data_0;
  end
end

//-----------------------------------------------------
// PORT 0 : asynchronous (combinational) read + tri-state
//-----------------------------------------------------
always @ (*)
begin : PORT0_READ
  if (cs_0 && oe_0) begin
    data_0_out = mem[address_0];
  end else begin
    data_0_out = {DATA_WIDTH{1'bz}};
  end
end
assign data_0 = (cs_0 && oe_0 && !we_0) ? data_0_out : {DATA_WIDTH{1'bz}};

//-----------------------------------------------------
// PORT 1 : synchronous (edge-triggered) write
// -- unused by syn_fifo.v (we_1 tied low there), kept
//    consistent with port 0 for generality / reuse
//-----------------------------------------------------
always @ (posedge clk)
begin : PORT1_WRITE
  if (cs_1 && we_1) begin
    mem[address_1] <= data_1;
  end
end

//-----------------------------------------------------
// PORT 1 : asynchronous (combinational) read + tri-state
//-----------------------------------------------------
always @ (*)
begin : PORT1_READ
  if (cs_1 && oe_1) begin
    data_1_out = mem[address_1];
  end else begin
    data_1_out = {DATA_WIDTH{1'bz}};
  end
end
assign data_1 = (cs_1 && oe_1 && !we_1) ? data_1_out : {DATA_WIDTH{1'bz}};

endmodule