 
typedef enum logic [1:0] {
  WRITE_OP = 2'b00,
  READ_OP  = 2'b01,
  SIM_RW   = 2'b10,
  RESET_OP = 2'b11
} type_e;

class ram_seq_item extends uvm_sequence_item; 
  `UVM_OBJ_CTOR(ram_seq_item)
  
  rand bit rst_n;
 	rand bit we;
 	rand bit [`ADDR_WIDTH-1:0] addr;
 	rand bit [`DATA_WIDTH-1:0] wdata;
  rand type_e op;
  bit [`DATA_WIDTH-1:0] rdata;
  
   `uvm_object_utils_begin(ram_seq_item)
    `uvm_field_int(we,    UVM_ALL_ON | UVM_DEC)
    `uvm_field_int(addr,  UVM_ALL_ON | UVM_DEC)
    `uvm_field_int(wdata, UVM_ALL_ON | UVM_DEC)
    `uvm_field_int(rdata, UVM_ALL_ON | UVM_DEC)
  `uvm_object_utils_end
  
  constraint range_addr
  {
    addr inside {[0:2]};
  }
  
 
  
 
endclass