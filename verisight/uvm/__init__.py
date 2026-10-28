"""
VeriSight UVM Architect Package.

Autonomous UVM Testbench Environment Generator inspired by XcelUVM:
- Generates complete, standards-compliant, cycle-accurate UVM 1.2 environments
- Interfaces, sequence items with constraints, driver, monitor, agent, scoreboard
- Reference models (SV behavioral), coverage subscribers, SVA assertions bind module
- Top-level testbench, package, Questa/VCS run scripts, and EDA Playground packages
- Spec-Driven Testbench Generation Agent for independent specification verification
"""

from verisight.uvm.uvm_architect import UVMArchitect, UVMGenerationResult
from verisight.agents.spec_driven_tb_agent import SpecDrivenTestbenchAgent

__all__ = ["UVMArchitect", "UVMGenerationResult", "SpecDrivenTestbenchAgent"]
