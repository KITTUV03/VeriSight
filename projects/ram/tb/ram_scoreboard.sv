class ram_scoreboard extends uvm_scoreboard;
  `uvm_component_utils(ram_scoreboard)
  `UVM_COMP_CTOR(ram_scoreboard)

  uvm_analysis_imp #(ram_seq_item, ram_scoreboard) mon_imp;
  bit [31:0] memory[int];

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    mon_imp = new("mon_imp", this);
  endfunction

  function void write(ram_seq_item tr);
    if (tr.we) begin
      // WRITE
      memory[tr.addr] = tr.wdata;
    end
    else begin
      // READ
      if (memory.exists(tr.addr)) begin
        if (tr.rdata !== memory[tr.addr])
          `uvm_error("RAM_SB",
            $sformatf("Mismatch @addr %0d EXP=%0d ACT=%0d",
                      tr.addr, memory[tr.addr], tr.rdata))
        else
          `uvm_info("RAM_SB",
            $sformatf("Match @addr %0d DATA=%0d",
                      tr.addr, tr.rdata),
            UVM_LOW)
      end
      else begin
        `uvm_warning("RAM_SB",
          $sformatf("Read from uninitialized addr %0d", tr.addr))
      end
    end
  endfunction
endclass
