`ifndef DRV
`define DRV

class fifo_driver extends uvm_driver#(fifo_trans);
  `uvm_component_utils(fifo_driver)
  `COMP_CNSTR(fifo_driver)
  virtual intf inf;
  
  extern function void build_phase(uvm_phase phase);
  extern task clear_all;
  extern task run_phase(uvm_phase phase);
  extern task send_to_dut(fifo_trans packet);
endclass
  
  
`endif


  
  function void fifo_driver::build_phase(uvm_phase phase);
    if (!uvm_config_db #(virtual intf) :: get(this," ","vif",inf))
      `uvm_fatal(get_type_name(),"Interface Not Received")
  endfunction
      
 task fifo_driver::clear_all;
   inf.drv_cb.WR_CS <= 0;
   inf.drv_cb.WR_EN <= 0;
   inf.drv_cb.RD_CS <= 0;
   inf.drv_cb.RD_EN <= 0;
   inf.drv_cb.DATA_IN <= 'b0;
 endtask
    
 task fifo_driver::run_phase(uvm_phase phase);
   clear_all;

   wait(inf.RST == 0);
   forever begin
     seq_item_port.get_next_item(req);
     send_to_dut(req);
     //req.print();
     seq_item_port.item_done();
   end
 endtask
    
 task fifo_driver::send_to_dut(fifo_trans packet);
   inf.drv_cb.WR_CS <= packet.WR_CS;
   inf.drv_cb.WR_EN <= packet.WR_EN;
   inf.drv_cb.RD_CS <= packet.RD_CS;
   inf.drv_cb.RD_EN <= packet.RD_EN;
   inf.drv_cb.DATA_IN <= packet.DATA_IN;
//    end
  @(inf.drv_cb);
  clear_all;
//    begin
//      wait(inf.RST==1);
//    end
     
//    join_any
//    disable fork;
     
//    if(inf.RST==1)
//      clear_all;
     
 endtask
