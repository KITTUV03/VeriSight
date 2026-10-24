RAM RTL Specification
1. Overview
The `ram_rtl` module implements a parameterized memory with a synchronous read interface and a write operation controlled by `we`. The memory stores `2**ADDR_WIDTH` words, each `DATA_WIDTH` bits wide.
The specification below describes the behavior directly implemented by the RTL. It does not assume memory initialization, write-during-reset behavior beyond the code, or any behavior not explicitly defined in the module.
2. Parameters
Parameter	Default	Description
`DATA_WIDTH`	`8`	Number of bits in each memory word and in `wdata`/`rdata`.
`ADDR_WIDTH`	`4`	Number of address bits. The memory depth is `2**ADDR_WIDTH`.
With the default parameters, the memory contains 16 words, each 8 bits wide, addressed from 0 through 15.
3. Interface Signals
Signal	Direction	Width	Description
`clk`	Input	1 bit	Rising-edge clock for sequential operations.
`rst_n`	Input	1 bit	Active-low synchronous reset for `rdata`.
`we`	Input	1 bit	Write enable. When high, the addressed memory word is written. When low, a read is performed.
`addr`	Input	`ADDR_WIDTH` bits	Address of the memory word to access.
`wdata`	Input	`DATA_WIDTH` bits	Data to write when `we` is high.
`rdata`	Output	`DATA_WIDTH` bits	Registered read-data output.
4. Functional Behavior
All operations occur on the rising edge of `clk`.
4.1 Reset
When `rst_n == 0` at a rising clock edge:
`rdata` is assigned zero.
No memory write or read is performed on that edge.
The memory array `mem` is not reset or initialized by this RTL; its contents are retained.
The reset is synchronous because it is checked inside `always_ff @(posedge clk)`.
4.2 Write Operation
When `rst_n == 1` and `we == 1` at a rising clock edge:
`mem[addr]` is assigned `wdata`.
`rdata` is not assigned and therefore retains its previous value.
4.3 Read Operation
When `rst_n == 1` and `we == 0` at a rising clock edge:
`mem[addr]` is sampled and assigned to `rdata`.
The read is synchronous and registered.
If the selected memory location has not previously been written or otherwise initialized, the read value is unknown in simulation.
4.4 Operation Priority
At each rising clock edge, the behavior is selected in this order:
If `rst_n == 0`, clear `rdata`; no memory access occurs.
Otherwise, if `we == 1`, write `wdata` to `mem[addr]`; hold `rdata`.
Otherwise, read `mem[addr]` into `rdata`.
A write and read are not performed together in the same clock cycle by this RTL.
5. Timing and Output Hold Behavior
Inputs are evaluated at the rising edge of `clk`.
`rdata` changes only on a rising edge when reset is active or a read operation is selected.
During a write cycle (`rst_n == 1` and `we == 1`), `rdata` holds its previous value.
There is no combinational read path from `addr` to `rdata`.
There is no explicit read-during-write behavior because the RTL selects either a write or a read based on `we`.
6. Memory Organization and Addressing
Memory declaration: `mem[0:(1<<ADDR_WIDTH)-1]`.
Number of words: `2**ADDR_WIDTH`.
Word width: `DATA_WIDTH` bits.
Valid address range: `0` through `(2**ADDR_WIDTH)-1`.
For the default configuration (`ADDR_WIDTH = 4`, `DATA_WIDTH = 8`):
Depth: 16 words.
Address range: 0–15.
Word width: 8 bits.
7. Initialization and Reset Limitations
The RTL does not initialize `mem`.
Reset clears only `rdata`; it does not clear the stored memory.
Memory contents that have not been written may appear as `X` in simulation.
After reset is deasserted, `rdata` remains zero until a read operation updates it, unless another operation changes it according to the RTL.
No asynchronous reset behavior is implemented.
8. Behavioral Summary
Condition at rising `clk` edge	Memory action	`rdata` action
`rst_n == 0`	No access; contents retained	Set to zero
`rst_n == 1`, `we == 1`	Write `wdata` to `mem[addr]`	Hold previous value
`rst_n == 1`, `we == 0`	Read `mem[addr]`	Update with selected word
9. Verification Points
A testbench or verification environment should check the following behaviors:
Reset drives `rdata` to zero on a rising clock edge while `rst_n` is low.
Reset does not clear previously written memory locations.
A write stores `wdata` at the selected address.
A write cycle leaves `rdata` unchanged.
A read cycle updates `rdata` with the contents of the selected address.
Reading an unwritten location may produce an unknown value in simulation.
The design supports the configured address range and data width.
Memory access is suppressed while reset is asserted.
Read data is registered; changing `addr` between rising edges does not by itself change `rdata`.
10. Scope and Assumptions
This specification reflects the provided RTL only. It does not define behavior for unknown (`X`/`Z`) control inputs, out-of-range indexing caused by unusual parameter values, or physical memory inference characteristics. No memory initialization, byte enables, simultaneous read/write, error handling, or asynchronous output behavior is implemented.