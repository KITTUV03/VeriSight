--- Page 1 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page1of21
Design Specification
I2C Master Controller with APB4 Interface
1. Document Information
Field Detail
ProjectName I2CMasterControllerwithAPB4ConfigurationInterface,partoftheI2CMulti-Master/Slave
Controller
ProjectEngineer BhavaniShriS
Version v1.1
Date October4,2026
ReferenceSpecification NXP/PhilipsI2C-BusSpecificationandUserManual,UM10204
2. Overview
APB-controlledI²Cmulti-master/slavecontroller thatbridges aprocessor'sAPBinterfacetoanI²Cbus.The
designusesacommandFIFOandbyte-levelFSMtomanageI²Ctransactions,whilealower-levelbitFSM
handlesSDA/SCLtiming,ACK/NACK,arbitration,clockstretching andbus recovery.Synchronizers and
programmableglitchfilteringareusedforreliable samplingoftheexternal I²Clines,andanRXFIFObuffers
receiveddatabacktotheAPBside
ThedesignsupportsStandard(100kHz),Fast(400kHz) andFast-modePlus(1MHz) speedgrades,7-bit
and10-bitaddressing,master-sideclockstretching,arbitration-lossdetection,anda9-clock bus-recovery
sequenceforastuckSDAline.ThecurrentdesigndoesnotexposeavisibleDONEorBUSYregister.
SoftwarecanmonitortheTX/RXbyte counterstotrackdataprogressanduseIRQ_STATUStodetecterror
conditions.Theactual transaction-completionstateisinternal tothebyteFSM,sosoftwaredoesnothavea
dedicatedindication forsuccessfultransactioncompletion.

--- Page 2 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page2of21
2.1 Top-level architecture
Top-level block diagram of i2c_top with its submodules and the main signals between them.
Main signals between blocks.
From -> To Signals Meaning
APBmaster->register PADDR[4:0],PSEL,PENABLE,PWRITE,
PWDATA[7:0]
APB4transfer.Thedecode actsontheACCESS
phase(PSEL& PENABLE).
Register->Command
FIFO
cmd_word[11:0],cmd_fifo_w_en Commandword{PADDR[3:0],PWDATA}pushedfor
writestooffsets0x00-0x0A whentheFIFOisnotfull.
CommandFIFO->
i2c_byte_fsm
cmd_in[11:0],cmd_fifo_empty First-word-fall-throughheadoftheFIFO;validwhile
cmd_fifo_empty=0.
i2c_byte_fsm->
CommandFIFO
cmd_fifo_r_en Popstrobe.Atmostonecommandisconsumedper
PCLKcycle.
i2c_byte_fsm->RX FIFO rx_data[7:0],rx_fifo_w_en One-cyclewritepulseforeachreceivedbyte.
Register<->RXFIFO rx_fifo_r_en,rx_fifo_r_data[7:0] PoponanAPB readofoffset0x10;theheadbyteis
presentedcombinationally(0x00whenempty).
Register->i2c_byte_fsm irq_clear One-cyclepulseonawritetoIRQ_CLEAR(0x0B).
i2c_byte_fsm->Register irq_status_out[5:0],tx_count[15:0], Stickyerrorbits[5:0]andthebytecountersreadback

--- Page 3 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page3of21
From -> To Signals Meaning
rx_count[15:0] at0x11-0x15.
i2c_byte_fsm->i2c_bit trig[2:0],tx_data[7:0],mode[1:0],
stretch_timeout[23:0],
sda_stuck_timeout[23:0]
Commandtriggeranditsoperand,speedmodeand
thetwotimeouts.
i2c_bit->i2c_byte_fsm resp[2:0],rx_data[7:0] Commandstatus(INPROGRESS,thentheresult)and
thereceivedbyteorsampledACKbit.
i2c_bit<->i2c_counter en,clear,max_count->done Sharedtimingcounter;done=(count>=max_count).
Pins->sync_2ff->
i2c_glitch->bitFSM
scl_in,sda_in->scl_s,sda_s->scl_syn,
sda_syn
Inputconditioningofthetwoasynchronousbusinputs.
i2c_bit->open_drain scl_oe,sda_oe 1=drivethelinelow,0=releasetotheexternalpull-
up.
3. Interfaces
Top-levelmodule:i2c_top.Itinstantiates theAPB4 register/decodelogic,thecommandFIFOandRXFIFO,
thebyte-level sequencer,and,insidethat,the bit-levelengine,whichinstantiates sync_2ff,i2c_glitchand
i2c_counter.
Signal Name Direction Width Description
PCLK Input 1 APB4clock.(Singlefunctionalclockinthei2cblocks)
PRESETn Input 1 APB4active-lowreset
PADDR[4:0] Input 5 APB4registeraddress;selectstheregisterorcommandwordperSection5.
PSEL Input 1 Selectstheperipheral,APB4selectforthisslave.
PENABLE Input 1 APB4enable;APBaccessphase
PWRITE Input 1 1=write,0=read.
PWDATA[7:0] Input 8 APB4writedata.Datathatisbeingwritten
PRDATA[7:0] Output 8 APB4readdata.DatathatisreturnedduringanAPBread
PREADY Output 1 Peripheralready
PSLVERR Output 1 APB error
irq Output 1 Levelinterrupt:highwheneveranybitofIRQ_STATUS[7:0]isset
(combinationalOR ofthestickybits,nomaskregister).Clearedbywriting
IRQ_CLEAR.
scl Inout 1 Open-drainSCLpintotheexternalI2Cbus.Drivenlowbytheblockorreleased
totheexternalpull-up.
sda Inout 1 Open-drainSDApintotheexternalI2Cbus.Drivenlowbytheblockorreleased
totheexternalpull-up.
Everyportbelongs tothe singlePCLKdomainexceptsclandsda,whichareasynchronous,externally driven
buspins.
4. Clocking and Reset
Clocking.PCLKisthesinglefunctionalclockfortheentireblock.ItclockstheAPB4decodelogicini2c_top,
bothFIFOs,thebyte-levelFSM,thebit-levelengine,thetimingandtimeoutcounters,theinputsynchronizers
andtheglitchfilters.Thereisnoseparate,slower orgatedclock.
Reset.PRESETnisactivelowandassertedasynchronously: everystate anddataregisteriscaptured on
posedgePCLKor negedgePRESETn.De-assertionusesthesameasynchronoussensitivitylist,soaclean,
glitch-freePRESETnisexpectedfromoutsidetheblock.
Registers reset.Allcontrol,stateand dataregisters arereset:FIFOread/write pointersandthe
overflow/underflow flags,thestickyillegal-accessandcommand-FIFO-fullbits,thebyte-FSMstateand

