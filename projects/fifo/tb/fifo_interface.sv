interface intf(input CLK,input RST);
  logic WR_CS;
  logic WR_EN;
  logic RD_CS;
  logic RD_EN;
  logic [`DATA_WIDTH-1:0] DATA_IN;
  logic [`DATA_WIDTH-1:0] DATA_OUT;
  logic EMPTY;
  logic FULL;
  
  clocking drv_cb @(posedge CLK);
    default input #1 output #0;
    output WR_CS,WR_EN,RD_CS,RD_EN,DATA_IN;
    input DATA_OUT,EMPTY,FULL;
  endclocking 
   
  clocking mon_cb @(posedge CLK);
    default input #1 output #0;
    input WR_CS,WR_EN,RD_CS,RD_EN,DATA_IN;
    input DATA_OUT,EMPTY,FULL;
  endclocking
  
  modport drv_mp(clocking drv_cb,input CLK,input RST);
  modport mon_mp(clocking mon_cb,input CLK,input RST);
  
  
endinterface