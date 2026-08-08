class fifo_memory_full_seq extends uvm_sequence#(fifo_trans);
  `uvm_object_utils(fifo_memory_full_seq)
  `OBJ_CNSTR(fifo_memory_full_seq)

  extern task body();
endclass

task fifo_memory_full_seq::body();
  fifo_write_seq wr_seq;
  repeat (257) begin
    wr_seq = fifo_write_seq::type_id::create("wr_seq");
    wr_seq.start(m_sequencer, this);
  end
endtask