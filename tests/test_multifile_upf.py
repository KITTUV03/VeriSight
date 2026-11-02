"""
Comprehensive Test Suite for VeriSight:
1. Multi-File RTL Input & Dependency Resolution
2. Optional UPF Power-Intent Integration
3. Unified Project Architecture & Diagnostics
4. Backward Compatibility Verification
"""

import json
import pytest
from pathlib import Path

from verisight.schemas.upf_schema import (
    PowerDomain, SupplyPort, SupplyNet, SupplySet, PowerSwitch,
    IsolationStrategy, LevelShifterStrategy, RetentionStrategy,
    PowerState, PowerStateTable, DomainCrossing, UPFValidationIssue,
    UPFKnowledge,
)
from verisight.schemas.rtl_schema import RTLModule, RTLKnowledge
from verisight.parsers.rtl_parser import parse_rtl
from verisight.parsers.upf_parser import parse_upf
from verisight.orchestrator import VeriSightPipeline
from verisight.config import VeriSightConfig, LLMConfig, PipelineConfig
from verisight.server.app import create_app, SimRequest, ValidateProjectRequest


@pytest.fixture
def multi_file_rtl_project(tmp_path):
    """
    Creates a realistic 6-file SystemVerilog design:
    - i2c_pkg.sv (package)
    - i2c_interface.sv (interface)
    - apb_slave.sv (module)
    - i2c_fsm.sv (submodule importing package)
    - i2c_core.sv (submodule instantiating fsm)
    - top.sv (top-level instantiating apb_slave and i2c_core)
    """
    rtl_dir = tmp_path / "rtl"
    rtl_dir.mkdir()

    # 1. Package
    pkg_file = rtl_dir / "i2c_pkg.sv"
    pkg_file.write_text(
        "package i2c_pkg;\n"
        "  typedef enum logic [1:0] {\n"
        "    IDLE  = 2'b00,\n"
        "    START = 2'b01,\n"
        "    ADDR  = 2'b10,\n"
        "    DATA  = 2'b11\n"
        "  } i2c_state_t;\n"
        "  localparam int TIMEOUT_CYCLES = 100;\n"
        "endpackage\n"
    )

    # 2. Interface
    if_file = rtl_dir / "i2c_interface.sv"
    if_file.write_text(
        "interface i2c_interface (input logic clk, input logic rst_n);\n"
        "  logic scl;\n"
        "  logic sda;\n"
        "  modport master (input scl, inout sda);\n"
        "  modport slave (input scl, inout sda);\n"
        "endinterface\n"
    )

    # 3. APB Slave Leaf Module
    apb_file = rtl_dir / "apb_slave.sv"
    apb_file.write_text(
        "module apb_slave (\n"
        "  input  logic        pclk,\n"
        "  input  logic        presetn,\n"
        "  input  logic [31:0] paddr,\n"
        "  input  logic        psel,\n"
        "  input  logic        penable,\n"
        "  output logic [31:0] prdata,\n"
        "  output logic        pready\n"
        ");\n"
        "  always_ff @(posedge pclk or negedge presetn) begin\n"
        "    if (!presetn) begin\n"
        "      prdata <= 32'h0;\n"
        "      pready <= 1'b0;\n"
        "    end else begin\n"
        "      pready <= psel & penable;\n"
        "    end\n"
        "  end\n"
        "endmodule\n"
    )

    # 4. I2C FSM (Imports package)
    fsm_file = rtl_dir / "i2c_fsm.sv"
    fsm_file.write_text(
        "import i2c_pkg::*;\n"
        "module i2c_fsm (\n"
        "  input  logic clk,\n"
        "  input  logic rst_n,\n"
        "  input  logic start_cmd,\n"
        "  output logic busy\n"
        ");\n"
        "  i2c_state_t current_state;\n"
        "  always_ff @(posedge clk or negedge rst_n) begin\n"
        "    if (!rst_n) current_state <= IDLE;\n"
        "    else if (start_cmd) current_state <= START;\n"
        "  end\n"
        "  assign busy = (current_state != IDLE);\n"
        "endmodule\n"
    )

    # 5. I2C Core (Instantiates i2c_fsm)
    core_file = rtl_dir / "i2c_core.sv"
    core_file.write_text(
        "module i2c_core (\n"
        "  input  logic clk,\n"
        "  input  logic rst_n,\n"
        "  input  logic start_tx,\n"
        "  output logic tx_busy\n"
        ");\n"
        "  i2c_fsm u_fsm (\n"
        "    .clk(clk),\n"
        "    .rst_n(rst_n),\n"
        "    .start_cmd(start_tx),\n"
        "    .busy(tx_busy)\n"
        "  );\n"
        "endmodule\n"
    )

    # 6. Top Level Module (Instantiates apb_slave and i2c_core)
    top_file = rtl_dir / "top.sv"
    top_file.write_text(
        "module top (\n"
        "  input  logic        clk,\n"
        "  input  logic        rst_n,\n"
        "  input  logic [31:0] paddr,\n"
        "  input  logic        psel,\n"
        "  output logic [31:0] prdata,\n"
        "  output logic        busy\n"
        ");\n"
        "  logic apb_ready;\n"
        "  apb_slave u_apb (\n"
        "    .pclk(clk),\n"
        "    .presetn(rst_n),\n"
        "    .paddr(paddr),\n"
        "    .psel(psel),\n"
        "    .penable(1'b1),\n"
        "    .prdata(prdata),\n"
        "    .pready(apb_ready)\n"
        "  );\n"
        "  i2c_core u_i2c (\n"
        "    .clk(clk),\n"
        "    .rst_n(rst_n),\n"
        "    .start_tx(psel),\n"
        "    .tx_busy(busy)\n"
        "  );\n"
        "endmodule\n"
    )

    return {
        "dir": rtl_dir,
        "files": [pkg_file, if_file, apb_file, fsm_file, core_file, top_file],
        "top_file": top_file,
    }


