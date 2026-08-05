# Synchronous FIFO Design Specification

## Overview

This document specifies a parameterized synchronous First-In-First-Out (FIFO) buffer designed for reliable data transfer between synchronous blocks within a single clock domain. The FIFO supports configurable data width and depth, provides comprehensive status monitoring, and includes protection mechanisms against overflow and underflow conditions. The design is suitable for use in high-speed datapath buffering, packet processing pipelines, and inter-module communication interfaces.

## Functional Requirements

- The FIFO shall accept two configurable parameters at elaboration time:
  - DATA_WIDTH: Width of each data word in bits (minimum: 1, typical: 8/16/32/64)
  - ADDR_WIDTH: Address width determining the FIFO depth, where DEPTH = 2^ADDR_WIDTH (minimum ADDR_WIDTH: 2, giving depth 4)
- The FIFO shall accept a single-bit write enable input signal (wr_en)
- The FIFO shall accept a data input bus (din) of width DATA_WIDTH
- The FIFO shall accept a single-bit read enable input signal (rd_en)
- The FIFO shall produce a data output bus (dout) of width DATA_WIDTH
- The FIFO shall produce a single-bit full flag (full) indicating no space remains for writing
- The FIFO shall produce a single-bit empty flag (empty) indicating no data is available for reading
- The FIFO shall produce a single-bit almost-full flag (almost_full) with a configurable threshold AF_LEVEL
- The FIFO shall produce a single-bit almost-empty flag (almost_empty) with a configurable threshold AE_LEVEL
- The FIFO shall produce a single-bit overflow flag (overflow) asserted for one cycle when wr_en is asserted while full
- The FIFO shall produce a single-bit underflow flag (underflow) asserted for one cycle when rd_en is asserted while empty
- The FIFO shall produce a count output bus (wr_count) of width ADDR_WIDTH+1 indicating the number of occupied locations
- The FIFO shall produce a count output bus (rd_count) of width ADDR_WIDTH+1 indicating the number of available words to read
- The FIFO shall support two operating modes selectable at elaboration time:
  - FWFT_MODE = 0: Standard mode — data appears on dout one clock cycle after rd_en assertion
  - FWFT_MODE = 1: First-Word Fall-Through mode — next data word appears on dout combinatorially after previous read, before rd_en assertion
- The FIFO shall support an optional registered output stage selectable at elaboration time:
  - REG_OUTPUT = 0: Combinational output from memory array
  - REG_OUTPUT = 1: Output registered for improved timing closure
- The FIFO shall implement a circular buffer architecture with one permanently unused location to distinguish between full and empty conditions
- All pointer arithmetic shall use an extra most significant bit beyond ADDR_WIDTH for full/empty disambiguation

## Reset Behavior

- The FIFO shall use an active-low asynchronous reset (rst_n)
- On reset assertion, the following behavior shall occur:
  - Write pointer (wr_ptr) shall be reset to 0
  - Read pointer (rd_ptr) shall be reset to 0
  - full flag shall be driven to 1'b0
  - empty flag shall be driven to 1'b1
  - almost_full flag shall be driven to 1'b0
  - almost_empty flag shall be driven to 1'b1
  - overflow flag shall be driven to 1'b0
  - underflow flag shall be driven to 1'b0
  - Memory contents may remain unchanged (no explicit clearing required)
  - In FWFT mode, dout register shall be driven to 0
- Reset must be held active for a minimum of 3 clock cycles to ensure proper initialization of all internal state
- After reset de-assertion, the FIFO shall be ready to accept write operations on the subsequent clock cycle
- The empty flag shall remain asserted until the first successful write operation completes

## Timing Requirements

- Clock frequency: The FIFO shall support operation at frequencies up to 400 MHz (2.5 ns period) in typical 28nm CMOS technology, subject to timing closure with actual parameters
- Setup time: All input signals (wr_en, rd_en, din) must be stable at least 0.5 ns before the rising clock edge
- Hold time: All input signals must remain stable for at least 0.2 ns after the rising clock edge
- Clock-to-output delay: Output signals (dout, flags, counts) shall be valid within 1.5 ns after the rising clock edge in REG_OUTPUT=0 mode
- Write latency: Data written on cycle N shall be available for reading on cycle N+1 (one clock cycle from write enable to data available in memory)
- Read latency (Standard mode): Data shall appear on dout in the same cycle as rd_en assertion, sourced from memory array
- Read latency (FWFT mode): Next data word shall appear on dout one cycle after the previous read completes, before subsequent rd_en assertion
- Flag update latency: full, empty, almost_full, and almost_empty flags shall reflect the FIFO state in the same clock cycle as the operation that caused the state change
- Overflow/underflow latency: Error flags shall be asserted in the same cycle as the violating operation
- Count update latency: wr_count and rd_count shall reflect the number of words in the FIFO in the same clock cycle as write/read operations
- All operations complete in a single clock cycle with no multi-cycle paths
- Maximum throughput: One write and one read per clock cycle when FIFO is neither full nor empty (simultaneous read/write supported)

