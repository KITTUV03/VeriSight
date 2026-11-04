class ram_driver extends uvm_driver#(ram_seq_item);
  `uvm_component_utils(ram_driver)
  `UVM_COMP_CTOR(ram_driver)
   virtual ram_if inf;
    ram_seq_item ram_tx;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    uvm_config_db #(virtual ram_if)::get(this,"","inf",inf);
  endfunction
  
  task run_phase(uvm_phase phase);
    super.run_phase(phase);
      ram_tx = ram_seq_item::type_id::create("ram_tx", this);
    forever begin
      seq_item_port.get_next_item(ram_tx);
      send_to_dut(ram_tx);
      seq_item_port.item_done(); 
    end
  endtask
  
  task send_to_dut(ram_seq_item ram_tx);
    @(inf.drv_cb);
   if (!ram_tx.rst_n) 
     begin
      inf.drv_cb.rst_n <= 0;
      inf.drv_cb.we    <= 0;
      inf.drv_cb.addr  <= 0;
      inf.drv_cb.wdata <= 0;

	end
	else begin
    inf.drv_cb.rst_n <= 1;
    inf.drv_cb.we    <= ram_tx.we;
    inf.drv_cb.addr  <= ram_tx.addr;
      if(ram_tx.we)
        begin
   			 inf.drv_cb.wdata <= ram_tx.wdata;
        end
      else
        begin
   			 inf.drv_cb.wdata <= 0;
          ram_tx.rdata<=inf.drv_cb.rdata;
        end
        
	end

  endtask
  
  
endclass
