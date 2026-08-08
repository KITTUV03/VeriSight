`ifndef FIFO_TRANS
`define FIFO_TRANS

typedef enum {RESET,WRITE,READ,SIM_RW,GENERAL,RANDOM} operation;


class fifo_trans extends uvm_sequence_item;

  `OBJ_CNSTR(fifo_trans)
  rand bit WR_CS;
  rand bit WR_EN;
  rand bit RD_CS;
  rand bit RD_EN;
  rand bit [`DATA_WIDTH-1:0] DATA_IN;
  rand operation operations;
  bit [`DATA_WIDTH-1:0] DATA_OUT;
  bit EMPTY;
  bit FULL;

  extern constraint fifo_operations;

  `uvm_object_utils_begin(fifo_trans)
  `uvm_field_enum(operation,operations,UVM_ALL_ON)
  `uvm_field_int(WR_CS,UVM_ALL_ON | UVM_BIN)
  `uvm_field_int(WR_EN,UVM_ALL_ON | UVM_BIN)
  `uvm_field_int(RD_CS,UVM_ALL_ON | UVM_BIN)
  `uvm_field_int(RD_EN,UVM_ALL_ON | UVM_BIN)
  `uvm_field_int(DATA_IN,UVM_ALL_ON | UVM_DEC)
  `uvm_field_int(DATA_OUT,UVM_ALL_ON | UVM_DEC)
  `uvm_field_int(EMPTY,UVM_ALL_ON | UVM_BIN)
  `uvm_field_int(FULL,UVM_ALL_ON | UVM_BIN)
  `uvm_object_utils_end

endclass

`endif

constraint fifo_trans::fifo_operations
{
  (operations == RESET)  -> ({WR_CS==0 && WR_EN==0 && RD_CS==0 &&RD_EN==0});
  (operations == WRITE)  -> ({WR_CS==1 && WR_EN==1 && RD_CS==0 && RD_EN==0});
  (operations == READ)   ->  ({WR_CS==0 && WR_EN==0 && RD_CS==1 && RD_EN==1});
  (operations == SIM_RW) -> ({WR_CS==1 && WR_EN==1 && RD_CS==1 && RD_EN==1});
  (operations == GENERAL) -> ({WR_CS==1 && WR_EN==0 && RD_CS==1 && RD_EN==0});
}