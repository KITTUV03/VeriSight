# Single-Port Synchronous RAM Design Specification

## 1. Overview

The `ram_rtl` module is a parameterizable, single-port synchronous Random Access Memory (RAM) implemented in synthesizable SystemVerilog. It features a synchronous active-low reset, mutually exclusive write and read operations controlled by a single write-enable signal (`we`), and a registered read-data output (`rdata`).

- **Module Name:** `ram_rtl`
- **Source File:** `ram_rtl.sv`
- **Memory Architecture:** Single-port, synchronous read, synchronous write
- **Target Technology:** FPGA / ASIC synthesizable block memory

---

## 2. Parameters

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `DATA_WIDTH` | Integer | `8` | Width of data bus (`wdata` and `rdata`), in bits |
| `ADDR_WIDTH` | Integer | `4` | Width of address bus (`addr`), in bits |
| `RAM_DEPTH`  | Derived | `1 << ADDR_WIDTH` | Total addressable storage locations (default: $2^4 = 16$) |

---

## 3. Port List

| Signal Name | Direction | Width | Clock Domain | Description |
| :--- | :---: | :---: | :---: | :--- |
| `clk` | Input | `1` | Source | System clock. All operations trigger on the positive edge (`posedge clk`). |
| `rst_n` | Input | `1` | `clk` | Synchronous active-low reset. Evaluated on the rising edge of `clk`. |
| `we` | Input | `1` | `clk` | Write Enable control: `1` = Write operation; `0` = Read operation. |
| `addr` | Input | `ADDR_WIDTH` | `clk` | Memory address for the target read or write operation. |
| `wdata` | Input | `DATA_WIDTH` | `clk` | Input data word to be stored into `mem[addr]` during a write operation. |
| `rdata` | Output | `DATA_WIDTH` | `clk` | Registered read data output. Updated synchronously on read operations. |

---

## 4. Functional Requirements

### REQ-001: Synchronous Reset
- **Description:** When `rst_n` is sampled LOW (`1'b0`) at the rising edge of `clk`, the read data output `rdata` shall be cleared to all zeros (`'0`).
- **Internal Storage Preservation:** The internal memory array `mem` is **not** cleared on reset and retains its existing state.

### REQ-002: Synchronous Write Operation
- **Condition:** When `rst_n` is HIGH (`1'b1`) and `we` is HIGH (`1'b1`) at `posedge clk`.
- **Behavior:** The data present on `wdata` shall be written into internal memory location `mem[addr]`.
- **Output Preservation:** The read data output `rdata` shall remain unchanged (holding its previous registered value) during a write cycle.

### REQ-003: Synchronous Read Operation
- **Condition:** When `rst_n` is HIGH (`1'b1`) and `we` is LOW (`1'b0`) at `posedge clk`.
- **Behavior:** The data stored in memory location `mem[addr]` shall be sampled and transferred to the registered output `rdata`.
- **Latency:** Read data is available on `rdata` with a latency of exactly **one clock cycle** following the assertion of `addr` with `we = 0`.

### REQ-004: Mutually Exclusive Access
- **Description:** Write and read operations are mutually exclusive within a given clock cycle:
  - If `we == 1'b1`: Memory write is executed; read is suppressed (`rdata` holds previous value).
  - If `we == 1'b0`: Memory read is executed; memory array `mem` is untouched.

---

## 5. Timing Requirements

- **Clock Sensitivity:** All sequential updates occur strictly on the positive edge of `clk` (`posedge clk`).
- **Reset Timing:** Reset `rst_n` is synchronous. Changes on `rst_n` take effect only upon the next active rising clock edge.
- **Input Setup & Hold:** `we`, `addr`, and `wdata` must meet standard setup and hold times relative to `posedge clk`.
- **Read Output Latency:** Exactly 1 clock cycle (pipelined synchronous output).

---

## 6. Memory Array Behavior & Initial State

- The memory storage array `mem[0 : (1<<ADDR_WIDTH)-1]` consists of $2^{\text{ADDR\_WIDTH}}$ words of `DATA_WIDTH` bits.
- Because `mem` is not reset on `rst_n`, reading an address before any write operation has occurred to that specific address will return an uninitialized value (4-state simulation value `X`).
- Valid read transactions require prior write initialization to the addressed location.

---

## 7. Verification Invariants & SVA Formal Contracts

```systemverilog
// Invariant 1: Synchronous Reset Contract
property p_ram_sync_reset;
    @(posedge clk) (!rst_n) |=> (rdata == '0);
endproperty

// Invariant 2: Write Operation Data Stability
property p_ram_write_hold_rdata;
    @(posedge clk) disable iff (!rst_n)
    (we) |=> $stable(rdata);
endproperty

// Invariant 3: Synchronous Read Capture
property p_ram_read_latency;
    logic [ADDR_WIDTH-1:0] sampled_addr;
    @(posedge clk) disable iff (!rst_n)
    (!we, sampled_addr = addr) |=> (rdata == mem[sampled_addr]);
endproperty
```
