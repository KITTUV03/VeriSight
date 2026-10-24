class ram_monitor extends uvm_monitor;
  `uvm_component_utils(ram_monitor)
  `UVM_COMP_CTOR(ram_monitor)

  virtual ram_if inf;
  uvm_analysis_port #(ram_seq_item) mon_ap;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(virtual ram_if)::get(this,"","inf",inf))
      `uvm_fatal("RAM_MON","Virtual interface not set");
    mon_ap = new("mon_ap", this);
  endfunction

  task run_phase(uvm_phase phase);
    ram_seq_item tx;

    forever begin
      @(inf.mon_cb);

      if (!inf.mon_cb.rst_n)
        continue;

      tx = ram_seq_item::type_id::create("tx", this);

      // Capture command
      tx.we    = inf.mon_cb.we;
      tx.addr  = inf.mon_cb.addr;
      tx.wdata = inf.mon_cb.wdata;

      // Handle READ latency (1-cycle)
      if (!tx.we) begin
        @(inf.mon_cb);
        tx.rdata = inf.mon_cb.rdata;
      end

      mon_ap.write(tx);
    end
  endtask
endclass
