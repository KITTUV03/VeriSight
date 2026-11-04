`define ADDR_WIDTH 4
`define DATA_WIDTH 8

`define UVM_COMP_CTOR(CLASS_NAME)                           \
function new(string name=`"CLASS_NAME`", uvm_component parent);          \
    super.new(name, parent);                                \
  endfunction

`define UVM_OBJ_CTOR(CLASS_NAME)                        \
  function new(string name = `"CLASS_NAME`");          \
    super.new(name);                                   \
  endfunction
