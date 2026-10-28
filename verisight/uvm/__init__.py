"""
VeriSight UVM Architect Package.

Autonomous UVM Testbench Environment Generator inspired by XcelUVM:
- Generates complete, standards-compliant, cycle-accurate UVM 1.2 environments
- Interfaces, sequence items with constraints, driver, monitor, agent, scoreboard
- Reference models (SV behavioral), coverage subscribers, SVA assertions bind module
- Top-level testbench, package, Questa/VCS run scripts, and EDA Playground packages
- Spec-Driven Testbench Generation Agent for independent specification verification
- VerificationMatrixSynthesizer for 50+ unique testcases and exhaustive multi-covergroup models
"""

from verisight.uvm.uvm_architect import UVMArchitect, UVMGenerationResult
from verisight.uvm.matrix_synthesizer import VerificationMatrixSynthesizer

__all__ = [
    "UVMArchitect",
    "UVMGenerationResult",
    "VerificationMatrixSynthesizer",
    "SpecDrivenTestbenchAgent",
]


def __getattr__(name: str):
    if name == "SpecDrivenTestbenchAgent":
        from verisight.agents.spec_driven_tb_agent import SpecDrivenTestbenchAgent
        return SpecDrivenTestbenchAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
