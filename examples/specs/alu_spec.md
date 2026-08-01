# ALU Design Specification

## Overview

This document specifies a simple 8-bit Arithmetic Logic Unit (ALU) that performs basic arithmetic and logic operations. The ALU is intended for use in a pipelined processor datapath.

## Functional Requirements

- The ALU shall accept two 8-bit input operands (operand_a, operand_b)
- The ALU shall accept a 4-bit operation select signal (op_sel)
- The ALU shall produce an 8-bit result output
- The ALU shall produce a 1-bit carry output for arithmetic operations
- The ALU shall produce a 1-bit zero flag when the result is zero
- All outputs shall be registered (one clock cycle latency)
- The ALU shall support the following operations:
  - 4'b0000: ADD (operand_a + operand_b)
  - 4'b0001: SUB (operand_a - operand_b)
  - 4'b0010: AND (operand_a & operand_b)
  - 4'b0011: OR  (operand_a | operand_b)
  - 4'b0100: XOR (operand_a ^ operand_b)
  - 4'b0101: NOT (~operand_a)
  - 4'b0110: SHL (operand_a << operand_b[2:0])
  - 4'b0111: SHR (operand_a >> operand_b[2:0])

## Reset Behavior

- The ALU uses an active-low asynchronous reset (rst_n)
- On reset assertion, all outputs shall be driven to 0:
  - result = 8'h00
  - carry = 1'b0
  - zero = 1'b0
- Reset must be held for at least 2 clock cycles

## Timing Requirements

- Clock frequency: 100 MHz (10 ns period)
- Setup time: All inputs must be stable at least 1 ns before the rising clock edge
- Output latency: 1 clock cycle from input to output
- All operations complete in a single clock cycle

## Corner Cases

- Addition overflow: When operand_a + operand_b > 255, carry must be set
- Subtraction underflow: When operand_a < operand_b, result wraps and carry is set
- Shift by zero: Result equals operand_a, no modification
- Undefined opcode: For op_sel values 4'b1000 through 4'b1111, result shall be 8'h00

## Illegal Conditions

- Operating the ALU without proper reset sequence is illegal
- Changing inputs during the clock edge is illegal
- Asserting reset for less than 2 clock cycles is illegal
