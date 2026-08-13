`ifndef FIFO_DEFINES_SVH
`define FIFO_DEFINES_SVH

`define DATA_WIDTH 8

`define COMP_CNSTR(class_name) \
  function new(string name, uvm_component parent); \
    super.new(name, parent); \
  endfunction

`define OBJ_CNSTR(class_name) \
  function new(string name = "class_name"); \
    super.new(name); \
  endfunction

`endif
