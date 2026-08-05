interface fifo_if #(
    parameter DATA_WIDTH = 8,
    parameter ADDR_WIDTH = 4
)(
    input logic clk,
    input logic rst_n
);
    logic                     wr_en;
    logic                     rd_en;
    logic [DATA_WIDTH-1:0]    din;
    logic [DATA_WIDTH-1:0]    dout;
    logic                     full;
    logic                     empty;
    logic                     almost_full;
    logic                     almost_empty;
    logic                     overflow;
    logic                     underflow;
    logic [ADDR_WIDTH:0]      wr_count;
    logic [ADDR_WIDTH:0]      rd_count;
    
    // Clocking blocks for driver and monitor
    clocking drv_cb @(posedge clk);
        output wr_en, rd_en, din;
        input  full, empty, almost_full, almost_empty;
    endclocking
    
    clocking mon_cb @(posedge clk);
        input wr_en, rd_en, din, dout, full, empty;
        input almost_full, almost_empty, overflow, underflow;
        input wr_count, rd_count;
    endclocking
    
    // Assertions for protocol checking
    property no_write_when_full;
        @(posedge clk) disable iff (!rst_n)
        (full && wr_en) |-> ##1 overflow;
    endproperty
    
    property no_read_when_empty;
        @(posedge clk) disable iff (!rst_n)
        (empty && rd_en) |-> ##1 underflow;
    endproperty
    
    ASSERT_NO_WRITE_FULL: assert property(no_write_when_full)
        else $error("Write attempted when FIFO full!");
    
    ASSERT_NO_READ_EMPTY: assert property(no_read_when_empty)
        else $error("Read attempted when FIFO empty!");
    
endinterface

package fifo_test_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    
    // Transaction class
    class fifo_transaction extends uvm_sequence_item;
        rand bit wr_en;
        rand bit rd_en;
        rand bit [7:0] din;
        
        constraint reasonable_ops {
            wr_en dist {0:=30, 1:=70};
            rd_en dist {0:=30, 1:=70};
        }
        
        `uvm_object_utils_begin(fifo_transaction)
            `uvm_field_int(wr_en, UVM_ALL_ON)
            `uvm_field_int(rd_en, UVM_ALL_ON)
            `uvm_field_int(din, UVM_ALL_ON)
        `uvm_object_utils_end
        
        function new(string name = "fifo_transaction");
            super.new(name);
        endfunction
    endclass
    
    // Sequence
    class fifo_sequence extends uvm_sequence #(fifo_transaction);
        `uvm_object_utils(fifo_sequence)
        
        function new(string name = "fifo_sequence");
            super.new(name);
        endfunction
        
        task body();
            repeat(500) begin
                fifo_transaction trans;
                trans = fifo_transaction::type_id::create("trans");
                start_item(trans);
                assert(trans.randomize());
                finish_item(trans);
            end
        endtask
    endclass
    
    // Driver
    class fifo_driver extends uvm_driver #(fifo_transaction);
        `uvm_component_utils(fifo_driver)
        
        virtual fifo_if vif;
        
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        
        task run_phase(uvm_phase phase);
            forever begin
                fifo_transaction trans;
                seq_item_port.get_next_item(trans);
                
                @(vif.drv_cb);
                vif.drv_cb.wr_en <= trans.wr_en;
                vif.drv_cb.rd_en <= trans.rd_en;
                vif.drv_cb.din   <= trans.din;
                
                seq_item_port.item_done();
            end
        endtask
    endclass
    
    // Monitor
    class fifo_monitor extends uvm_monitor;
        `uvm_component_utils(fifo_monitor)
        
        virtual fifo_if vif;
        uvm_analysis_port #(fifo_transaction) item_collected_port;
        
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            item_collected_port = new("item_collected_port", this);
        endfunction
        
        task run_phase(uvm_phase phase);
            forever begin
                @(vif.mon_cb);
                // Monitor and collect transactions
            end
        endtask
    endclass
    
    // Scoreboard
    class fifo_scoreboard extends uvm_scoreboard;
        `uvm_component_utils(fifo_scoreboard)
        
        virtual fifo_if vif;
        
        logic [7:0] expected_queue [$];
        int unsigned wr_ptr_model, rd_ptr_model;
        int unsigned count_model;
        
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        
        task run_phase(uvm_phase phase);
            wr_ptr_model = 0;
            rd_ptr_model = 0;
            count_model = 0;
            
            forever begin
                @(posedge vif.clk);
                if (!vif.rst_n) begin
                    expected_queue.delete();
                    wr_ptr_model = 0;
                    rd_ptr_model = 0;
                    count_model = 0;
                end else begin
                    // Model write
                    if (vif.mon_cb.wr_en && !(count_model == 16)) begin
                        expected_queue.push_back(vif.mon_cb.din);
                        wr_ptr_model = (wr_ptr_model + 1) % 16;
                        count_model++;
                    end
                    
                    // Model read
                    if (vif.mon_cb.rd_en && count_model > 0) begin
                        expected_queue.pop_front();
                        rd_ptr_model = (rd_ptr_model + 1) % 16;
                        count_model--;
                    end
                    
                    // Check outputs against model
                    check_outputs();
                end
            end
        endtask
        
        function void check_outputs();
            // Check FIFO count
            if (vif.mon_cb.wr_count !== count_model) begin
                `uvm_error("SCOREBOARD", 
                    $sformatf("FIFO count mismatch: Expected %0d, Got %0d", 
                    count_model, vif.mon_cb.wr_count))
            end
            
            // Check full flag
            if ((count_model == 15) !== vif.mon_cb.full) begin
                `uvm_error("SCOREBOARD", 
                    $sformatf("Full flag mismatch: Expected %0b, Got %0b", 
                    (count_model == 15), vif.mon_cb.full))
            end
            
            // Check empty flag
            if ((count_model == 0) !== vif.mon_cb.empty) begin
                `uvm_error("SCOREBOARD", 
                    $sformatf("Empty flag mismatch: Expected %0b, Got %0b", 
                    (count_model == 0), vif.mon_cb.empty))
            end
            
            // Check overflow
            if (vif.mon_cb.overflow && !(vif.mon_cb.wr_en && vif.mon_cb.full)) begin
                `uvm_error("SCOREBOARD", "False overflow detected")
            end
            
            // Check underflow
            if (vif.mon_cb.underflow && !(vif.mon_cb.rd_en && vif.mon_cb.empty)) begin
                `uvm_error("SCOREBOARD", "False underflow detected")
            end
        endfunction
    endclass
    
    // Environment
    class fifo_env extends uvm_env;
        `uvm_component_utils(fifo_env)
        
        fifo_driver driver;
        fifo_monitor monitor;
        fifo_scoreboard scoreboard;
        
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            driver = fifo_driver::type_id::create("driver", this);
            monitor = fifo_monitor::type_id::create("monitor", this);
            scoreboard = fifo_scoreboard::type_id::create("scoreboard", this);
        endfunction
        
        function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
            monitor.item_collected_port.connect(scoreboard.analysis_export);
        endfunction
    endclass
    
    // Test
    class fifo_test extends uvm_test;
        `uvm_component_utils(fifo_test)
        
        fifo_env env;
        fifo_sequence seq;
        
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            env = fifo_env::type_id::create("env", this);
            seq = fifo_sequence::type_id::create("seq");
        endfunction
        
        task run_phase(uvm_phase phase);
            phase.raise_objection(this);
            seq.start(env.driver.sequencer);
            #1000;
            phase.drop_objection(this);
        endtask
    endclass
    