@pytest.fixture
def valid_upf_file(tmp_path):
    """Creates a comprehensive IEEE 1801 UPF file correlated with the multi-file project."""
    upf_path = tmp_path / "design.upf"
    upf_path.write_text(
        "# IEEE 1801 UPF Power Intent for multi-file I2C/APB system\n"
        "create_power_domain PD_TOP -include_scope\n"
        "create_power_domain PD_I2C -elements {u_i2c/u_fsm}\n"
        "\n"
        "create_supply_port VDD -domain PD_TOP -direction in\n"
        "create_supply_port VDD_I2C -domain PD_I2C -direction in\n"
        "create_supply_port VSS -domain PD_TOP -direction in\n"
        "\n"
        "create_supply_net VDD -domain PD_TOP\n"
        "create_supply_net VDD_I2C -domain PD_I2C\n"
        "create_supply_net VSS -domain PD_TOP\n"
        "create_supply_net VSS -domain PD_I2C -reuse\n"
        "\n"
        "set_domain_supply_net PD_TOP -primary_power_net VDD -primary_ground_net VSS\n"
        "set_domain_supply_net PD_I2C -primary_power_net VDD_I2C -primary_ground_net VSS\n"
        "\n"
        "create_power_switch SW_I2C -domain PD_I2C \\\n"
        "  -input_supply_port {in VDD} \\\n"
        "  -output_supply_port {out VDD_I2C} \\\n"
        "  -control_port {ctrl pwr_ctrl} \\\n"
        "  -on_state {ON in {!ctrl}}\n"
        "\n"
        "set_isolation ISO_I2C -domain PD_I2C \\\n"
        "  -isolation_signal iso_en -isolation_sense high \\\n"
        "  -clamp_value 0 -applies_to outputs\n"
        "set_isolation_control ISO_I2C -domain PD_I2C \\\n"
        "  -isolation_signal iso_en -isolation_sense high\n"
        "\n"
        "set_level_shifter LS_I2C -domain PD_I2C -rule both -location self\n"
        "\n"
        "set_retention RET_I2C -domain PD_I2C \\\n"
        "  -retention_power_net VDD -retention_ground_net VSS\n"
        "set_retention_control RET_I2C -domain PD_I2C \\\n"
        "  -save_signal {save_en high} -restore_signal {restore_en high}\n"
        "\n"
        "add_power_state PD_TOP -state {ON -supply_expr {power == `{FULL_ON, 1.0} && ground == `{FULL_ON, 0.0}}}\n"
        "add_power_state PD_I2C -state {ON -supply_expr {power == `{FULL_ON, 1.0} && ground == `{FULL_ON, 0.0}}}\n"
        "add_power_state PD_I2C -state {OFF -supply_expr {power == `{OFF} && ground == `{FULL_ON, 0.0}}}\n"
        "\n"
        "create_pst pst_table -supplies {PD_TOP.primary.power PD_I2C.primary.power}\n"
        "add_pst_state ALL_ON -pst pst_table -state {ON ON}\n"
        "add_pst_state I2C_OFF -pst pst_table -state {ON OFF}\n"
    )
    return upf_path


