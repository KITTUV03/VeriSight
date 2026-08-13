`ifndef PASS_MON
`define PASS_MON

class fifo_passive extends uvm_monitor;

  `uvm_component_utils(fifo_passive)
  `COMP_CNSTR(fifo_passive)

  virtual intf inf;

  uvm_analysis_port #(fifo_trans) pass_port;

  extern function void build_phase(uvm_phase phase);
  extern task run_phase(uvm_phase phase);

endclass

`endif


function void fifo_passive::build_phase(uvm_phase phase);
  if (!uvm_config_db #(virtual intf)::get(this, "", "vif", inf))
    `uvm_fatal(get_type_name(), "Interface Not Received")

  pass_port = new("pass_port", this);
endfunction


task fifo_passive::run_phase(uvm_phase phase);
  fifo_trans packet;

  wait(inf.RST == 0);
  @(posedge inf.CLK); #1;

  forever begin
    @(posedge inf.CLK); #1;

    packet = fifo_trans::type_id::create("packet", this);

    packet.DATA_OUT = inf.DATA_OUT;
    packet.FULL     = inf.FULL;
    packet.EMPTY    = inf.EMPTY;

    pass_port.write(packet);
  end
endtask