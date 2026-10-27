"""
VeriSight UVM Architect Package.

Autonomous UVM Testbench Environment Generator inspired by XcelUVM:
- Generates complete, standards-compliant, cycle-accurate UVM 1.2 environments
- Interfaces, sequence items with constraints, driver, monitor, agent, scoreboard
- Reference models (SV behavioral), coverage subscribers, SVA assertions bind module
- Top-level testbench, package, Questa/VCS run scripts, and EDA Playground packages
"""

from verisight.uvm.uvm_architect import UVMArchitect, UVMGenerationResult

__all__ = ["UVMArchitect", "UVMGenerationResult"]