# =============================================================================
# SCENARIO 1: Single RTL File Analysis
# =============================================================================
class TestScenario1SingleRTLFile:
    def test_single_file_parsing(self):
        """Upload one .sv file and parse successfully."""
        alu_path = Path("examples/rtl/alu.sv")
        assert alu_path.exists()

        k = parse_rtl(rtl_path=str(alu_path))
        assert k is not None
        assert any(m.name == "alu" for m in k.modules)
        assert k.top_module == "alu"
        assert len(k.file_list) == 1
        assert "alu.sv" in k.file_list[0]

    def test_single_file_pipeline_run(self, tmp_path):
        """Run full offline analysis pipeline on single RTL file."""
        alu_path = "examples/rtl/alu.sv"
        log_path = "examples/logs/sim.log"
        spec_path = "examples/specs/alu_spec.md"

        cfg = VeriSightConfig(
            llm=LLMConfig(airgap=True),
            pipeline=PipelineConfig(output_dir=str(tmp_path), save_intermediates=True),
        )
        pipe = VeriSightPipeline(config=cfg)
        rep = pipe.run(
            log_path=log_path,
            rtl_path=alu_path,
            spec_path=spec_path,
        )

        assert rep is not None
        assert rep.classification == "RTL Bug"
        assert pipe.knowledge.rtl is not None
        assert pipe.knowledge.upf is None  # UPF was not provided


# =============================================================================
# SCENARIO 2: Multiple RTL Files & Dependency Resolution
# =============================================================================
class TestScenario2MultipleRTLFiles:
    def test_multi_file_collection_and_hierarchy(self, multi_file_rtl_project):
        """Upload 6 individual files without merging and verify hierarchy resolution."""
        files = [str(f) for f in multi_file_rtl_project["files"]]
        assert len(files) == 6

        k = parse_rtl(rtl_files=files)

        # 1. Individual boundaries and files preserved
        assert len(k.file_list) == 6
        mod_names = {m.name for m in k.modules}
        assert "top" in mod_names
        assert "i2c_core" in mod_names
        assert "i2c_fsm" in mod_names
        assert "apb_slave" in mod_names
        assert "i2c_pkg" in k.packages
        assert "i2c_interface" in k.interfaces

        # 2. Package and interface attributes
        pkg_mod = next((m for m in k.modules if m.name == "i2c_pkg"), None)
        assert pkg_mod is not None and pkg_mod.is_package
        if_mod = next((m for m in k.modules if m.name == "i2c_interface"), None)
        assert if_mod is not None and if_mod.is_interface

        # 3. Top-level auto-detection
        assert k.top_module == "top"
        assert "top" in k.top_candidates

        # 4. Topological compilation order
        # Packages must come before modules importing them; leaf submodules before parent; top last.
        comp_names = [Path(p).name for p in k.compilation_order]
        assert "i2c_pkg.sv" in comp_names
        assert "top.sv" in comp_names
        assert comp_names.index("i2c_pkg.sv") < comp_names.index("i2c_fsm.sv")
        assert comp_names.index("i2c_fsm.sv") < comp_names.index("i2c_core.sv")
        assert comp_names.index("i2c_core.sv") < comp_names.index("top.sv")
        assert comp_names.index("apb_slave.sv") < comp_names.index("top.sv")

    def test_top_module_explicit_override(self, multi_file_rtl_project):
        """User overrides detected top-level module."""
        files = [str(f) for f in multi_file_rtl_project["files"]]
        k = parse_rtl(rtl_files=files, top_module="i2c_core")
        assert k.top_module == "i2c_core"

    def test_missing_dependency_detection(self, tmp_path):
        """Missing instantiations or imports are detected and reported."""
        orphan = tmp_path / "orphan.sv"
        orphan.write_text(
            "module orphan (\n"
            "  input logic clk\n"
            ");\n"
            "  missing_submod u_sub (.clk(clk));\n"
            "endmodule\n"
        )
        k = parse_rtl(rtl_files=[str(orphan)])
        assert any(d.get("required") == "missing_submod" for d in k.missing_dependencies)


