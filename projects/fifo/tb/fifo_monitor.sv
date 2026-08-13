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
    @(posedge inf.CLK);
    #1; // input skew, matches the original clocking block's `default input #1`

    if (prev) begin
      packet = fifo_trans::type_id::create("packet");
      packet.WR_CS    = temp_wr_cs;
      packet.WR_EN    = temp_wr_en;
      packet.RD_CS    = temp_rd_cs;
      packet.RD_EN    = temp_rd_en;
      packet.DATA_IN  = temp_din;
      packet.DATA_OUT = inf.DATA_OUT;
      packet.FULL     = inf.FULL;
      packet.EMPTY    = inf.EMPTY;

      ap_port.write(packet);
    end

    temp_wr_cs   = inf.WR_CS;
    temp_wr_en   = inf.WR_EN;
    temp_rd_cs   = inf.RD_CS;
    temp_rd_en   = inf.RD_EN;
    temp_din = inf.DATA_IN;
    prev = 1;
  end
endtask