endpackage

`timescale 1ns/1ps
`include "uvm_macros.svh"
import uvm_pkg::*;
import fifo_test_pkg::*;

module tb_top;
    
    parameter DATA_WIDTH = 8;
    parameter ADDR_WIDTH = 4;
    parameter CLK_PERIOD = 10;
    
    logic clk;
    logic rst_n;
    
    // Clock generation
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end
    
    // Reset generation
    initial begin
        rst_n = 0;
        repeat(5) @(posedge clk);
        rst_n = 1;
    end
    
    // Interface instantiation
    fifo_if #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) vif (
        .clk(clk),
        .rst_n(rst_n)
    );
    
    // DUT instantiation
    sync_fifo #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH),
        .FWFT_MODE(0)
    ) dut (
        .clk         (clk),
        .rst_n       (rst_n),
        .wr_en       (vif.wr_en),
        .din         (vif.din),
        .rd_en       (vif.rd_en),
        .dout        (vif.dout),
        .full        (vif.full),
        .empty       (vif.empty),
        .almost_full (vif.almost_full),
        .almost_empty(vif.almost_empty),
        .overflow    (vif.overflow),
        .underflow   (vif.underflow),
        .wr_count    (vif.wr_count),
        .rd_count    (vif.rd_count)
    );
    
    // UVM test
    initial begin
        uvm_config_db #(virtual fifo_if)::set(null, "*", "vif", vif);
        run_test("fifo_test");
    end
    
    // Wave dumping
    initial begin
        $dumpfile("fifo_tb.vcd");
        $dumpvars(0, tb_top);
    end
    
    // Timeout
    initial begin
        #100000;
        $display("FATAL: Simulation timeout!");
        $finish;
    end
    
endmodule