# =============================================================================
# SCENARIO 3: Multiple RTL Files + Optional UPF Power Intent
# =============================================================================
class TestScenario3MultipleRTLFilesPlusUPF:
    def test_upf_parser_power_intent_extraction(self, multi_file_rtl_project, valid_upf_file):
        """Parse UPF and correlate with RTL hierarchy."""
        rtl_files = [str(f) for f in multi_file_rtl_project["files"]]
        rtl_k = parse_rtl(rtl_files=rtl_files)

        upf_k = parse_upf(upf_path=str(valid_upf_file), rtl_knowledge=rtl_k)

        # 1. Power Domains
        assert len(upf_k.power_domains) == 2
        domain_names = {pd.name for pd in upf_k.power_domains}
        assert "PD_TOP" in domain_names
        assert "PD_I2C" in domain_names

        # 2. Correlated Elements
        i2c_pd = next(pd for pd in upf_k.power_domains if pd.name == "PD_I2C")
        assert "u_i2c/u_fsm" in i2c_pd.elements

        # 3. Supply ports & switches
        assert len(upf_k.supply_ports) == 3
        assert len(upf_k.power_switches) == 1
        sw = upf_k.power_switches[0]
        assert sw.name == "SW_I2C"
        assert sw.domain == "PD_I2C"
        assert sw.on_state == "ON in {!ctrl}"

        # 4. Isolation & Retention
        assert len(upf_k.isolation_strategies) == 1
        iso = upf_k.isolation_strategies[0]
        assert iso.name == "ISO_I2C"
        assert iso.isolation_signal == "iso_en"
        assert iso.clamp_value == "0"

        assert len(upf_k.retention_strategies) == 1
        ret = upf_k.retention_strategies[0]
        assert ret.name == "RET_I2C"
        assert ret.save_signal == "save_en"
        assert ret.restore_signal == "restore_en"

        # 5. Power States & PST
        assert len(upf_k.power_states) == 3
        assert len(upf_k.power_state_tables) == 1
        pst = upf_k.power_state_tables[0]
        assert pst.name == "pst_table"
        assert len(pst.states) == 2

    def test_full_pipeline_with_rtl_and_upf(self, multi_file_rtl_project, valid_upf_file, tmp_path):
        """Execute end-to-end multi-agent pipeline with multi-file RTL + UPF."""
        rtl_files = [str(f) for f in multi_file_rtl_project["files"]]
        log_path = "examples/logs/sim.log"

        cfg = VeriSightConfig(
            llm=LLMConfig(airgap=True),
            pipeline=PipelineConfig(output_dir=str(tmp_path), save_intermediates=True),
        )
        pipe = VeriSightPipeline(config=cfg)

        rep = pipe.run(
            log_path=log_path,
            rtl_files=rtl_files,
            upf_path=str(valid_upf_file),
        )

        assert rep is not None
        # Agent 1 populated knowledge
        assert pipe.knowledge.upf is not None
        assert len(pipe.knowledge.upf.power_domains) == 2

        # Agent 3 analyzed power intent
        assert pipe.rtl_analysis is not None
        assert pipe.rtl_analysis.power_intent is not None
        assert len(pipe.rtl_analysis.power_intent.power_domains) == 2

        # Agent 4 generated report with Power-Aware section
        md_file = tmp_path / "report.md"
        html_file = tmp_path / "report.html"
        assert md_file.exists()
        assert html_file.exists()

        md_content = md_file.read_text(encoding="utf-8")
        assert "## Power-Aware Intent (UPF Analysis)" in md_content
        assert "PD_TOP" in md_content
        assert "PD_I2C" in md_content

        html_content = html_file.read_text(encoding="utf-8")
        assert "⚡ Power Intent (UPF)" in html_content
        assert "tab-upf" in html_content


