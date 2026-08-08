
class fifo_sim_rw_seq extends fifo_base_seq;
  `uvm_object_utils(fifo_sim_rw_seq)
  `OBJ_CNSTR(fifo_sim_rw_seq)

  extern task body();
endclass

task fifo_sim_rw_seq::body();
  packet = fifo_trans::type_id::create("packet");
  start_item(packet);
  if (!packet.randomize() with { operations == SIM_RW; })
    `uvm_error(get_type_name(), "Randomization failed")
  finish_item(packet);
endtask