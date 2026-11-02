# AMBA AHB-Lite (Advanced High-performance Bus) Slave Specification

## 1. Overview
The **AMBA AHB-Lite Slave** is a 32-bit pipelined bus interface designed in accordance with the **ARM AMBA 3 AHB-Lite Protocol Specification (v1.0)**. It supports high-speed register access, burst operations, single-wait-state bus handshakes, and error response signaling for SoC system buses.

---

## 2. Interface Signal Definitions

| Signal Name | Width | Direction | Active Level | Description |
|:---|:---:|:---:|:---:|:---|
| `HCLK` | 1 | Input | Rising Edge | Primary bus clock. All bus timings are synchronous to rising edge of `HCLK`. |
| `HRESETn` | 1 | Input | Low | Active-low system reset. Initializes all registers and state machines. |
| `HSEL` | 1 | Input | High | Slave select. Driven high by bus interconnect when this slave is addressed. |
| `HADDR` | 32 | Input | - | 32-bit address bus for transfer address phase. |
| `HTRANS` | 2 | Input | - | Transfer type:<br/>• `2'b00` = `IDLE`<br/>• `2'b01` = `BUSY`<br/>• `2'b10` = `NONSEQ`<br/>• `2'b11` = `SEQ` |
| `HWRITE` | 1 | Input | High/Low | Transfer direction: `1` = Write transfer, `0` = Read transfer. |
| `HSIZE` | 3 | Input | - | Transfer size: `3'b010` indicates 32-bit word transfer. |
| `HBURST` | 3 | Input | - | Burst type: `3'b000` = `SINGLE`, `3'b001` = `INCR`. |
| `HPROT` | 4 | Input | - | Protection control (opcode fetch, privileged, bufferable, cacheable). |
| `HWDATA` | 32 | Input | - | 32-bit write data bus driven during the data phase of write transfers. |
| `HREADY` | 1 | Input | High | Transfer ready input from interconnect/previous slave. |
| `HREADYOUT` | 1 | Output | High | Transfer ready output driven by slave. High indicates transfer complete. |
| `HRDATA` | 32 | Output | - | 32-bit read data bus driven during the data phase of read transfers. |
| `HRESP` | 1 | Output | High | Transfer response: `1'b0` = `OKAY`, `1'b1` = `ERROR`. |

---

## 3. Register Memory Map

The slave exposes 32-bit memory-mapped registers aligned to 4-byte boundaries:

| Offset | Register Name | Access Type | Reset Value | Description |
|:---:|:---|:---:|:---:|:---|
| `0x00` | `REG_CTRL` | Read / Write | `0x00000000` | **Control Register**<br/>• Bit [0]: Core Enable (`EN`)<br/>• Bit [1]: Interrupt Enable (`INT_EN`)<br/>• Bits [3:2]: Mode (`00`=Normal, `01`=Loopback, `10`=Diagnostic) |
| `0x04` | `REG_STATUS` | **Read-Only** | `0x00000002` | **Status Register**<br/>• Bit [0]: Busy flag (`BUSY`)<br/>• Bit [1]: Ready flag (`READY`, default `1`)<br/>• Bit [2]: Error flag (`ERR`)<br/>*Requirement:* Any write attempt to `REG_STATUS` must trigger an error response (`HRESP = 1`). |
| `0x08` | `REG_DATA0` | Read / Write | `0x00000000` | **Data Register 0**<br/>Full 32-bit read/write retention data buffer. |
| `0x0C` | `REG_DATA1` | Read / Write | `0x00000000` | **Data Register 1**<br/>Secondary 32-bit general-purpose data storage. |
| `0x10` | `REG_BURST_CNT` | Read / Write | `0x00000000` | **Burst Count Register**<br/>Tracks accumulated burst transfers. Initialized to `0x00000000`. |

---

## 4. AHB-Lite Protocol Rules & Timing

1. **Two-Phase Transfer Pipeline:**
   - **Address Phase (Cycle T):** When `HSEL && HREADY && (HTRANS == NONSEQ || HTRANS == SEQ)`, address and control signals (`HADDR`, `HWRITE`, `HSIZE`) are sampled.
   - **Data Phase (Cycle T+1):** Write data (`HWDATA`) is written into target register, or read data (`HRDATA`) is returned to the master.
2. **Error Response (`HRESP = 1`):**
   - Must be asserted for two cycles during an error condition in accordance with AHB specification.
   - **Condition 1 (Unmapped Address):** Accesses to offsets greater than `0x10` must trigger `HRESP = 1` and `HRDATA = 32'hDEAD_0000`.
   - **Condition 2 (Read-Only Write Protection):** A write to `REG_STATUS` (`0x04`) must trigger `HRESP = 1`, and `REG_STATUS` contents must remain unchanged.
3. **Data Integrity:**
   - All 32 bits written to `REG_DATA0` and `REG_DATA1` must be stored and returned verbatim on readback.
