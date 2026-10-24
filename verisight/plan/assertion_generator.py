"""
Automated SystemVerilog Assertion (SVA) Synthesis Engine.

Inspired by:
1. AssertLLM: Generating Hardware Verification Assertions from Natural Language Specifications
   https://github.com/hkust-zhiyao/AssertLLM
2. AutoSVA: Automating Formal Testbench and Assertion Generation
   https://github.com/PrincetonUniversity/AutoSVA
"""

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from verisight.utils.logger import get_logger

logger = get_logger("assertion_generator")


class SynthesizedAssertion(BaseModel):
    """A synthesized SystemVerilog assertion."""
    name: str
    property_type: str = "assert"  # assert, assume, cover
    description: str = ""
    clock: str = "clk"
    reset: str = "rst_n"
    sva_code: str = ""
    target_rule: str = ""


class SVAProtocolSuite(BaseModel):
    """A complete suite of synthesized SVA checkers for a module."""
    module_name: str
    assertions: List[SynthesizedAssertion] = Field(default_factory=list)
    bind_file_content: str = ""


def synthesize_sva_from_spec(
    spec_text: str,
    module_name: str = "dut",
    clock_signal: str = "clk",
    reset_signal: str = "rst_n",
) -> SVAProtocolSuite:
    """
    Extracts specification invariants and synthesizes SystemVerilog Assertions.

    Args:
        spec_text: Text from specification markdown file.
        module_name: Target module name to bind assertions.
        clock_signal: Clock identifier (e.g. pclk, HCLK, clk).
        reset_signal: Active-low reset identifier (e.g. presetn, HRESETn, rst_n).

    Returns:
        SVAProtocolSuite containing synthesized properties and bindable code.
    """
    assertions: List[SynthesizedAssertion] = []
    lines = spec_text.splitlines()

    # Detect bus clock and reset naming if present in spec
    clk = clock_signal
    rst = reset_signal
    for line in lines:
        if "HCLK" in line:
            clk = "HCLK"
            rst = "HRESETn"
            break
        elif "pclk" in line:
            clk = "pclk"
            rst = "presetn"
            break

    # Rule 1: Read-Only Protection Rules
    for line in lines:
        if "read-only" in line.lower() or "read only" in line.lower():
            match_addr = re.search(r"(0x[0-9a-fA-F]+)", line)
            addr_val = match_addr.group(1) if match_addr else "32'h04"

            # Check if APB or AHB
            if "pslverr" in spec_text.lower():
                sva_body = (
                    f"property p_ro_protect;\n"
                    f"    @(posedge {clk}) disable iff (!{rst})\n"
                    f"    (psel && penable && pwrite && (paddr == {addr_val})) |-> pslverr;\n"
                    f"endproperty\n"
                    f"assert property (p_ro_protect)\n"
                    f"    else $error(\"SVA_ERR: Write to Read-Only register {addr_val} did not assert pslverr!\");"
                )
            else:
                sva_body = (
                    f"property p_ro_protect;\n"
                    f"    @(posedge {clk}) disable iff (!{rst})\n"
                    f"    (HSEL && HREADY && (HTRANS == 2'b10 || HTRANS == 2'b11) && HWRITE && (HADDR == {addr_val})) |=> HRESP;\n"
                    f"endproperty\n"
                    f"assert property (p_ro_protect)\n"
                    f"    else $error(\"SVA_ERR: Write to Read-Only register {addr_val} did not assert HRESP!\");"
                )

            assertions.append(SynthesizedAssertion(
                name="SVA_RO_WRITE_PROTECTION",
                description=f"Asserts error response when writing to read-only register {addr_val}",
                clock=clk,
                reset=rst,
                sva_code=sva_body,
                target_rule=line.strip(),
            ))
            break

    # Rule 2: Handshake / Ready Assertion
    if "pready" in spec_text.lower():
        sva_ready = (
            f"property p_ready_valid;\n"
            f"    @(posedge {clk}) disable iff (!{rst})\n"
            f"    (psel && penable) |-> (pready == 1'b1);\n"
            f"endproperty\n"
            f"assert property (p_ready_valid)\n"
            f"    else $warning(\"SVA_WARN: APB Slave pready dropped unexpectedly during access!\");"
        )
        assertions.append(SynthesizedAssertion(
            name="SVA_HANDSHAKE_READY",
            description="Asserts slave completion signal on transfer access",
            clock=clk,
            reset=rst,
            sva_code=sva_ready,
            target_rule="Handshake protocol ready completion",
        ))
    elif "hready" in spec_text.lower() or "hreadyout" in spec_text.lower():
        sva_ready = (
            f"property p_hreadyout_asserted;\n"
            f"    @(posedge {clk}) disable iff (!{rst})\n"
            f"    HREADYOUT == 1'b1;\n"
            f"endproperty\n"
            f"assert property (p_hreadyout_asserted)\n"
            f"    else $warning(\"SVA_WARN: AHB Slave HREADYOUT inserted wait state!\");"
        )
        assertions.append(SynthesizedAssertion(
            name="SVA_HANDSHAKE_READY",
            description="Asserts AHB slave HREADYOUT high",
            clock=clk,
            reset=rst,
            sva_code=sva_ready,
            target_rule="AHB transfer ready handshake",
        ))

    # Assemble bind file
    sva_blocks = "\n\n".join([a.sva_code for a in assertions])
    bind_code = (
        f"// Auto-generated SVA Assertion Suite by VeriSight (AssertLLM/AutoSVA methodology)\n"
        f"module {module_name}_sva_bind(\n"
        f"    input logic {clk},\n"
        f"    input logic {rst}\n"
        f");\n\n"
        f"{sva_blocks}\n\n"
        f"endmodule\n"
    )

    return SVAProtocolSuite(
        module_name=module_name,
        assertions=assertions,
        bind_file_content=bind_code,
    )