--- Page 4 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page4of21
datapath,the configurationregisters,irq_r,tx_cnt/rx_cnt,thecommand-runner handshake,thebitengine
stateanddatapath,thetwosync_2ffpairs,thetwoi2c_glitchfilter/countregistersand thei2c_counter count
register.
Registers not reset.ThetwoFIFOstorage arrays (mem)arenotreset.Theircontentsarenever observable
whiletheFIFOisempty: i2c_fifoforces r_datato0x00wheneverthepointersareequal.
Clock-domain crossings.Thereareexactly two,bothsingle-bit,external-asynchronoustoPCLK:
• scl_in->2-flopsynchronizer (sync_2ff)->glitchfilter (i2c_glitch) ->stretch/timeoutlogic andthebit-level
FSM.
• sda_in->2-flopsynchronizer(sync_2ff)->glitchfilter(i2c_glitch)->arbitrationcomparisonandthe bit-
levelFSM.
Bothsynchronizers andbothfiltersresettologic 1,matchingthepulled-upidlebus,sotheconditionedbus
readsidleimmediately outofresetandnofalseSTARTor busyconditionisseen.
5. Register Map
AllregistersarebytewideandaddressedbyPADDR[4:0].Writesto0x00-0x0A arenotstoredinAPB-side
registers:i2c_topbuildsa12-bitcommandword{PADDR[3:0],PWDATA[7:0]}andpushesitintothe
commandFIFO.Configurationvalues thereforetakeeffectwhen thecommandis poppedbyi2c_byte_fsm,in
FIFOorder.Readsfrom0x10-0x15 returnlive status.
5.1 Register summary
Offset Register Name Width Access Reset Value Description
0x00 I2C_SLV_ADDRH 2 W 0x0(addrh=
2'b00)
Slaveaddressbits[9:8](10-bitaddressing).Command
header0x0.
0x01 I2C_SLV_ADDRL 8 W 0x00 Slaveaddresslowbyte: 7-bitaddressin[6:0],orbits[7:0]
ofa10-bitaddress.Header0x1.
0x02 MODE 3 W 0x0(Standard,7-
bit)
[2:1]speed,[0]10-bitaddressing.Header0x2.
0x03 SCL_TIMEOUT2 8 W 0x00 Clock-stretchtimeout[23:16].Header0x3.
0x04 SCL_TIMEOUT1 8 W 0x00 Clock-stretchtimeout[15:8].Header0x4.
0x05 SCL_TIMEOUT0 8 W 0x00 Clock-stretchtimeout[7:0].24-bitvalue0disablesthe
timeout.Header0x5.
0x06 SDA_TIMEOUT2 8 W 0x00 SDA-stuck/bus-busytimeout[23:16].Header 0x6.
0x07 SDA_TIMEOUT1 8 W 0x00 SDA-stuck/bus-busytimeout[15:8].Header0x7.
0x08 SDA_TIMEOUT0 8 W 0x00 SDA-stuck/bus-busytimeout[7:0].24-bitvalue0
disablesrecovery; abusybusthenfailstheSTART at
once.Header0x8.
0x09 TX_DATA 8 W n/a Queuesatransmitbyte.Header0x9 (CMD_TX).
0x0A RX_DATA 8 W n/a Queuesareceive-byterequest;PWDATAisignored.
Header0xA(CMD_RX).
0x0B IRQ_CLEAR - W n/a Anywritepulsesirq_clearforonePCLKcycle.Not
queued;takeseffectimmediately.
0x0C-
0x0F
RESERVED - - n/a Write:ignored,setsIRQ_STATUS[7].Read:0x00,sets
IRQ_STATUS[7].
0x10 RX_FIFO 8 R 0x00(FIFO
empty)
Popsandreturnsthenext receivedbyte;reads0x00
whentheFIFOisempty.
0x11 TX_COUNT_HIGH 8 R 0x00 tx_count[15:8].
0x12 TX_COUNT_LOW 8 R 0x00 tx_count[7:0].
0x13 RX_COUNT_HIGH 8 R 0x00 rx_count[15:8].
0x14 RX_COUNT_LOW 8 R 0x00 rx_count[7:0].

--- Page 5 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page5of21
Offset Register Name Width Access Reset Value Description
0x15 IRQ_STATUS 8 R 0x00 Stickystatusbits
Theconfigurationregisters arewrite-only: they cannotbereadback,andareadofany offsetoutside0x10-
0x15returns0x00.
5.2 Bit fields and reset values
Register Bits Field Access Reset Function
I2C_SLV_ADDRH [7:2] - W - Ignored.
[1:0] ADDR_HI W 2'b00 Addressbits[9:8].UsedonlywhenMODE[0]=
1;sentinthefirst10-bitaddressbyte{11110,
ADDR_HI,R/W}.
I2C_SLV_ADDRL [7:0] ADDR_LO W 0x00 7-bitmode:bits[6:0]aretheslaveaddressand
bit7isignored;theaddressbyteis
{ADDR_LO[6:0],R/W}.10-bitmode:sentasthe
secondaddressbyte.
MODE [7:3] - W - Ignored.
[2:1] SPEED W 2'b00 00Standard(100kHz),01Fast(400kHz),10
Fast-modePlus(1MHz),11Standard.
[0] ADDR10 W 1'b0 0=7-bitaddressing,1=10-bitaddressing.
SCL_TIMEOUT2/1/0 [7:0]
each
STRETCH_TO W 0x00
each
24-bitclock-stretchtimeoutinPCLKcycles,0=
disabled.MaximumtimeSCLmaystaylowafter
theenginereleasesit(includesthe2+
FILTER_LEN cycleinputlatency).
SDA_TIMEOUT2/1/0 [7:0]
each
SDA_STUCK_TO W 0x00
each
24-bittimeoutinPCLK cycles,0=disabled.
EvaluatedonlywhenaSTART findsthebusnot
free(Section6.7).
TX_DATA [7:0] TXD W - Bytetotransmit.NotstoredinanAPBregister.
RX_DATA [7:0] - W - Ignored;thewriteitselfistherequest.
IRQ_CLEAR [7:0] - W - Ignored;anywriteclearsallofIRQ_STATUS.
RX_FIFO [7:0] RXD R 0x00 Receivedbyte; 0x00whentheFIFOisempty.
TX_COUNT_HIGH/LOW [7:0]
each
tx_count R 0x0000 16-bitcountofdatabyteswhoseACKslothas
completed(ACKedorNACKed).Addressbytes
arenotcounted.Wrapsat0xFFFF; not
clearableexceptbyreset.
RX_COUNT_HIGH/LOW [7:0]
each
rx_count R 0x0000 16-bitcountofreceiveddatabytes.Wrapsat
0xFFFF;notclearableexceptbyreset.
IRQ_STATUS [0] NACK R 0 SlaveNACKedanaddressbyteoratransmitted
databyte.
[1] ARB_LOST R 0 Arbitrationlost.
[2] SDA_ERR R 0 SDAstilllowaftertherecoverysequence.
[3] SDA_REC R 0 SDAwasstucklowandtherecoverysequence
releasedit(informational).
[4] SCL_ERR R 0 SCLheldlowpaststretch_timeout,orSCL
stucklowatSTART.
[5] BUS_BUSY R 0 BusnotfreewhenaSTART wasrequestedand
recoveryisdisabled.
[6] CMD_FIFO_FULL R 0 Acommandwritewasdroppedbecausethe
commandFIFO wasfull.
[7] ILLEGAL R 0 IllegalAPB access.
AllIRQ_STATUSbitsaresticky. Aneweventwins over aclearpresentedinthesamecycle.

--- Page 6 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page6of21
5.3 Command word encoding
EveryAPB writeto0x00-0x0A becomesone12-bitcommandwordinthecommandFIFO.Theheader isthe
lowfourbitsoftheAPBaddress,sotheregisteroffsetandthecommandheader arethesamenumber.
12-bit command word format.
Bits Field Meaning
[11:8] HDR Commandheader=PADDR[3:0].Selectstheaction(Table3).
[7:0] DATA Commandoperand=PWDATA[7:0].MeaningdependsonHDR.
Command header values.
HDR Mnemonic APB
offset
DATA bits used Action when i2c_byte_fsm pops the word
0x0 CMD_ADDRH 0x00 [1:0] addrh<=DATA[1:0].
0x1 CMD_ADDRL 0x01 [7:0] addrl<= DATA.
0x2 CMD_MODE 0x02 [2:0] mode_reg<= DATA[2:0](speedandaddresssize).
0x3 CMD_SCL_TIMEOUT_2 0x03 [7:0] stretch_timeout[23:16]<= DATA.
0x4 CMD_SCL_TIMEOUT_1 0x04 [7:0] stretch_timeout[15:8]<=DATA.
0x5 CMD_SCL_TIMEOUT_0 0x05 [7:0] stretch_timeout[7:0]<=DATA.
0x6 CMD_SDA_TIMEOUT_2 0x06 [7:0] sda_stuck_timeout[23:16]<=DATA.
0x7 CMD_SDA_TIMEOUT_1 0x07 [7:0] sda_stuck_timeout[15:8]<= DATA.
0x8 CMD_SDA_TIMEOUT_0 0x08 [7:0] sda_stuck_timeout[7:0]<=DATA.
0x9 CMD_TX 0x09 [7:0] TransmitDATA.Atthestartofatransaction italsotriggers
START andtheaddressphase;mid-transactionitsends
thenext byte(orforcesarepeatedSTART iftheprevious
bytewasaread).
0xA CMD_RX 0x0A none Receiveonebyte. Atthestartofatransactionittriggers
START andtheaddressphase;consecutiveCMD_RX
wordsformareadburst.
Headers0xB-0xEarenevergenerated:offset0x0B(IRQ_CLEAR)ishandledoutsidetheFIFOandwrites
above0x0Barerejected.Header0xF(CMD_IGNORE) isreserved;i2c_byte_fsmdropsitifitis everpresent,
butnoAPB accessproducesit.
Configurationwords(0x0-0x8)areconsumedonlywhile i2c_byte_fsmisinM_IDLE.Aconfigurationwordthat
reaches theheadoftheFIFOinthemiddleofaburstthereforeendsthetransactionwith aSTOPandis
appliedafterwards,soaconfigurationwritecanalsobeusedtoseparatetwotransactions.
5.4 Access rules
Access Offsets Effect Sets IRQ_STATUS[7]
Write 0x00-0x0A CommandwordpushedintothecommandFIFO.Ifthe
FIFOisfullthewordisdroppedandIRQ_STATUS[6]is
set.
No
Write 0x0B irq_clearpulse,immediate(notqueued). No
Write 0x0C-0x1F Ignored. Yes
Read 0x10-0x15 ReturnsthevalueinSection5.1.Areadof0x10pops
theRXFIFO.
No
Read 0x00-0x0F,0x16-0x1F Returns0x00. Yes
PREADYisalways 1andPSLVERR isalways 0,soillegalaccessescomplete normally andarevisibleonly
throughIRQ_STATUS[7].

--- Page 7 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page7of21
6. Functional Description
6.1 Micro-architecture
6.1.1 i2c_top (APB4 register / decode logic)
i2c_topcontainsnosequencing.Itqualifies eachAPB transfer(apb_access=PSEL&PENABLE;PREADYis
tiedhigh,sothisisexactly theone-cycleACCESSphase),decodestheoffset,formsthe commandword,
drivesthecommandFIFOwritestrobe,generates theirq_clear pulse,andholds twostickystatus flops
(command-FIFO-fullandillegal-access)thatfollowthesamepolicyasthestickybits ini2c_byte_fsm.The
readmuxselects PRDATAcombinationally fromPADDR.irqistheORoftheeightstatus bits.Theopen-drain
logicisimplemented here(scl=scl_oe?1'b0:1'bz),similarly forsda;scl_inandsda_inreadthepin,
includingtheblock'sowndrive.
6.1.2 i2c_fifo (command FIFO and RX FIFO)
Asingle-clockFIFOwithparametersWIDTHandDEPTH(power oftwo,atleast2).Thereadandwrite
pointerscarryoneextrabit,sofullis count[ADDR_WIDTH]andemptyispointerequality. TheFIFOis first-
word-fall-through:r_data istheheadentry, forcedto0x00whenempty. Awriteisacceptedonw_en & full
and a read on r_en & empty; awritewhenfullorareadwhenemptyisignored. overflowandunderfloware
registeredone-cycleflagsthat arenotconnectedati2c_top,soanRXFIFOoverflowisnotreported.The
commandFIFOis12bits wide,theRX FIFO8bits.
6.1.3 i2c_byte_fsm
i2c_byte_fsmturnsthecommandstreamintobustransactions.Ithas fourparts:
• Configuration registers:addrh,addrl,mode_reg,stretch_timeoutandsda_stuck_timeout.They are
loadedonlywhen aconfigurationwordispopped inM_IDLEandfeedi2c_bitdirectly(mode_reg[2:1] is
thespeedmode).
• Command runner:issues onei2c_bitcommandatatime.TheMainFSMpulsesgowith atrigger code
andoperand;therunnerregisterstrigandtx_dataand setsbusy, holdstriguntili2c_bitshows resp=
INPROGRESS(commandaccepted),releases trigtoIDLE,thenwaitsforresptochange,andfinally
pulsesdonewith theresultlatched inres(status) andres_rx(rx_dataofi2c_bit).resandres_rxremain
validuntilthenextcommandcompletes.
• Main FSM(M_IDLE ...M_FLUSH):popscommands,buildsaddressbytes,decidesACK orNACK for
eachreceivedbyte,chooses betweencontinue,repeatedSTARTandSTOP,and handles errors.A
one-bitflag(iss)ensureseachstateissuesits i2c_bitcommandexactly once.
• Status:thestickyirq_r[5:0]register,updated asirq_r <=(irq_r &~irq_clear)|irq_set,andthe16-bit
tx_cntandrx_cntcounters.rx_fifo_w_enisaregisteredone-cyclepulseandrx_datais thebyteitwrites.
6.1.4 i2c_bit
i2c_bitexecutesone bus-levelcommand(STARTor repeatedSTART,TXbyte,RXbyte,STOP)atatime,
generates theSCL/SDAtiminganddetectsbuserrors.
• Input conditioning:scl_inandsda_inpassthroughsync_2ffandi2c_glitch,givingscl_syn and
sda_syn.bus_free=scl_syn &sda_syn.
• Timing table:thenanosecondconstants fortheselectedspeedmodeareconvertedtoPCLKcycles
androundedup,sonointervalisshorter thanthespecifiedminimum.
• Timing counter:onesharedi2c_counter.Itiscleared oneverystatechange,andmax_countischosen
perstateas(interval -1),soeachstatelastsexactly theintervalincycles.Inthefourstatesthat waitfor
SCLtorise(S_ST_SCLH,S_BIT_HIGH,S_SP_SCLH,S_REC_HIGH)thecounteradvances,anddone
isqualified,onlywhilescl_syn =1.TheintervalisthereforemeasuredfromthemomentSCLis
observedhigh.
• Timeout counters:stretch_cntcounts consecutivecyclesspent inawait-for-SCL-highstatewith
scl_syn =0andraises stretch_towhenitreaches stretch_timeout(0disables).sda_stuck_cntcounts
cycles inS_CHKwhile thebus isnotfreeandraises sda_stuck_towhenitreaches sda_stuck_timeout.

--- Page 8 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page8of21
• FSM and datapath(S_IDLE ...S_ABORT):tx_buf andrx_bufshiftregisters,bit_idx,ack_phase,op_rx,
ack_lat(theACK/NACKbittosendafteranRXbyte),bus_owned(aSTART hasbeenissuedandno
STOPyet),rec_modeandrec_cnt(busrecovery) anderr_code(resultreportedfromS_ABORT).
• Line drive:scl_oeandsda_oeareregisterscomputedfromthecurrentstate,soeachlinechange
appearsonePCLKcycleafterthestateisentered.Theenginenever drivesalinehigh.
6.1.5 sync_2ff, i2c_glitch and i2c_counter
• sync_2ff:twoflopsinseries withasynchronousresettoRESET_VAL(1).Outputis thesecondflop.
• i2c_glitch:holds afiltered valuefiltandcountsconsecutive samplesthatdisagreewithit;filtchanges
onlyafterFILTER_LENconsecutivedisagreeing samples,soshorterpulsesarerejected.Withen=0
themoduleis acombinationalpass-through(dout=din).
• i2c_counter:countincrements whileenis high anddoneis low,clearsonclear,anddone=(count>=
max_count).Thecountoutputisnotusedbyi2c_bit.
6.1.6 How the submodules interact
Thefollowingsequencedescribes awriteoftwobytes toa7-bitslave(softwarewritesI2C_SLV_ADDRL,
TX_DATA,TX_DATA):
1. ThethreeAPB writesaredecodedini2c_topandpushedintothecommandFIFOasthree12-bitwords.
2. i2c_byte_fsm(M_IDLE) popstheADDRLwordandappliesit,then popsthefirstTXword,storesits
dataandmoves toM_START.
3. M_STARTpulses gowithTRIG_START.Thecommandrunner presentsthe triggertoi2c_bit,which
performstheSTARTandreports resp=IDLE;therunnerpulsesdone.
4. M_ADDR1issuesTRIG_TXwith {ADDRL[6:0],0}.i2c_bitshiftsthebyteout MSBfirst,readstheslave's
ACKbitandreturns itinrx_data[0].AnACK leadstoM_DATA.
5. M_DATAissuesTRIG_TXforthefirstdatabyte;onACK tx_countincrementsand M_NEXTexamines
theFIFOhead.ThesecondTXwordis poppedandM_DATAsends it.
6. AfterthesecondbyteM_NEXT findsnodatacommandattheFIFOhead,soM_STOPissues
TRIG_STOP;when i2c_bitreportsresp= IDLEthebyteFSM returnstoM_IDLE.
Aread is thesameexceptthatM_DATAissues TRIG_RXwith the ACK/NACKbitchosenfromthe FIFO head,
andthebyte returnedinrx_dataispushedintotheRXFIFOand counted inrx_count.Errorsfromi2c_bit
returnasanon-zerorespandarehandledinM_ERR.
6.2 APB4 register access
i2c_topisastandardtwo-phaseAPB4slave:aSETUPcycle(PSELhigh,PENABLElow) followedby an
ACCESScycle(PSELand PENABLEhigh).PREADYistiedhighand PSLVERRtiedlow, soeveryaccess
takesexactly oneACCESScycle.
• Write to 0x00-0x0A:thecommandwordispushedintothecommandFIFOattheendoftheACCESS
cycleifthe FIFOisnotfull.IfitisfullthewordisdroppedandIRQ_STATUS[6]is set.
• Write to 0x0B:irq_clearis pulsedforonecycleregardlessofPWDATA.
• Write to 0x0C-0x1F:noregistereffect;IRQ_STATUS[7]is set.
• Read of 0x10:returns theRXFIFOheadandpopsitattheendoftheACCESScycle.Areadwhile
emptyreturns0x00andchanges nothing.
• Read of 0x11-0x15:returns thecorrespondinglivestatus byte.
• Read of any other offset:returns0x00andsets IRQ_STATUS[7].
6.3 Transaction model
ThereisnoexplicitSTART orSTOPcommand.Arunofconsecutive CMD_TX/CMD_RXwordsinthe
commandFIFOformsonebus transaction.Thefirstdatacommandthatreaches theheadoftheFIFOwhile
theengineisidlecausesaSTARTand anaddressphase.Whilethedirectionstays thesame(TXafterTX,or
RXafterRX)bytesaresentbacktoback.Achangeofdirection(TXfollowedby RXor RXfollowedby TX)
producesarepeatedSTART andanewaddressphase. Aftereachdata byte,i2c_byte_fsmlooksattheFIFO

--- Page 9 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page9of21
head:ifitis notadatacommand,becausetheFIFO isemptyorthenextwordisaconfiguration word,a
STOPisgenerated andtheenginereturns toidle.
Thedecisionis takenonceperbyte,inthecycleafterthebyte completes.Commandsthatarealready inthe
FIFOatthatmomentbelongtothecurrenttransaction;commandswrittenlater startanewone.
6.4 START, addressing and repeated START
Onthefirstdata commandofatransactiontheengineissues aSTART(or,mid-transaction, arepeated
START),thentransmitstheaddressbyte(s):
• 7-bit addressing (MODE[0]=0):one addressbyte,{addrl[6:0],R/W}.
• 10-bit write:twobytes,{11110,addrh[1:0],0}then addrl[7:0].
• 10-bit read that starts a transaction:the write-formsequence{11110,addrh[1:0],0},addrl[7:0]issent
first;theengine thenissuesarepeatedSTARTandsends {11110,addrh[1:0],1},afterwhichdatais
received.This isthe10-bitreadprotocol ofUM10204.
• 10-bit read reached by a direction change from a write:the repeatedSTARTisfollowedbyonlythe
firstbyte,{11110,addrh[1:0],1}.
• Direction change from a 10-bit read to a write:the repeatedSTARTis followedby{11110,addrh[1:0],
0}andaddrl[7:0].
ANACK onanaddressbytesetsIRQ_STATUS[0],stops thetransactionwith aSTOPand discardsthe
remainingqueueddatacommands.START,repeatedSTARTand STOPwaveformsareinFigures4to6.
6.5 Data phase and ACK/NACK handling
TX byte.Theenginedrivesthe byteMSB first,thenreleasesSDA andsamplestheslave's ACKbit.ANACK
setsIRQ_STATUS[0]andendsthetransactionwithaSTOP.Thebyteisstill counted intx_count.
RX byte.Theengine releases SDA,receives eightbitsMSB first,thendrivesthe ACK/NACKbititself.Thebit
ischosenwhenthecommandis issuedtoi2c_bit:ACK (0)ifthecommandatthe FIFOheadatthatmomentis
alsoaCMD_RX,otherwiseNACK (1).Areadburstmustthereforebequeuedatleastone commandaheadof
thebyte inflight.IfaCMD_RXarrivesaftertheprecedingbytewasalreadyNACKed,theprecedingbyteis
correctlyNACKedandthenewbyteisfetchedwitharepeatedSTARTandanewaddressphase.
6.6 Transaction continuation
Aftereachcompleteddata byte(stateM_NEXT)theenginecheckstheFIFOhead:aTXinthe writedirection
oranRXinthereaddirection(andthepreviousbytewasnotNACKed)continuestheburst;adatacommand
oftheopposite directioncausesarepeatedSTARTandafreshaddressphase;anythingelsecausesaSTOP
andareturntoidle.
6.7 Error handling
EacherrorisreportedasastickybitinIRQ_STATUSandendsthe currenttransaction.Ineveryerror case,
TX/RXcommandsstillqueued forthefailedtransactionarepoppedanddiscarded oncethetransactionhas
ended(M_FLUSH),soafollowingconfiguration wordor thenexttransaction'sfirstdatacommandisnot
mistakenforacontinuation.
Error conditions, reporting and byte-FSM action.
Condition Result code IRQ bit Detected / handled STOP issued by
i2c_byte_fsm
SlaveNACKonan
addressbyteoronaTX
databyte
(ACKbit=1) [0] ByteFSMreadsthesampledACKbit;
goestoM_STOP,thenM_FLUSH.
Yes
Arbitrationlost ARB_LOST [1] i2c_bit:atransmitted1(addressordata
bit,nottheACKbit)readsback0,orSDA
islowwhenarepeatedSTART needsit
high.Linesarereleasedandi2c_bit
returnstoIDLE.
No
SDAstuck, SDA_ERR [2] SDAstilllowafterthe9-clockrecovery No(recoveryalready

--- Page 10 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page10of21
Condition Result code IRQ bit Detected / handled STOP issued by
i2c_byte_fsm
unrecoverable anditsSTOP. endedwithaSTOP)
SDAstuck,recovered SDA_RECOVERY [3] RecoveryreleasedSDA.TheSTART is
retriedonce.Iftheretryhits
SDA_RECOVERYagainthetransaction
isabandonedandonlybit[3]isset.
No
SCLheldlowtoolong SCL_ERR [4] SCLlowlongerthanstretch_timeoutafter
theenginereleasedit,orSCLlowat
START aftersda_stuck_timeoutexpired.
Linesreleased.
No
BusnotfreeatSTART BUS_BUSY [5] SDAorSCLlowatSTART with
sda_stuck_timeout=0,orSDA lowatthe
endoftheSTART setuptimewhenno
START waspreviouslyissued.Lines
released.
No
START on a busy bus.Ifthebusis notfreewhen aSTARTis requested:withsda_stuck_timeout=0the
STARTfailsatoncewithBUS_BUSY.Withanon-zerotimeouttheenginewaits;ifthebus becomesfreethe
STARTproceeds.IfSDAstays lowwithSCL highforthetimeout,theengine runs9SCL pulses withSDA
released,thenaSTOP(busrecovery);SDAhighafterwards gives SDA_RECOVERYandlowgives
SDA_ERR.IfSCL isthelineheldlow whenthetimeoutexpires,theresultisSCL_ERR.
6.8 Bit-level timing generation
i2c_bitderivesall intervalsfromafixedtableofUM10204 minimumtimes,convertedtoPCLKcycles with
NS2C(ns)=ceil(CLK_FREQ_MHZ xns/1000),sonointervalisshorter thanthespecificationminimum.
Timing constants (ns) and PCLK cycles at 100 MHz (Standard / Fast / Fast-mode Plus).
Interval Standard (ns) Fast (ns) Fast+ (ns) Cycles at 100 MHz
(Std / Fast / Fast+)
tSU;STA(STARTsetup) 4700 600 260 470/60/26
tHD;STA(STARThold) 4000 600 260 400/60/26
tLOW 6000 1500 600 600/150/60
tHIGH 4000 1000 400 400/100/40
tSU;STO(STOPsetup) 4000 600 260 400/60/26
tBUF(busfree) 4700 1300 500 470/130/50
Recoveryhalf-cycle 5000 1250 500 500/125/50
T_HD_DAT(SDA holdafter
SCLfalls)
300 300 300 30
SCL high timeis countedfromthemomentSCL isobservedhigh afterthesynchronizer andfilter,sotHIGH
isnever shorterthanthe target.This alsoprovides clock-stretchhandlingandwired-ANDclock
synchronizationwithothermasters.TheresultingSCLfrequencyis slightly belownominalandnever above it
(about99kHz,391kHzand943kHzat100 MHz);theshortfallisafixednumber ofPCLKcycles of
synchronizerandfilter latency,soitgrowsatslower clocks(about806kHzinFast-modePlusat25MHz).
SDA data hold.After SCLispulledlowtheengine keepsSDA unchangedforT_HD_DAT =300ns (rounded
uptowholecycles) beforemovingSDAtothenextbitvalue.Theholdiscarvedout oftLOW,sothe SCLlow
timeis unchanged(Figure8).
Per-state intervals.S_ST_REL:onecycleforaninitialSTART,tLOWforarepeatedSTART.S_ST_SCLH:
tSU;STAfromobservedSCLhigh.S_ST_SDAL:tHD;STA.S_HOLD:atleastT_HD_DAT beforeaSTARTor
STOP,none beforeTX/RX.S_BIT_SET:T_HD_DAT.S_BIT_LOW:tLOW-T_HD_DAT.S_BIT_HIGH:tHIGH
fromobservedhigh. S_SP_SDAL:tLOW.S_SP_SCLH:tSU;STOfromobservedhigh.S_SP_SDAH: tBUF.
Eachrecoverystate:one half-cycle.Everystatelastsatleastone cycle.

--- Page 11 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page11of21
Clock requirement.CLK_FREQ_MHZ mustmatchtherealclock.Aclockof20MHzor moreis
recommendedand 10MHzistheabsolute minimumforFast-modePlus,becausethelowphasemustbe
longer thanthesynchronizer andfilterlatency.
6.9 Input conditioning
scl_inandsda_ineachpassthrougha2-flopsynchronizerand adigitalglitchfilter.Thefilter outputchanges
onlyaftertheinputhasdisagreedwith itforFILTER_LENconsecutive PCLK cycles,sopulsesshorter than
FILTER_LENcycles arerejected.Achangeonthepinappearsonscl_syn /sda_syn afterabout2+
FILTER_LENPCLKcycles (plus uptoonecycle ofsamplingalignment).Thefiltercanbebypassedperlineat
elaborationtime(GLITCH_FILTER_EN=0);itisnotintendedtobeswitchedwhilethebusis active.
6.10 Transfer completion and status polling
Theblockhas no done, busy or FIFO-level register and no completion interrupt.irqreportsonlythe
eventsin IRQ_STATUS:sixbusevents (fiveerrorsandtheinformationalSDA-recoveredbit),command-FIFO
overflowandillegal access.Softwaredetermines progressandcompletionas follows.
What software can observe.
Question Where to look How it behaves
HasaTXdatabytefinished? TX_COUNT (0x11/0x12) Incrementsby1whenthebyte'sACKslothascompleted,
whethertheslaveACKedorNACKed.Addressbytes and
configurationwritesarenot counted.
HasanRXbytearrived? RX_COUNT(0x13/0x14),
thenRX_FIFO (0x10)
rx_countincrementsinthesamecycletheRXFIFOwrite
pulseisgenerated;thebyteisintheFIFOonecyclelater.
Back-to-backAPBaccessesareatleasttwocyclesapart,so
areadofRX_FIFO thatfollowsareadofRX_COUNTalways
seesthebyte.
Didsomethingfail? irq,IRQ_STATUS (0x15) Stickyerrorbits.ANACK isreportedbeforetheSTOPhas
beensent.
HastheSTOPcompletedand
thebusgonefree?
Notobservableinregisters Waitaboundedtimeafterthelastcountupdate(seebelow),
orwatchthebus.
HasthecommandFIFO
drained?
Notobservableinregisters Impliedbythecountersreachingtheexpectedvalues.
Expected software sequence for a write of N bytes:
1. Optionallyclear IRQ_STATUS(write0x0B), thenreadTX_COUNTtogetthestarting value c0.
2. Queuetheconfigurationwords (ifany) andNCMD_TXwords.Queuethewholetransactionpromptly:if
theFIFOrunsemptybetweenbytes,aSTOPis issued(Section 6.3).
3. PolluntilTX_COUNT-c0(modulo 65536)equals N,or irq/IRQ_STATUSshowsanerror,with a
softwaretimeoutincaseneither happens(forexample, anendless clockstretchwithstretch_timeout=
0).
4. Ifthebus mustbeknown freebeforethe nextaction,waitfortheSTOPtimebelow.
For a read of N bytes,queueNCMD_RXwords,poll RX_COUNTinthesameway, thenreadRX_FIFON
times.Becausethe RXFIFOreturns 0x00whenempty, useRX_COUNT,not thevalueread,toknowthat
dataispresent.
Error cases.AnaddressNACKsetsIRQ_STATUS[0]andtx_count doesnotadvance.Adata NACKsets
IRQ_STATUS[0]andtx_countdoesadvanceforthatbyte,sosoftwaremustcheckIRQ_STATUSaswellas
thecount.ForARB_LOST,SDA_ERR,SCL_ERRandBUS_BUSYthecountersstopwherethey were.After
anyerrorthecommandsalreadyqueued forthetransactionarediscarded withoutbeingcounted.
STOP time.Fromthelastbyte'scountupdate,theSTOPtakesaboutT_HD_DAT +tLOW+tSU;STO+tBUF
plusafewPCLKcycles ofhandshakeand synchronizer/filterlatency: about15us inStandardmode,3.7usin
Fastmodeand1.7usinFast-modePlus.

--- Page 12 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page12of21
Separating transactions.ToforceaSTOPbetweentwotransactions,either waitforthefirsttransaction's
countbeforequeuingthesecond,orplaceaconfiguration word(forexample arewriteofI2C_SLV_ADDRL)
betweenthem.
6.11 Interrupt behaviour and latency
irqis thecombinationalORoftheeightstickyIRQ_STATUSflops(noextraregisterstage,nomask).Itis a
leveloutput:itstays highuntil thestatus bits arecleared byawritetoIRQ_CLEAR.Bit[3](SDArecovered) is
informationalandalsoraises irq.
LatencyisgiveninPCLK cyclesfromthe event cycle,thecyclein whichtheconditionis firstevaluatedtrue
bythelogic namedinthe table,tothecycleinwhichirqis firstseenhigh.Avalue of1meansirqishighinthe
cycleimmediatelyafterthe eventcycle.Thefiguresassumethe logicitselfis notdelayed;events that
originateonthebus addtheinputconditioninglatency(2+FILTER_LENcycles),and SCL_ERRand
BUS_BUSYadd theprogrammedtimeout.
irq assertion and de-assertion latency.
Source Bit Event cycle Cycles to irq Path
SlaveNACK [0] i2c_bitsamplestheACK bitattheendoftheACK-bit
SCLhightime.
3 bitengine->
runner->
byteFSM->
irq_r
Arbitrationlost [1] i2c_bitdetectsthemismatch(orSDAlowatarepeated
START).
5 S_ABORT->
resp->
runner->
M_ERR->
irq_r
SDAerror [2] EndoftherecoverySTOP bus-freetimewithSDA still
low.
4 resp->
runner->
M_ERR->
irq_r
SDArecovered [3] EndoftherecoverySTOP bus-freetimewithSDA high. 3 resp->
runner->
byteFSM->
irq_r
SCLerror [4] stretch_cntreachesstretch_timeout(orSCLlowat
START aftersda_stuck_timeout).
5 S_ABORT->
resp->
runner->
M_ERR->
irq_r
Busbusy [5] START findsthebusnot freewithsda_stuck_timeout=
0(orSDA lowattheendofSTART setup).
5 S_ABORT->
resp->
runner->
M_ERR->
irq_r
CommandFIFOfull [6] ACCESScycleofthewritethatfindstheFIFOfull. 1 decode->
stickyflop
Illegalaccess [7] ACCESScycleoftheillegalreadorwrite. 1 decode->
stickyflop
De-assertion
(IRQ_CLEAR write)
all ACCESScycleofthewriteto0x0B. 1(irqlow) decode->
clearsall
stickyflops
De-assertion.Theirq_clear pulseisgenerated combinationallyintheACCESScycleandclearseverysticky
bitattheedgethatendsit,soirqislow inthefirstcycleaftertheIRQ_CLEARwrite completes.Areadof
IRQ_STATUSimmediately afterwardsreturns 0x00unless aneweventhas occurred.Aneweventinthe
samecycleastheclear winsand keepsits bitset.
Ordering.IRQ_CLEARis notqueuedbehindpendingcommands.ANACKis reportedbeforetheSTOPthat
followsithas beensent,soirqcanrisewhilethebus isstill active.

--- Page 13 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page13of21
6.12 Bus and register timing diagrams
TheAPBdiagramsarecycleaccurate.Thebusdiagramsarenottoscale:intervallengths dependonthe
speedmode (Section 6.8),and eachscl_oe or sda_oe edgeappears onePCLK cycleafter itsstateis entered.
SCLandSDA areshown asthe resultingwired-AND linelevels;risetimesarenotdrawn.
APB4 write of 0xA5 to TX_DATA (0x09).
APB4 read of RX_FIFO (0x10).
START on an idle bus.
Repeated START from S_HOLD, shown after a byte the master ACKed. SDA is released while SCL is low, SCL is
released, then SDA falls while SCL is high.

--- Page 14 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page14of21
STOP signal genertion
One-byte write transfer with ACK: START, address byte 0xA5, slave ACK(slave_sda_oe) on the ninth clock.
7. FSM / State Transitions
7.1 Byte-level FSM (i2c_byte_fsm)
State transition diagram of i2c_byte_fsm.
Current state Condition Next state What happens
M_IDLE CMD_TX/CMD_RX M_START Starttransaction
M_IDLE Configurationcommand M_IDLE Updateconfiguration
M_START done&RESP_IDLE M_ADDR1 START successful
M_START SDA recovery+firstretry M_START Retry START

--- Page 15 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page15of21
Current state Condition Next state What happens
M_START SDArecovery+alreadyretried M_ERR Error
M_START Othererror M_ERR Error
M_ADDR1 biterror M_ERR Error
M_ADDR1 addressNACK M_STOP SetNACK +stop
M_ADDR1 addressaccepted,nosecondbyte M_DATA Dataphase
M_ADDR1 10-bitsecondbyterequired M_ADDR2 Sendsecondaddressbyte
M_ADDR2 biterror M_ERR Error
M_ADDR2 NACK M_STOP SetNACK +stop
M_ADDR2 10-bitwrite M_DATA Dataphase
M_ADDR2 10-bitread M_START RepeatedSTART
M_DATA biterror M_ERR Error
M_DATA successfulREAD M_NEXT PushRXdata
M_DATA successfulWRITE+ACK M_NEXT IncrementTXcount
M_DATA WRITE+NACK M_STOP SetNACK +stop
M_NEXT nextTXsamedirection M_DATA Nextdata byte
M_NEXT nextRXsamedirection M_DATA Nextdata byte
M_NEXT directionchanges M_START RepeatedSTART
M_NEXT nodatacommand M_STOP End transaction
M_STOP STOPerror M_ERR Error
M_STOP success+err_flag=0 M_IDLE Transactioncomplete
M_STOP success+err_flag=1 M_FLUSH Clearqueueddata
M_ERR anyhandlederror M_FLUSH SetIRQ+flush
M_FLUSH datacommandremains M_FLUSH Popcommand
M_FLUSH nodatacommand M_IDLE Returnidle

--- Page 16 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page16of21
7.2 Bit-level engine FSM (i2c_bit)
State transition diagram of i2c_bit.
Current state Condition Next state What happens
S_IDLE trig==TRIG_START S_CHK STARTcommandisaccepted.respbecomesRESP_INPROGRESS;bus-freecheckbegins.
S_IDLE trig==TRIG_TXorTRIG_RX S_ABORT TX/RXisnotallowedbeforeSTART.err_code=RESP_BUS_BUSY.
S_IDLE trig==TRIG_STOP S_ABORT STOPwhilealreadyidleistreatedasano-op.err_code=RESP_IDLE.
S_IDLE Novalidtrigger S_IDLE Waitsforacommand.
S_CHK bus_free== 1 S_ST_REL Bus isfree;continueSTARTgeneration.
S_CHK Bus notfree+sda_stuck_timeout== 0 S_ABORT Immediatelyreports RESP_BUS_BUSY.
S_CHK SDAstucktimeoutreached+scl_syn ==1 S_REC_LOW SDAisstucklowwhile SCLishigh;starts9-clockbusrecovery.
S_CHK SDAstucktimeoutreached+scl_syn ==0 S_ABORT SCLisalso heldlow; reportsRESP_SCL_ERR.

--- Page 17 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page17of21
Current state Condition Next state What happens
S_CHK Busnotfreeandtimeoutnotyetreached S_CHK Continueswaiting/checkingthebus.
S_ST_REL done_ok S_ST_SCLH ReleasesSDA andwaitsforthe STARTsetupphase.
S_ST_REL done_ok== 0 S_ST_REL Continues waitingfortherequired timing.
S_ST_SCLH stretch_to S_ABORT SCLremains lowtoolong;reportsRESP_SCL_ERR.
S_ST_SCLH done_ok+sda_syn== 1 S_ST_SDAL SCLishighandSDAis high;readytogenerateSTART.
S_ST_SCLH done_ok+sda_syn == 0+bus_owned==1 S_ABORT AnothermasterpulledSDA low;reportsRESP_ARB_LOST.
S_ST_SCLH done_ok+sda_syn == 0+bus_owned==0 S_ABORT Bus isstillbusy; reportsRESP_BUS_BUSY.
S_ST_SCLH Noneofabove S_ST_SCLH Continues waitingforSCLhigh/timingcompletion.
S_ST_SDAL done_ok S_ST_SCLL Pulls SDAlowwhileSCL ishigh,creatingtheSTART condition.
S_ST_SDAL done_ok== 0 S_ST_SDAL ContinuesSTARTholdtiming.
S_ST_SCLL Always S_HOLD Pulls SCLlow,marksbus_owned=1,setsresp=RESP_IDLE;STARTiscomplete.
S_HOLD trig==TRIG_START +done_ok S_ST_REL GeneratesarepeatedSTARTwhilethebus isalready owned.
S_HOLD trig==TRIG_TX S_BIT_SET Latchestx_data,setsTXmode,initializesbit_idx=7;starts bytetransmission.
S_HOLD trig== TRIG_RX S_BIT_SET
ClearsRXbuffer,setsRXmode,latches
ACK/NACKvalue,initializes bit_idx=7;starts
bytereception.
S_HOLD trig==TRIG_STOP+done_ok S_SP_SDAL Begins STOPsequence.
S_HOLD Novalidtrigger S_HOLD Keepsthebusownedandwaitsforthenextcommand.
S_BIT_SET done_ok S_BIT_LOW MaintainsSDA forT_HD_DAT beforechangingtheSDA bit.
S_BIT_SET done_ok== 0 S_BIT_SET Continues SDAholdtiming.
S_BIT_LOW done_ok S_BIT_HIGH Drives therequired SDAvalueandcompletes theSCL-lowperiod.
S_BIT_LOW done_ok== 0 S_BIT_LOW ContinuesSCL-lowtiming.
S_BIT_HIGH stretch_to S_ABORT SCLis heldlowtoolongby thebus;reportsRESP_SCL_ERR.

--- Page 18 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page18of21
Current state Condition Next state What happens
S_BIT_HIGH done_ok+TX+sent1butsda_syn ==0 S_ABORT Arbitrationislostbecauseanother masterforcedSDAlow. ReportsRESP_ARB_LOST.
S_BIT_HIGH done_ok+normaldatabit+bit_idx!=0 S_BIT_SET Samples/handlesthecurrentbit,decrementsbit_idx,andpreparesthenextbit.
S_BIT_HIGH done_ok+lastdatabit(bit_idx== 0) S_BIT_SET Completes8databitsandsetsack_phase=1togeneratethe9thACK bit.
S_BIT_HIGH done_ok+ack_phase==1 S_HOLD ACK/NACK bitis complete.Storesrx_data, setsresp=RESP_IDLE,andwaits forthenextcommand.
S_SP_SDAL done_ok S_SP_SCLH HoldsSDA lowwhileSCL islow,preparing forSTOP.
S_SP_SCLH stretch_to S_ABORT SCLremains lowtoolong;reportsRESP_SCL_ERR.
S_SP_SCLH done_ok S_SP_SDAH Releases SCLandwaitsforittobecomehigh.
S_SP_SDAH done_ok S_IDLE
ReleasesSDA whileSCL ishigh,creatingSTOP.
Clearsbus_owned;normalcompletiongives
RESP_IDLE.
S_REC_LOW done_ok S_REC_HIGH DrivesSCLlow fortherecoveryclock'slowhalf-cycle.
S_REC_HIGH stretch_to S_ABORT SCLis heldlowtoolongduringrecovery; reportsRESP_SCL_ERR.
S_REC_HIGH done_ok+rec_cnt==8 S_REC_END Ninthrecoveryclockiscomplete.
S_REC_HIGH done_ok+rec_cnt!=8 S_REC_LOW Incrementsrecovery counterand generatesanother recoveryclock.
S_REC_END done_ok S_SP_SDAL Recoveryclocksarefinished;begins normalSTOPsequencewithrec_mode=1.
S_ABORT Always S_IDLE Releasesbus ownership,clearsrecoverymode,puts theerrorcodeintoresp,andreturnstoidle.
Any undefined
state Any S_IDLE Defaultsafetytransitionback toS_IDLE.
7.3 Command handshake (trig / resp)
i2c_byte_fsmandi2c_bitcommunicatethroughalevel-triggerhandshake.trigis acceptedonlywhile i2c_bitis
inS_IDLE(busfree) orS_HOLD(busowned);itisignoredinany other state.Whenthecommandis
acceptedrespbecomesINPROGRESS;thecallerthenreturns trigtoIDLE.Whenthecommandfinishes,
respholdstheresultuntil thenextcommandisaccepted.
trig encodings.
Name Value Meaning
TRIG_IDLE 0 Nocommand.
TRIG_START 1 FromS_IDLE:START.FromS_HOLD:repeatedSTART (afteratleastT_HD_DATofSCL
low).LeavesSCLlowandtheengineinS_HOLD.

--- Page 19 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page19of21
Name Value Meaning
TRIG_TX 2 Sendtx_data[7:0]MSBfirst,thenreadtheslave'sACK bitintorx_data[0](0=ACK,1=NACK).
ValidonlyinS_HOLD.
TRIG_RX 3 Receiveeight bits,thendrivetheACKbittx_data[0](0=ACK,1= NACK),latchedat
acceptance.rx_data[7:0]=receivedbyte.
TRIG_STOP 4 GenerateSTOPandwaitthebus-freetime.InS_IDLE itisano-opreturningRESP_IDLE.
resp encodings.
Name Value Meaning
RESP_IDLE 0 Success.
RESP_INPROGRESS 1 Commandrunning.
RESP_ARB_LOST 2 Atransmitted1readbackas0(databitsonly),orSDAlowwhenaSTARTorrepeated
START neededithigh.
RESP_SDA_ERR 3 SDAstucklow andstilllowafterbusrecovery.
RESP_SDA_RECOVERY 4 SDAwasstucklow;9-clockrecoveryplusSTOPreleasedit.
RESP_SCL_ERR 5 SCLheldlowlongerthanstretch_timeout,orstucklow atSTART.
RESP_BUS_BUSY 6 BusnotfreewhenaSTART wasrequested,orTX/RX issuedwithnoSTART.
Handshakelatency: i2c_bitmovestoresp=INPROGRESSonecycleafteritsamples trig;trigis held fortwo
cycles.After theresultappears onresptherunnerpulsesdoneonecyclelater,and thebyteFSMactson
doneinthefollowing cycle.
8. Reference Specification and Supported Features
Reference Specification:NXP/Philips I2C-BusSpecificationand UserManual,UM10204.
Feature (from reference spec) Spec
Section/Clause
Supported?
(Yes /
Partial / No)
Notes
START /repeatedSTART
generation
3.1.4,3.1.10 Yes -
STOPgeneration 3.1.5 Yes -
7-bitaddressing 3.1.11 Yes -
10-bitaddressing 3.1.11 Yes Write,readanddirection-change forms;seeSection6.4.
Standard-mode(100kHz) 5,Table10 Yes -
Fast-mode(400kHz) 5,Table10 Yes -
Fast-modePlus(1MHz) 5,Table10 Yes -
Master-transmitter:receive
ACK/NACK
- Yes NACKreportedinIRQ_STATUS[0].
Master-receiver:generate
ACK/NACK,NACK onlastbyte
- Yes ACKonlyifanotherCMD_RX isalreadyqueued(Section
6.5).
SDAholdtimeafterSCLfalls
(internalhold)
- Yes T_HD_DAT=300ns.
Clockstretching(masterwaitsfor
astretchedSCL)
3.1.9 Yes Programmabletimeout;atimeoutisflagged
(IRQ_STATUS[4]),notauto-recovered.
Clocksynchronization(wired-AND
SCL)
- Yes SCLhightimeiscountedfromobservedSCLhigh.
Multi-masterarbitration-loss
detection
3.1.6 Yes Atransmitted1readbackas0,orSDA lowata
(repeated)START.
Arbitrationrecovery/retry 3.1.6 No Lossisreportedandthetransferabandoned;no

--- Page 20 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page20of21
Feature (from reference spec) Spec
Section/Clause
Supported?
(Yes /
Partial / No)
Notes
automaticretry.
Busclear(stuckSDA) 3.1.16 Yes 9clockpulsesplusSTOP;oneretryoftheinitiating
START.
Inputspikesuppression(tSP,50
nsforFastandFast+)
- Partial DigitalfilterrejectspulsesshorterthanFILTER_LEN
PCLKcycles.Meeting50nsneedsFILTER_LEN x
PCLKperiodofatleast50ns(forexample
FILTER_LEN >=5at100MHz).
Generalcalladdress(0x00) 3.1.13 No Notimplemented.
Softwareresetviageneralcall 3.1.13 No Notimplemented.
Reservedaddresses(START byte,
CBUS,deviceID,Hsmastercode)
- No Nospecialhandling;theaddressregistersacceptany
value.
High-speedmode(3.4MHz)and
UltraFast-mode
- No Outofscope.
Slavemode(addressmatch,ACK
generation,slavestretching)
3.1 No Outofscopeforthismodule;seeSection10.
SMBustimeout/PEC n/a(SMBus
extension)
No Notpartofthisproject'sscope.
9. Parameters
Top-level parameters (i2c_top)
Parameter Legal Range Default Effect
CLK_FREQ_MHZ >=10(>=20
recommended)
100 PCLKfrequencyinMHz;alltimingconstantsderivefromit.
Belowabout10MHzFast-modePlusmarginscollapse.
FILTER_LEN >=1 3 Glitch-filterlengthinPCLK cycles;shorterpulsesarerejected.
GLITCH_FILTER_EN 0or1 1 1= filteractive,0=bypass(combinationalpass-through).
CMD_FIFO_DEPTH powerof2,>=2 1024 CommandFIFOentries(12bitseach);checkedat
elaboration.
RX_FIFO_DEPTH powerof2,>=2 1024 RXFIFOentries(8bitseach);checkedatelaboration.
Internal parameters and derived values
Parameter Legal Range Default Effect
CMD_HEADER_WIDTH
(i2c_byte_fsm)
4only 4 Widthofthecommand-wordheader;checkedatelaboration.
DATA_WIDTH
(i2c_byte_fsm)
8only 8 WidthofcommanddataandofTX/RXdata;checkedat
elaboration.
WIDTH(i2c_bit) >=CNT_WIDTH 24 Widthofstretch_timeoutandsda_stuck_timeout(3x8to
matchthetimeoutcommandwords).
CNT_WIDTH(i2c_bit,
derived)
derived 10at100
MHz
$clog2(NS2C(6000)+1),sizedfromthelargestconstant
(Standard-modetLOW).
RESET_VAL(sync_2ff,
i2c_glitch)
1'b0or1'b1 1'b1 Resetvalueofthesynchronizerandfilter;1matchesthe
pulled-upidlebus.
WIDTH,DEPTH (i2c_fifo) DEPTH powerof
2,>=2
12/8,1024 Entrywidthanddepth;setbythetop-levelparametersabove.
10. Known Limitations
• Mastermodeonly. Slavemode(addressmatch,ACK generation,slaveclockstretching,generalcall)is
outofscopeforthiscontroller.

--- Page 21 ---
I2CMasterControllerwithAPB4Interface-DesignSpecificationv1.1
Page21of21
• Nodone,busyorFIFO-level statusandnocompletioninterrupt.Completionisinferredfrom
TX_COUNT/RX_COUNT andIRQ_STATUS,andtheendofthe STOPconditionis notobservablein
registers.Thecountersare16bits,wrap,and cannotbeclearedexceptbyreset.
• irqhas nomaskorenable register andincludestheinformationalSDA-recoveredbit.
• Atransactionendswhenthe commandFIFOhasnodatacommandatthehead afterabyte.Ifsoftware
queuesbytes moreslowly thanthebus consumesthem,thetransactionissplitby aSTOP.A
configurationwordattheFIFOheadalsoends atransaction.
• AnRXbyte isACKedonlyifthenextRX_DATAwriteisalready queuedwhenthe byte'sACK/NACKis
committed.Arequestthatarrives onebytelatecompletes correctlybutthrougharepeatedSTART and
anewaddressphase.
• CommandFIFOfull:thewriteis droppedand onlyIRQ_STATUS[6]isset.Adroppedcommandinthe
middleofatransactionchanges whatissent,andtheFIFOlevel cannotberead.
• RXFIFOoverflowandunderflowarenotreported.Abytereceived whiletheRXFIFOis fullis dropped
butstillcountedinrx_count,andanempty-FIFO readreturns0x00,whichisalso avaliddatavalue.
• Afteranerror,onlythedatacommandsalready queuedforthefailedtransactionarediscarded.
Commandswrittenafterwards startanewtransaction.
• Multi-masterarbitrationlossis detectedand thetransferabandoned,butthereisnoautomatic retryor
back-off;softwareobserves IRQ_STATUS[1]andre-issuesthetransfer.
• Aclock-stretchtimeoutisflaggedbuthasnorecoveryactionbeyondendingthetransaction.With
stretch_timeout= 0anendlessstretchhangs theengine.
• IftheSTART retryafterSDA recovery hitsasecondrecovery, thetransactionis abandonedandonly
IRQ_STATUS[3]isset.
• Configurationregistersarewrite-only andtakeeffectonlywhen poppedwhiletheengine isidle,inFIFO
order.
• TheSCLfrequencyisslightlybelownominalbecauseofsynchronizer andfilterlatency;the shortfall
growsatlowerPCLKfrequencies.
• DATA_WIDTHisaparameter ofthe byte-level FSM butthe designis correctonly forDATA_WIDTH=8;
othervaluesarerejectedbyanelaboration-timecheck.
• General-callrecognitionandthesoftware-resetbroadcastarenotimplemented.NoSMBus timeoutor
packet-errorchecking.
• PRESETnde-assertion isnotinternallyre-synchronized;aclean,glitch-freeresetisassumedtobe
suppliedfromoutsidetheblock.
• IllegalAPBaccessescompletenormally(PSLVERRis neverasserted) andarereportedonlythrough
IRQ_STATUS[7].