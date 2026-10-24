class ram_write_seq extends uvm_sequence#(ram_seq_item);
  `uvm_object_utils(ram_write_seq)
   `UVM_OBJ_CTOR(ram_write_seq)
  ram_seq_item ram_tx;
  task body();
    repeat(10)
      begin
        `uvm_info(get_type_name,"Enter in write_seq task Body",UVM_LOW)
        ram_tx=ram_seq_item::type_id::create("ram_tx");
        start_item(ram_tx);
        ram_tx.randomize() with {op==WRITE_OP;we==1;rst_n==1;};
        ram_tx.print();
        finish_item(ram_tx);
      end
  endtask

endclass