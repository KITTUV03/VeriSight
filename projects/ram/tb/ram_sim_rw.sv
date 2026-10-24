class ram_sim_rw_seq extends uvm_sequence#(ram_seq_item);
  `uvm_object_utils(ram_sim_rw_seq)
   `UVM_OBJ_CTOR(ram_sim_rw_seq)
  ram_seq_item ram_tx;
  task body();
    repeat(5)
      begin
        ram_tx=ram_seq_item::type_id::create("ram_tx");
        `uvm_info(get_type_name,"Enter in sim_rw task Body",UVM_LOW)

        start_item(ram_tx);
        ram_tx.randomize() with {op==SIM_RW;rst_n==1;};
                ram_tx.print();

        finish_item(ram_tx);
      end
  endtask

endclass