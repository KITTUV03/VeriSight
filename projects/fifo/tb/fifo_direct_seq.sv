`ifndef SEQ
`define SEQ


class fifo_base_seq extends uvm_sequence#(fifo_trans);
  `uvm_object_utils(fifo_base_seq)
  `OBJ_CNSTR(fifo_base_seq)

  fifo_trans packet;

endclass

`endif