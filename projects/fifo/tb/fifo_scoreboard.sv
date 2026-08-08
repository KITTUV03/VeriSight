`ifndef FIFO_SCO
`define FIFO_SCO

`uvm_analysis_imp_decl(_active)
`uvm_analysis_imp_decl(_passive)


class fifo_scoreboard extends uvm_scoreboard;

  `uvm_component_utils(fifo_scoreboard)
  `COMP_CNSTR(fifo_scoreboard)

  virtual intf inf;

  uvm_analysis_imp_active  #(fifo_trans, fifo_scoreboard) ap_imp;
  uvm_analysis_imp_passive #(fifo_trans, fifo_scoreboard) pass_imp;

  fifo_trans active_q[$];
  fifo_trans passive_q[$];

  bit [`DATA_WIDTH-1:0] exp_DATA_OUT[$];
  bit                   exp_EMPTY;
  bit                   exp_FULL;
  bit [`ADDR_WIDTH:0]   status_count;
  bit [`DATA_WIDTH-1:0] exp_data;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(virtual intf)::get(this, "", "vif", inf))
      `uvm_fatal(get_type_name(), "Interface Not Received")

    ap_imp   = new("ap_imp", this);
    pass_imp = new("pass_imp", this);
  endfunction


  function void write_active(fifo_trans packet);
    fifo_trans cloned;
    if (!$cast(cloned, packet.clone()))
      `uvm_fatal(get_type_name(), "Failed to clone active transaction")

    active_q.push_back(cloned);
    `uvm_info(get_type_name(),
      $sformatf("Active Monitor Packet Received | QUEUE_SIZE=%0d", active_q.size()),
      UVM_HIGH)
  endfunction


  function void write_passive(fifo_trans packet1);
    fifo_trans cloned;
    if (!$cast(cloned, packet1.clone()))
      `uvm_fatal(get_type_name(), "Failed to clone passive transaction")

    passive_q.push_back(cloned);
    `uvm_info(get_type_name(),
      $sformatf("Passive Monitor Packet Received | QUEUE_SIZE=%0d", passive_q.size()),
      UVM_HIGH)
  endfunction


  task run_phase(uvm_phase phase);
    fifo_trans packet, packet1;
    forever begin
      wait (active_q.size() > 0 && passive_q.size() > 0);
      packet  = active_q.pop_front();
      packet1 = passive_q.pop_front();
      compare(packet, packet1);
    end
  endtask


  function void compare(fifo_trans packet, fifo_trans packet1);

    `uvm_info(get_type_name(),
      $sformatf("\n==================== FIFO TRANSACTION ====================\n\
WR_CS=%0b WR_EN=%0b RD_CS=%0b RD_EN=%0b\n\
DATA_IN =0x%0h DATA_OUT=0x%0h\n\
FULL=%0b EMPTY=%0b\n\
STATUS_COUNT=%0d QUEUE_SIZE=%0d\n\
============================================================",
      packet.WR_CS,
      packet.WR_EN,
      packet.RD_CS,
      packet.RD_EN,
      packet.DATA_IN,
      packet1.DATA_OUT,
      packet1.FULL,
      packet1.EMPTY,
      status_count,
      exp_DATA_OUT.size()),
      UVM_HIGH);

    exp_FULL  = (status_count == `DEPTH);
    exp_EMPTY = (status_count == 0);

    if (inf.RST == 0) begin

      if ((packet.WR_CS && packet.WR_EN && !exp_FULL) &&
          (packet.RD_CS && packet.RD_EN && !exp_EMPTY)) begin

        exp_DATA_OUT.push_back(packet.DATA_IN);
        exp_data = exp_DATA_OUT.pop_front();

        if (exp_data == packet1.DATA_OUT)
          `uvm_info(get_type_name(),
            $sformatf("SIMULTANEOUS WR/RD PASS | EXP=0x%0h ACT=0x%0h COUNT=%0d QUEUE_SIZE=%0d",
                      exp_data, packet1.DATA_OUT, status_count, exp_DATA_OUT.size()),
            UVM_LOW)
        else
          `uvm_error(get_type_name(),
            $sformatf("SIMULTANEOUS WR/RD FAIL | EXP=0x%0h ACT=0x%0h COUNT=%0d QUEUE_SIZE=%0d",
                      exp_data, packet1.DATA_OUT, status_count, exp_DATA_OUT.size()));

      end
      else if (packet.WR_CS && packet.WR_EN && !exp_FULL) begin

        exp_DATA_OUT.push_back(packet.DATA_IN);

        `uvm_info(get_type_name(),
          $sformatf("WRITE PASS | DATA_IN=0x%0h COUNT=%0d->%0d QUEUE_SIZE=%0d",
                    packet.DATA_IN, status_count, status_count+1, exp_DATA_OUT.size()),
          UVM_LOW);

        status_count = status_count + 1;

      end
      else if (packet.RD_CS && packet.RD_EN && !exp_EMPTY) begin

        if (exp_DATA_OUT.size() == 0) begin
          `uvm_error(get_type_name(), "Attempted to pop from an empty reference queue!");
        end
        else begin

          exp_data = exp_DATA_OUT.pop_front();

          if (exp_data == packet1.DATA_OUT)
            `uvm_info(get_type_name(),
              $sformatf("READ PASS | EXP=0x%0h ACT=0x%0h COUNT=%0d->%0d QUEUE_SIZE=%0d",
                        exp_data, packet1.DATA_OUT, status_count, status_count-1, exp_DATA_OUT.size()),
              UVM_LOW)
          else
            `uvm_error(get_type_name(),
              $sformatf("READ FAIL | EXP=0x%0h ACT=0x%0h COUNT=%0d->%0d QUEUE_SIZE=%0d",
                        exp_data, packet1.DATA_OUT, status_count, status_count-1, exp_DATA_OUT.size()));

        end

        status_count = status_count - 1;

      end
      else begin
        `uvm_info(get_type_name(),
          $sformatf("NO FIFO OPERATION | COUNT=%0d QUEUE_SIZE=%0d", status_count, exp_DATA_OUT.size()),
          UVM_LOW);
      end

      exp_FULL  = (status_count == `DEPTH);
      exp_EMPTY = (status_count == 0);

      if (exp_FULL === packet1.FULL)
        `uvm_info(get_type_name(),
          $sformatf("FULL FLAG PASS | Expected=%0b Actual=%0b COUNT=%0d",
                    exp_FULL, packet1.FULL, status_count),
          UVM_LOW)
      else
        `uvm_error(get_type_name(),
          $sformatf("FULL FLAG FAIL | Expected=%0b Actual=%0b COUNT=%0d",
                    exp_FULL, packet1.FULL, status_count));

   
      if (exp_EMPTY === packet1.EMPTY)
        `uvm_info(get_type_name(),
          $sformatf("EMPTY FLAG PASS | Expected=%0b Actual=%0b COUNT=%0d",
                    exp_EMPTY, packet1.EMPTY, status_count),
          UVM_LOW)
      else
        `uvm_error(get_type_name(),
          $sformatf("EMPTY FLAG FAIL | Expected=%0b Actual=%0b COUNT=%0d",
                    exp_EMPTY, packet1.EMPTY, status_count));

      `uvm_info(get_type_name(),
        $sformatf("SCOREBOARD STATUS | COUNT=%0d FULL=%0b EMPTY=%0b QUEUE_SIZE=%0d",
                  status_count, exp_FULL, exp_EMPTY, exp_DATA_OUT.size()),
        UVM_HIGH);

    end
    else begin
      exp_DATA_OUT.delete();
      status_count = 0;
    end

  endfunction

endclass

`endif