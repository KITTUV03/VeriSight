
class fifo_reset_seq extends fifo_base_seq;
  `uvm_object_utils(fifo_reset_seq)
  `OBJ_CNSTR(fifo_reset_seq)

  extern task body();
endclass

task fifo_reset_seq::body();
  packet = fifo_trans::type_id::create("packet");
  start_item(packet);
  if (!packet.randomize() with { operations == RESET; })
    `uvm_error(get_type_name(), "Randomization failed")
  finish_item(packet);
endtask