## Corner Cases

- **Simultaneous read and write when FIFO is empty**: Write succeeds (data stored), read does not occur (underflow asserted), empty flag remains asserted until write completes, then de-asserts in subsequent cycle
- **Simultaneous read and write when FIFO is full**: Read succeeds (data retrieved), write does not occur (overflow asserted), full flag remains asserted until read completes, then de-asserts in subsequent cycle
- **Simultaneous read and write when FIFO is neither full nor empty**: Both operations succeed, FIFO occupancy count (wr_count/rd_count) remains unchanged
- **Write to FIFO with one remaining empty slot**: Write succeeds, full flag asserts in the same cycle, wr_count equals DEPTH-1 after write
- **Read from FIFO with one remaining data word**: Read succeeds, empty flag asserts in the same cycle, rd_count equals 0 after read
- **Back-to-back writes when almost-full**: AF_LEVEL defines the threshold; when wr_count >= AF_LEVEL, almost_full asserts. If AF_LEVEL = DEPTH-2, almost_full asserts when 2 or fewer empty slots remain
- **Back-to-back reads when almost-empty**: AE_LEVEL defines the threshold; when rd_count <= AE_LEVEL, almost_empty asserts. If AE_LEVEL = 2, almost_empty asserts when 2 or fewer data words remain
- **Pointer wraparound**: When write pointer or read pointer reaches DEPTH-1 and increments, it shall wrap to 0 correctly with the extra address bit toggling for full/empty distinction
- **Write when wr_ptr+1 == rd_ptr (all locations full)**: Write is suppressed, overflow flag asserts for one cycle, data is not stored, memory contents preserved
- **Read when rd_ptr == wr_ptr (all locations empty)**: Read returns undefined data (memory contents at read address), underflow flag asserts for one cycle, read pointer does not advance
- **DATA_WIDTH = 1 (single-bit FIFO)**: All operations function identically with 1-bit data path width
- **ADDR_WIDTH = 2 (depth of 4)**: FIFO functions correctly with minimal depth, AF_LEVEL and AE_LEVEL must be adjusted accordingly
- **AF_LEVEL set to DEPTH (threshold equals capacity)**: almost_full never asserts
- **AE_LEVEL set to 0**: almost_empty asserts only when FIFO is completely empty
- **FWFT mode read from empty FIFO**: dout holds the last valid data word read; empty flag indicates data is not valid
- **Reset assertion during active read/write**: Both operations aborted, pointers reset, flags reset, any in-flight data lost
- **Parameter validation at elaboration time**: The design shall verify at compile time that DEPTH equals 2^ADDR_WIDTH; mismatch shall result in a compilation error

## Illegal Conditions

- **Operation without reset**: Operating the FIFO without first asserting the reset signal for the minimum required duration (3 clock cycles) is illegal and may result in pointer misalignment, incorrect flag states, and data corruption
- **Asserting reset for fewer than 3 clock cycles**: May result in incomplete initialization of internal state elements, leaving flags in unknown states
- **Changing inputs during setup/hold window**: Input signals (wr_en, rd_en, din) shall not transition within the setup-hold window around the active clock edge; violation may cause metastability on captured signals
- **Writing while FIFO is full with overflow protection ignored**: The hardware suppresses the write and asserts overflow, but the external logic must not rely on the write having succeeded
- **Reading while FIFO is empty with underflow protection ignored**: The hardware suppresses the read and asserts underflow; dout value is undefined and must not be used by downstream logic
- **Exceeding ADDR_WIDTH of 16**: Depth beyond 65536 locations (ADDR_WIDTH > 16) is not supported without timing verification; the circular buffer addressing and flag generation must be re-evaluated for such configurations
- **DATA_WIDTH of 0**: Zero-width data path is undefined and shall not be used
- **Asynchronous reset de-assertion coincident with clock edge**: Reset de-assertion must not occur simultaneous with the active clock edge; a minimum separation of 1 ns is required to avoid recovery/removal timing violations
- **Modifying FIFO parameters after synthesis**: All parameter values (DATA_WIDTH, ADDR_WIDTH, FWFT_MODE, REG_OUTPUT, AF_LEVEL, AE_LEVEL) are fixed at elaboration time and cannot be changed dynamically during operation
- **Using AF_LEVEL greater than or equal to DEPTH**: If AF_LEVEL >= DEPTH, the almost_full flag behavior is undefined; AF_LEVEL must satisfy 0 <= AF_LEVEL < DEPTH
- **Using AE_LEVEL greater than or equal to DEPTH**: If AE_LEVEL >= DEPTH, the almost_empty flag behavior is undefined; AE_LEVEL must satisfy 0 <= AE_LEVEL < DEPTH
- **Violating maximum fanout on pointer registers**: In deep FIFO configurations (ADDR_WIDTH > 8), the read and write pointers drive comparators for all status flags; physical synthesis must ensure timing closure, else register duplication may be required