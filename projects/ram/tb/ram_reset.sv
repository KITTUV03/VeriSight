class ram_reset extends uvm_sequence#(ram_seq_item);
  `uvm_object_utils(ram_reset)
   `UVM_OBJ_CTOR(ram_reset)
  ram_seq_item ram_tx;
  task body();
    repeat(5)
      begin
        ram_tx=ram_seq_item::type_id::create("ram_tx");
        `uvm_info(get_type_name,"Enter in reset task Body",UVM_LOW)

        start_item(ram_tx);
        ram_tx.randomize() with {op==RESET_OP;rst_n==0;};
                ram_tx.print();

        finish_item(ram_tx);
      end
  endtask

endclass