`ifndef SUBS
`define SUBS

class subscriber extends uvm_subscriber #(fifo_trans);

  `uvm_component_utils(subscriber)
   fifo_trans packet;

  covergroup cvg;

    coverpoint packet.WR_EN;
    coverpoint packet.RD_EN;
    coverpoint packet.WR_CS;
    coverpoint packet.RD_CS;


  endgroup
  
  function new(string name="subscriber",uvm_component parent);
    super.new(name,parent);
    cvg = new();
  endfunction


  
  function void write(fifo_trans t);
    packet = t;
    cvg.sample();
  endfunction
  
  
  function void report_phase(uvm_phase phase);
    $display("%0f",cvg.get_coverage());
  endfunction
  

endclass

`endif