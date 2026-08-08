`ifndef MON
`define MON

class fifo_monitor extends uvm_monitor;
  `uvm_component_utils(fifo_monitor)
  `COMP_CNSTR(fifo_monitor)
  virtual intf inf;
  fifo_trans packet;

  uvm_analysis_port #(fifo_trans) ap_port;

  extern function void build_phase(uvm_phase phase);
  extern task run_phase(uvm_phase phase);
 // extern task get_from_dut();
endclass
  
  
`endif


  
  function void fifo_monitor::build_phase(uvm_phase phase);
    if (!uvm_config_db #(virtual intf) :: get(this," ","vif",inf))
      `uvm_fatal(get_type_name(),"Interface Not Received")
      
      ap_port=new("ap_port",this);
  endfunction
      

    
task fifo_monitor::run_phase(uvm_phase phase);
  bit temp_wr_cs, temp_wr_en, temp_rd_cs, temp_rd_en;
  bit [`DATA_WIDTH-1:0] temp_din;
  bit prev;

  wait(inf.RST == 0);   
  prev = 0;

  forever begin
    @(inf.mon_cb);

   
    if (prev) begin
      packet = fifo_trans::type_id::create("packet");
      packet.WR_CS    = temp_wr_cs;
      packet.WR_EN    = temp_wr_en;
      packet.RD_CS    = temp_rd_cs;
      packet.RD_EN    = temp_rd_en;
      packet.DATA_IN  = temp_din;
      packet.DATA_OUT = inf.mon_cb.DATA_OUT;
      packet.FULL     = inf.mon_cb.FULL;
      packet.EMPTY    = inf.mon_cb.EMPTY;

      ap_port.write(packet);
    end

    temp_wr_cs   = inf.mon_cb.WR_CS;
    temp_wr_en   = inf.mon_cb.WR_EN;
    temp_rd_cs   = inf.mon_cb.RD_CS;
    temp_rd_en   = inf.mon_cb.RD_EN;
    temp_din = inf.mon_cb.DATA_IN;
    prev = 1;
  end
endtask
