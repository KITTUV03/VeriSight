class fifo_memory_empty_seq extends uvm_sequence#(fifo_trans);
  `uvm_object_utils(fifo_memory_empty_seq)
  `OBJ_CNSTR(fifo_memory_empty_seq)

  extern task body();
endclass

task fifo_memory_empty_seq::body();
  fifo_read_seq rd_seq;
  repeat (257) begin
    rd_seq = fifo_read_seq::type_id::create("rd_seq");
    rd_seq.start(m_sequencer, this);
  end
endtask
