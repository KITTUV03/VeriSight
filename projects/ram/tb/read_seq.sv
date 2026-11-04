class ram_read_seq extends uvm_sequence#(ram_seq_item);
  `uvm_object_utils(ram_read_seq)
   `UVM_OBJ_CTOR(ram_read_seq)
  ram_seq_item ram_tx;
  task body();
    repeat(10)
      begin
        ram_tx=ram_seq_item::type_id::create("ram_tx");
        `uvm_info(get_type_name,"Enter in read_seq task Body",UVM_LOW)
        start_item(ram_tx);
        ram_tx.randomize() with {op==READ_OP;we==0;rst_n==1;};
                ram_tx.print();

        finish_item(ram_tx);
      end
  endtask

endclass