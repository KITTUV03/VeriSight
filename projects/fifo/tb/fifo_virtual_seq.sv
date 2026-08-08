
class fifo_virtual_seq extends uvm_sequence#(fifo_trans);
  `uvm_object_utils(fifo_virtual_seq)
  `OBJ_CNSTR(fifo_virtual_seq)

  extern task body();
endclass

task fifo_virtual_seq::body();
  fifo_reset_seq        reset_seq;
  fifo_write_seq        write_seq;
  fifo_read_seq         read_seq;
  fifo_sim_rw_seq       sim_seq;
  fifo_general_seq      gen_seq;
  fifo_memory_full_seq  mem_full_seq;
  fifo_memory_empty_seq mem_empty_seq;

  // Reset
  reset_seq = fifo_reset_seq::type_id::create("reset_seq");
  reset_seq.start(m_sequencer, this);

  // Normal writes
  repeat (4) begin
    write_seq = fifo_write_seq::type_id::create("write_seq");
    write_seq.start(m_sequencer, this);
  end

  // Normal reads
  repeat (4) begin
    read_seq = fifo_read_seq::type_id::create("read_seq");
    read_seq.start(m_sequencer, this);
  end

  reset_seq = fifo_reset_seq::type_id::create("reset_seq");
  reset_seq.start(m_sequencer, this);

  // Simultaneous WR/RD
  repeat (5) begin
    sim_seq = fifo_sim_rw_seq::type_id::create("sim_seq");
    sim_seq.start(m_sequencer, this);
  end

  reset_seq = fifo_reset_seq::type_id::create("reset_seq");
  reset_seq.start(m_sequencer, this);

  // Fill FIFO past DEPTH
  mem_full_seq = fifo_memory_full_seq::type_id::create("mem_full_seq");
  mem_full_seq.start(m_sequencer, this);

  reset_seq = fifo_reset_seq::type_id::create("reset_seq");
  reset_seq.start(m_sequencer, this);

  // Drain FIFO past empty
  mem_empty_seq = fifo_memory_empty_seq::type_id::create("mem_empty_seq");
  mem_empty_seq.start(m_sequencer, this);

  reset_seq = fifo_reset_seq::type_id::create("reset_seq");
  reset_seq.start(m_sequencer, this);

  // General operation
  gen_seq = fifo_general_seq::type_id::create("gen_seq");
  gen_seq.start(m_sequencer, this);

  reset_seq = fifo_reset_seq::type_id::create("reset_seq");
  reset_seq.start(m_sequencer, this);

endtask