# =============================================================================
# SCENARIO 4: RTL-Only Project (Multi-File without UPF)
# =============================================================================
class TestScenario4RTLOnlyMultiFileProject:
    def test_multi_file_without_upf(self, multi_file_rtl_project, tmp_path):
        """Verify that multi-file RTL project runs cleanly when UPF is omitted."""
        rtl_files = [str(f) for f in multi_file_rtl_project["files"]]
        log_path = "examples/logs/sim.log"

        cfg = VeriSightConfig(
            llm=LLMConfig(airgap=True),
            pipeline=PipelineConfig(output_dir=str(tmp_path)),
        )
        pipe = VeriSightPipeline(config=cfg)
        rep = pipe.run(
            log_path=log_path,
            rtl_files=rtl_files,
            upf_path=None,
        )

        assert rep is not None
        assert pipe.knowledge.upf is None
        assert pipe.rtl_analysis.power_intent is None

        # Standard reports still render cleanly
        md_content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "Power-Aware Intent Analysis" not in md_content


# =============================================================================
# SCENARIO 5: UPF Validation & Meaningful Diagnostics
# =============================================================================
class TestScenario5UPFValidation:
    def test_inconsistent_and_invalid_upf_diagnostics(self, multi_file_rtl_project, tmp_path):
        """Invalid hierarchy element, switchable domain without isolation, syntax error."""
        rtl_files = [str(f) for f in multi_file_rtl_project["files"]]
        rtl_k = parse_rtl(rtl_files=rtl_files)

        bad_upf = tmp_path / "bad.upf"
        bad_upf.write_text(
            "create_power_domain PD_TOP\n"
            "# Bad instance reference in RTL hierarchy\n"
            "create_power_domain PD_GHOST -elements {u_nonexistent/instance_xyz}\n"
            "# Power switch on PD_GHOST without any isolation strategy\n"
            "create_power_switch SW_GHOST -domain PD_GHOST -on_state {ON in {!ctrl}}\n"
            "# Unknown command\n"
            "invalid_upf_command_xyz --foobar\n"
        )

        upf_k = parse_upf(upf_path=str(bad_upf), rtl_knowledge=rtl_k)
        assert len(upf_k.validation_issues) > 0

        # Hierarchy mismatch diagnostic details
        ghost_issue = next((iss for iss in upf_k.validation_issues if "u_nonexistent" in iss.description), None)
        assert ghost_issue is not None
        assert ghost_issue.severity in ("warning", "error")
        assert "u_nonexistent" in ghost_issue.element


# =============================================================================
# SCENARIO 6: Backward Compatibility Verification
# =============================================================================
class TestScenario6BackwardCompatibility:
    def test_backward_compatible_sim_request_model(self):
        """Existing callers supplying only rtl_path and tb_path work without change."""
        req = SimRequest(
            rtl_path="examples/rtl/alu.sv",
            tb_path="examples/tb/alu_tb.sv",
        )
        assert req.rtl_path == "examples/rtl/alu.sv"
        assert req.rtl_files is None
        assert req.upf_path is None

    def test_project_validation_endpoint(self, multi_file_rtl_project, valid_upf_file):
        """Validate project structure and diagnostics via API endpoint."""
        from verisight.server.app import validate_project_core, ValidateProjectRequest
        files = [str(f) for f in multi_file_rtl_project["files"]]
        req = ValidateProjectRequest(
            rtl_files=files,
            upf_path=str(valid_upf_file),
        )
        data = validate_project_core(req)
        assert data["valid"] is True
        assert data["mode"] == "rtl_upf"
        assert data["top_module"] == "top"
        assert "PD_TOP" in data["power_domains"]
        assert "PD_I2C" in data["power_domains"]
