# AMBA APB (Advanced Peripheral Bus) Slave Specification

## 1. Overview
The **AMBA APB Slave** is a 32-bit register controller interface designed in accordance with the **ARM AMBA 3 / AMBA 4 APB Protocol Specification**. It provides a low-overhead, non-pipelined bus slave interface for peripheral device registers, control blocks, and status monitoring.

---

## 2. Interface Signal Definitions

| Signal Name | Width | Direction | Active Level | Description |
|:---|:---:|:---:|:---:|:---|
| `pclk` | 1 | Input | Rising Edge | APB bus clock. All signals sampled on rising edge. |
| `presetn` | 1 | Input | Low | Asynchronous/Synchronous system reset. Active low. |
| `paddr` | 32 | Input | - | 32-bit peripheral address bus. |
| `psel` | 1 | Input | High | Peripheral slave select. Indicates slave is targeted. |
| `penable` | 1 | Input | High | APB strobe. Indicates the second and subsequent cycles of an APB transfer. |
| `pwrite` | 1 | Input | High/Low | Transfer direction. `1` = Write, `0` = Read. |
| `pwdata` | 32 | Input | - | 32-bit write data bus driven by APB bridge/master. |
| `pready` | 1 | Output | High | Handshake extension. Slave pulls `pready=1` when ready to complete transfer. |
| `prdata` | 32 | Output | - | 32-bit read data bus driven by the slave during read operations. |
| `pslverr` | 1 | Output | High | Slave error response. Indicates an illegal transaction. |

---

## 3. Register Memory Map

The slave implements memory-mapped 32-bit registers aligned to 4-byte boundaries:

| Offset | Register Name | Access Type | Reset Value | Description |
|:---:|:---|:---:|:---:|:---|
| `0x00` | `REG_CTRL` | Read / Write | `0x00000000` | **Control Register**<br/>• Bit [0]: Core Enable (`EN`)<br/>• Bit [1]: Interrupt Enable (`INT_EN`)<br/>• Bits [3:2]: Operating Mode (`00`=Normal, `01`=Loopback, `10`=Diagnostic) |
| `0x04` | `REG_STATUS` | **Read-Only** | `0x00000002` | **Status Register**<br/>• Bit [0]: Busy flag (`BUSY`)<br/>• Bit [1]: Ready flag (`READY`, default `1`)<br/>• Bit [2]: Error flag (`ERR_OCCURRED`)<br/>*Note:* Any write attempt to this register must assert `pslverr`. |
| `0x08` | `REG_DATA0` | Read / Write | `0x00000000` | **Data Register 0**<br/>32-bit general-purpose data storage buffer. Full 32-bit read/write retention. |
| `0x0C` | `REG_DATA1` | Read / Write | `0x00000000` | **Data Register 1**<br/>32-bit secondary general-purpose data storage buffer. |
| `0x10` | `REG_TIMER` | Read / Write | `0x00000000` | **Timer Counter Register**<br/>32-bit timer value incrementing on every clock cycle when `REG_CTRL[0]` is active. |

---

## 4. APB Protocol Timing & State Machine

1. **IDLE State:**
   - `psel = 0`, `penable = 0`, `pready = 1`, `pslverr = 0`. No active transfer.
2. **SETUP State:**
   - Initiated when `psel = 1` and `penable = 0`.
   - `paddr`, `pwrite`, and `pwdata` (if write) are driven and held stable.
3. **ACCESS State:**
   - On the next clock cycle, master asserts `penable = 1`.
   - Slave drives `pready = 1` when ready to complete.
   - For write operations, slave registers internal data on rising edge of `pclk` when `penable && pready`.
   - For read operations, slave drives valid `prdata` while `penable && pready`.
   - Master deasserts `penable` (and `psel` if no back-to-back transfer) on the subsequent clock cycle.

---

## 5. Protocol Error Conditions & PSLVERR Rules

1. **Unmapped Address Access:**
   - Any transaction targeting an address offset outside the valid range (`paddr > 0x10`) must complete with `pslverr = 1` and `prdata = 32'hDEAD_0000`.
2. **Read-Only Register Write Protection:**
   - Any write transaction targeting `REG_STATUS` (`paddr == 32'h04` and `pwrite == 1`) must assert `pslverr = 1` during the ACCESS phase. The contents of `REG_STATUS` must remain unaltered.
3. **PENABLE Strobe Timing Rule:**
   - `penable` must never be asserted without `psel` being asserted simultaneously.
