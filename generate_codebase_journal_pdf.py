#!/usr/bin/env python3
"""
VeriSight Master Codebase & Architecture Journal Generator (v2.4 Enterprise Edition)
Generates an exhaustive, beautifully styled technical journal PDF documenting:
- The entire VeriSight Tri-Engine workflow
- File-by-file comprehensive code explanations for all source files in verisight/
- Directory paths, actual code snippets, 'Why Written' rationales, and 'How It Works' mechanics
- Clean simple English explanations of all algorithms (AST X-Tracer, 9 Decision Rules,
  Spec-Driven UVM Synthesis, Dynamic Coverage Closure, and Sandbox Safety)
- Numbered two-pass canvas with running headers, footers, and page numbers.
"""

import os
import sys
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Suppress headers/footers on cover page
        if self._pageNumber > 1:
            # Header
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#064e3b")) # Deep Emerald
            self.drawString(54, 755, "VERISIGHT™ • COMPREHENSIVE CODEBASE & ARCHITECTURE JOURNAL")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b")) # Slate Muted
            self.drawRightString(558, 755, "Deep Code-Level Implementation Reference")
            
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.75)
            self.line(54, 747, 558, 747)
            
            # Footer
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.75)
            self.line(54, 45, 558, 45)
            
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(54, 32, "Mirafra Technologies • Confidential & Proprietary • v2.4 Enterprise Edition")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(558, 32, page_text)
            
        self.restoreState()


def build_codebase_journal_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Palette matching VeriSight Brand
    c_primary = colors.HexColor("#064e3b")      # Deep Emerald Green (#064e3b)
    c_accent = colors.HexColor("#0f766e")       # Deep Teal (#0f766e)
    c_dark = colors.HexColor("#0f172a")         # Slate Dark (#0f172a)
    c_body = colors.HexColor("#1e293b")         # Body Slate
    c_muted = colors.HexColor("#475569")        # Muted Slate
    c_code = colors.HexColor("#047857")         # Forest Green
    c_card_bg = colors.HexColor("#f8fafc")      # Light Slate BG
    c_card_border = colors.HexColor("#cbd5e1")  # Border Slate
    c_callout_bg = colors.HexColor("#f0fdf4")   # Mint Callout BG
    c_callout_border = colors.HexColor("#86efac")# Mint Border
    c_code_bg = colors.HexColor("#0f172a")      # Terminal Dark BG (#0f172a)

    title_style = ParagraphStyle(
        "JournalTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=28,
        textColor=c_primary,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        "JournalSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=c_muted,
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=c_body,
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=12,
        textColor=c_body,
        leftIndent=10,
        spaceAfter=3
    )

    path_badge_style = ParagraphStyle(
        "PathBadge",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=9,
        leading=12,
        textColor=c_code,
        spaceAfter=2
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=c_primary
    )

    code_block_style = ParagraphStyle(
        "CodeSnippet",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#e2e8f0"), # Code Light Text
        spaceAfter=2
    )

    story = []

    # =========================================================================
    # COVER / HEADER BANNER
    # =========================================================================
    story.append(Paragraph("VeriSight: Master Codebase & Architecture Journal", title_style))
    story.append(Paragraph(
        "<b>Comprehensive File-by-File Technical Guide with Real Implementation Code, Design Rationales & Execution Mechanics</b><br/>"
        "<i>System Architects: Patel Kittu & Vinod Nikhil Monterio • Mirafra Technologies • v2.4 Enterprise Edition</i>",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceBefore=0, spaceAfter=10))

    # Executive Summary Card
    exec_summary_p = Paragraph(
        "<b>Executive Codebase Overview:</b> This journal is a comprehensive, code-level reference for the VeriSight platform. "
        "Unlike high-level marketing overviews, this document inspects the <b>exact Python and SystemVerilog code implementations</b> "
        "written across the <code>verisight/</code> package. "
        "For every core file, it provides: (1) The exact directory path, (2) The actual code snippet written in that file, "
        "(3) <b>Why that code was written</b> (the specific engineering problem, failure mode, or hallucination risk it eliminates), "
        "and (4) <b>How it works</b> (the step-by-step execution flow during simulation triage, verification planning, or UVM synthesis).",
        body_style
    )
    exec_table = Table([[exec_summary_p]], colWidths=[504])
    exec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_callout_bg),
        ("BOX", (0, 0), (-1, -1), 1, c_callout_border),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(exec_table)
    story.append(Spacer(1, 10))

    # Helper function to add an in-depth code card
    def add_deep_file_card(file_path, role_badge, code_snippet, why_written, how_it_works, interactions=None):
        card_content = []
        
        # Path & Role Banner
        card_content.append(Paragraph(f"📁 <b>File Path:</b> <code>{file_path}</code>", path_badge_style))
        card_content.append(Paragraph(f"<b>System Role:</b> {role_badge}", meta_label_style))
        card_content.append(Spacer(1, 3))
        
        # Code Snippet Box (Terminal style)
        if code_snippet:
            clean_code = code_snippet.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>&nbsp;&nbsp;")
            snippet_p = Paragraph(f"<b>Core Implementation Code:</b><br/>&nbsp;&nbsp;{clean_code}", code_block_style)
            code_table = Table([[snippet_p]], colWidths=[492])
            code_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), c_code_bg),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#334155")),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            card_content.append(code_table)
            card_content.append(Spacer(1, 4))
            
        # Why We Wrote This Code
        card_content.append(Paragraph(f"<b>💡 Why We Wrote This Code:</b> {why_written}", body_style))
        
        # How It Works & Execution Logic
        card_content.append(Paragraph(f"<b>⚙️ How It Works & Logic:</b> {how_it_works}", body_style))
        
        # Interactions
        if interactions:
            card_content.append(Paragraph(f"<b>🔗 Inter-Module Dataflow:</b> {interactions}", bullet_style))
            
        table = Table([[card_content]], colWidths=[504])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_card_bg),
            ("BOX", (0, 0), (-1, -1), 0.75, c_card_border),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(KeepTogether([table, Spacer(1, 8)]))

    # =========================================================================
    # SUBSYSTEM 1: WIZARD LAUNCHER & ORCHESTRATION
    # =========================================================================
    story.append(Paragraph("1. User Experience, Wizard Launcher & Master Orchestration", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/wizard.py",
        "Interactive Terminal Launcher & 2x2 Tri-Engine Gateway",
        """# Pure Spec-Driven Mode Handling in VeriSight Plan:
if not rtl_path:
    # RTL is strictly optional: default is empty string so pressing Enter skips
    rtl_path = _prompt_path("RTL Source directory or file (.sv, .v)", required=False, default="")
...
summary_table.add_row("RTL Source", str(rtl_path) if rtl_path else "[bold green]None (Spec-Driven Planning)[/bold green]")""",
        "Previously, when users did not provide an RTL file, the wizard defaulted to examples/rtl/alu.sv, which caused the AI to hallucinate ALU logic into non-ALU specifications (such as I2C or FIFO). We rewrote this to enforce clean, pure spec-driven execution where RTL is optional, with a 2x2 interactive card interface displaying silicon hero badges.",
        "The wizard prompts the user for specifications and configuration parameters. When the user selects Engine 2 and hits Enter to skip RTL, it marks rtl_path as None and passes this flag downstream to the planner orchestrator, enabling true pre-RTL shift-left verification planning.",
        "Dispatches execution to verisight/orchestrator.py, verisight/plan/planner_orchestrator.py, or verisight/agents/spec_driven_tb_agent.py."
    )

    add_deep_file_card(
        "verisight/orchestrator.py",
        "Multi-Agent Cognitive Pipeline Orchestrator (Engine 1)",
        """class VeriSightOrchestrator:
    def run_pipeline(self, rtl_path, log_path, spec_path=None, vcd_path=None):
        knowledge = self.agent1.execute(rtl=rtl_path, log=log_path, spec=spec_path, vcd=vcd_path)
        classification = self.agent2.execute(knowledge=knowledge)
        rtl_analysis = self.agent3.execute(knowledge=knowledge, classification=classification)
        fix_result = self.agent5.execute(knowledge=knowledge, rtl_analysis=rtl_analysis)
        report = self.agent4.execute(knowledge=knowledge, classification=classification, fix=fix_result)
        return report""",
        "Prevents monolithic LLM failure. When a single prompt attempts log parsing, AST elaboration, classification, and code patching, models get confused and hallucinate non-existent hardware. We wrote this orchestrator to enforce strict separation of cognitive duties across 5 independent agents.",
        "Executes a linear, strongly-typed pipeline where each agent consumes validated Pydantic artifacts from the previous agent. If any agent encounters an LLM timeout, the orchestrator triggers graceful offline fallback to local deterministic rule engines.",
        "Sequences Agent 1 -> Agent 2 -> Agent 3 -> Agent 5 -> Agent 4."
    )

    add_deep_file_card(
        "verisight/config.py",
        "Multi-Provider Configuration & Air-Gap Model Resolver",
        """class VeriSightConfig(BaseModel):
    model_provider: str = Field(default="gemini") # gemini, claude, openai, ollama, vllm
    airgap_mode: bool = Field(default=False)
    local_endpoint: str = Field(default="http://localhost:11434")
    token_budget_per_run: int = Field(default=15000)""",
        "Enforces strict semiconductor confidentiality and vendor independence. Chip companies cannot send unmasked RTL to external clouds. This configuration allows zero-code switching between commercial cloud APIs and 100% on-premise air-gapped models.",
        "Loads .env variables, validates API keys with pre-flight probes, and routes agent requests to either cloud endpoints (Gemini/Claude) or local Ollama/vLLM endpoints (DeepSeek-Coder/Llama-3).",
        "Loaded by base_agent.py and all tools."
    )

    # =========================================================================
    # SUBSYSTEM 2: MULTI-AGENT INTELLIGENCE FABRIC (verisight/agents/)
    # =========================================================================
    story.append(Paragraph("2. The Specialized Multi-Agent Intelligence Fabric", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/agents/base_agent.py",
        "Abstract Base Agent with Schema Enforcement & Backoff",
        """class BaseAgent:
    def reason(self, prompt: str, system_prompt: str, output_model: Type[BaseModel]) -> BaseModel:
        # Enforces structured output parsing and exponential backoff retry
        for attempt in range(self.max_retries):
            raw_response = self._call_provider(prompt, system_prompt)
            validated = self._validate_and_parse(raw_response, output_model)
            if validated:
                return validated
        return self._fallback_deterministic(output_model)""",
        "Raw LLMs output conversational text that breaks downstream scripts. We wrote BaseAgent to guarantee that every single agent response strictly validates against a Pydantic schema, and that transient network glitches are automatically retried with exponential backoff.",
        "Wraps Google GenAI, Anthropic, and OpenAI SDKs. Parses JSON from raw LLM responses, strips markdown wrappers, validates against the target Pydantic schema, and falls back to deterministic rule evaluations if retries are exhausted.",
        "Inherited by all 6 agent classes in verisight/agents/."
    )

    add_deep_file_card(
        "verisight/agents/agent1_knowledge.py",
        "Agent 1: Knowledge Engine & Multi-Modal Collateral Ingestion",
        """class KnowledgeAgent(BaseAgent):
    def extract_knowledge(self, rtl_path, log_path, spec_path, vcd_path):
        ast_data = self.pyslang_parser.parse(rtl_path)
        log_errors = self.log_parser.tokenize(log_path)
        vcd_slice = self.vcd_parser.slice_window(vcd_path, window=20)
        return UnifiedKnowledge(ast=ast_data, logs=log_errors, waveform=vcd_slice)""",
        "Simulation failures involve disjoint files (logs, Verilog source, waveforms, specs). An engineer wastes hours correlating lines. Agent 1 bridges these media into a single coherent knowledge graph before any diagnosis begins.",
        "Invokes pyslang_rtl.py to elaborate the AST, log_parser.py to extract fatal error signatures, and vcd_parser.py to perform temporal window slicing (+/- 20 cycles), returning UnifiedKnowledge.",
        "Emits knowledge.json consumed by Agent 2."
    )

    add_deep_file_card(
        "verisight/agents/agent2_classifier.py",
        "Agent 2: 9-Rule Decision Engine & Evidence Calibrator",
        """class RootCauseClassifierAgent(BaseAgent):
    def _evaluate_rules(self, knowledge: UnifiedKnowledge) -> Classification:
        # Rule 1: Scoreboard Mismatch (DUT output != Reference output)
        # Rule 2: X-Propagation (4-state logic uninitialized flop)
        # Rule 3: Protocol Handshake Violation (SVA assertion failure)
        ...
        classification = self._verify_and_calibrate(classification, knowledge)
        return classification""",
        "Prevents ungrounded AI hallucination. We wrote this code to enforce a strict rule-based taxonomy: a failure cannot be declared an 'RTL Bug' unless physical evidence (AST lines, timestamps, waveform transitions) satisfies one of the 9 formal rules.",
        "Executes a deterministic pre-analysis, sends evidence to the LLM with strict instructions, and then runs _verify_and_calibrate() to cross-verify the LLM's citations against actual source files, penalizing confidence if any hallucinated identifier is detected.",
        "Emits summary.json consumed by Agents 3, 4, and 5."
    )

    add_deep_file_card(
        "verisight/agents/agent3_rtl_analyzer.py",
        "Agent 3: RTL Root Cause Analyzer & Logic Cone Tracing",
        """class RTLAnalyzerAgent(BaseAgent):
    def analyze_rtl(self, knowledge: UnifiedKnowledge, summary: Classification):
        x_origins = self.xtracer.find_uninitialized_regs(knowledge.ast)
        cone_signals = self.traceweave.backward_cone(target_signal, cycle=summary.fail_cycle)
        cdc_hazards = self.extended_checks.check_cdc(knowledge.ast)
        fsm_deadlocks = self._check_fsm_deadlocks(knowledge.ast)
        return RTLAnalysisReport(x_origins=x_origins, cone=cone_signals, cdc=cdc_hazards)""",
        "Identifies circuit-level defect mechanisms. Even after knowing a bug is in the RTL, isolating whether it is an uninitialized register, a clock-domain crossing race, or an FSM deadlock normally takes hours of waveform tracing.",
        "Executes the static X-Tracer to find reset-less flops, walks backward through the AST fan-in cone using WaveTrace, checks for missing 2-FF CDC synchronizers, and inspects FSM transition graphs for deadlocks.",
        "Emits rtl_analysis.json consumed by Agent 4 and Agent 5."
    )

    add_deep_file_card(
        "verisight/agents/agent4_reporter.py",
        "Agent 4: Interactive Dashboard & Report Compiler",
        """class ReporterAgent(BaseAgent):
    def generate_reports(self, knowledge, classification, rtl_analysis, fix_result):
        html_dashboard = self._build_interactive_html(classification, rtl_analysis, fix_result)
        markdown_report = self._compile_markdown_summary(classification, rtl_analysis)
        json_error = ErrorSchema(root_cause=classification.reason, patch=fix_result.patch)
        return ReportArtifacts(html=html_dashboard, md=markdown_report, json=json_error)""",
        "Transforms complex verification data into actionable executive and technical views. Eliminates manual reporting by providing synchronized waveform cursors and machine-readable JSON for CI/CD pipelines.",
        "Aggregates diagnostic data from all agents, embeds sub-cycle waveform timelines via waveform_studio.py, formats unified diff views, and writes report.html, report.md, and error.json.",
        "Final deliverable compiler; outputs to output/ directory."
    )

    add_deep_file_card(
        "verisight/agents/agent5_fix_generator.py",
        "Agent 5: Minimal Surgical Git Patch Synthesizer & Sandbox",
        """class FixGeneratorAgent(BaseAgent):
    def generate_fix(self, rtl_analysis: RTLAnalysisReport):
        # Enforces minimal code region patch (lines starting with - and +)
        diff_text = self._synthesize_patch_diff(rtl_analysis)
        # Verify syntax with pyslang before testing
        if not self.sv_validator.validate_syntax(diff_text):
            return FixResult(available=False, reason="Syntax check failed")
        # Validate in isolated /tmp sandbox simulation
        passed = self.sim_runner.run_sandbox_regression(diff_text)
        return FixResult(available=passed, patch=diff_text)""",
        "Prevents AI from generating broken or non-synthesizable code fixes. Many AI tools rewrite whole files, introducing new bugs. Agent 5 operates under a strict minimal-diff policy and tests every patch in a compilation sandbox before presenting it.",
        "Identifies the exact buggy lines, creates a minimal unified git diff, validates syntax via pyslang, copies design files to a temporary /tmp sandbox, and re-executes simulation to ensure the failing assertion passes without regression.",
        "Emits proposed.patch and updates fix_result consumed by Agent 4."
    )

    add_deep_file_card(
        "verisight/agents/spec_driven_tb_agent.py",
        "Engine 3: 10-Stage Spec-Driven UVM 1.2 Synthesis Agent",
        """class SpecDrivenTBAgent(BaseAgent):
    def generate_testbench(self, spec_path: str, rtl_path: str, output_dir: str):
        # Stage 1-2: Spec Ingestion & Grounding (Spec is the functional source of truth)
        spec_truth = self._extract_spec_truth(spec_path)
        # Stage 3-4: Interface Extraction via pyslang AST
        ports = self.pyslang.extract_ports(rtl_path)
        # Stage 5-8: Synthesize 14-Component UVM VIP Suite with Independent Golden Ref Model
        suite = self.uvm_architect.synthesize(spec_truth=spec_truth, ports=ports)
        # Stage 9-10: Pre-compile with pyslang & run dynamic simulation sign-off
        self.sv_validator.validate_suite(suite)
        return SpecDrivenTBResult(suite=suite)""",
        "Solves the 'AI testbench mirroring' flaw. When an AI reads buggy RTL to write a testbench, it copies the designer's bugs into the reference model, producing 100% false passes. This agent enforces the 'Spec-as-Truth' principle: the reference model is grounded strictly in the specification.",
        "Executes a structured 10-stage pipeline: ingests specs, maps RTL interfaces via pyslang AST, synthesizes 14 VIP components (including golden reference model and scoreboard comparator), checks IEEE-1800 syntax, and verifies simulation.",
        "Primary engine for Workflow 4 / Engine 3; uses verisight/uvm/uvm_architect.py."
    )

    # =========================================================================
    # SUBSYSTEM 3: ENGINE 2 — VERISIGHT PLAN (verisight/plan/)
    # =========================================================================
    story.append(Paragraph("3. Engine 2 Deep Dive: Scaled Verification Planning & Coverage", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/plan/planner_orchestrator.py",
        "Verification Plan Master Orchestrator (Spec-Driven Planning)",
        """class PlannerOrchestrator:
    def generate_verification_plan(self, spec_path, rtl_path=None, coverage_path=None):
        # Pure Spec-Driven Mode: RTL is optional
        spec_text = read_file(spec_path)
        features = self.feature_extractor.extract_features(spec_text, rtl_path=rtl_path)
        tests = self.test_planner.generate_tests(features) # Generates 50+ scaled tests
        covergroups = self.coverage_architect.build_coverage_model(features) # 90+ CPs
        assertions = self.assertion_architect.generate_assertions(features) # 30+ SVA
        return VerificationPlanReport(tests=tests, coverage=covergroups, sva=assertions)""",
        "Coordinates all planning modules into a cohesive flow. Enables pure spec-driven verification planning directly from PDF/Markdown datasheets before RTL coding even starts.",
        "Sequences Phase 1 (Feature Extraction), Phase 2 (50+ Test Scenario Formulation), Phase 3 (Coverage Model Synthesis), and Phase 4 (SVA Assertion Synthesis). Generates verification_plan.json and verification_plan.md.",
        "Coordinates feature_extractor.py, test_planner.py, coverage_architect.py, and assertion_architect.py."
    )

    add_deep_file_card(
        "verisight/plan/feature_extractor.py",
        "Multi-Modal Specification Feature Decomposer",
        """class FeatureExtractor:
    def extract_features(self, spec_text: str, rtl_path: Optional[str] = None):
        # Decomposes spec into atomic, verifiable items (e.g. REQ_001, REQ_002)
        sections = self._split_sections(spec_text)
        features = []
        for sec in sections:
            features.extend(self._extract_atomic_requirements(sec))
        return features""",
        "Eliminates ambiguity in specifications. Specifications are written in free-form English, making it hard to track what is verified. This code breaks specifications down into atomic, numbered functional requirements.",
        "Uses prompt engineering to parse sections, register maps, and operational modes, outputting normalized RequirementItem objects with unique IDs, categories, and verification priorities.",
        "Feeds extracted requirements to test_planner.py and coverage_architect.py."
    )

    add_deep_file_card(
        "verisight/plan/test_planner.py",
        "50+ Scaled Test Matrix Synthesizer (8 Functional Classes)",
        """class TestPlanner:
    CATEGORIES = [
        "directed", "constrained_random", "reset_initialization", "boundary_corner",
        "error_negative", "performance_backpressure", "concurrency_race", "protocol_specific"
    ]
    def generate_tests(self, features: List[RequirementItem]) -> List[TestCaseItem]:
        # Formulates at least 6-8 unique tests for each of the 8 categories -> 50+ tests
        tests = []
        for cat in self.CATEGORIES:
            tests.extend(self._synthesize_category_scenarios(features, category=cat))
        return tests""",
        "Solves the 'shallow test plan' problem. Earlier tools generated only 10 to 12 generic tests, missing corner cases. We wrote this code to enforce an 8-category verification matrix guaranteeing at least 50 unique, scaled test scenarios.",
        "Iterates across all 8 verification dimensions, prompting the LLM with category-specific constraints (e.g. inject bus parity errors for 'error_negative'; test FIFO simultaneous read/write for 'boundary_corner').",
        "Outputs test_plan.json and test_plan.md."
    )

    add_deep_file_card(
        "verisight/plan/coverage_architect.py",
        "Multi-Covergroup & Functional Coverage Model Synthesizer",
        """class CoverageArchitect:
    def build_coverage_model(self, features: List[RequirementItem]) -> CoveragePlan:
        # Synthesizes 90+ coverage points and 150+ bins
        cg_models = []
        for feat in features:
            cg = self._synthesize_covergroup(feat)
            cg.add_cross_coverage(feat.cross_signals)
            cg_models.append(cg)
        return CoveragePlan(covergroups=cg_models)""",
        "Translates requirements into measurable verification targets. Functional coverage ensures that tests actually exercise all protocol states, illegal values, and boundary conditions.",
        "Constructs SystemVerilog covergroups containing explicit bins for valid ranges, illegal bins, transition bins (e.g., IDLE => WRITE => READ => IDLE), and cross-coverage between control and data buses.",
        "Outputs coverage_model.sv and coverage_spec.json for integration into UVM subscribers."
    )

    add_deep_file_card(
        "verisight/plan/assertion_architect.py",
        "Formal SystemVerilog Assertion (SVA) Synthesizer",
        """class AssertionArchitect:
    def generate_assertions(self, features: List[RequirementItem]) -> List[AssertionItem]:
        # Synthesizes 30+ formal SVA concurrent assertions
        sva_list = []
        for feat in features:
            if feat.has_temporal_constraint:
                sva_list.append(self._create_sva_property(feat, op="|->", guard="!rst_n"))
        return sva_list""",
        "Bridges natural language timing requirements into executable formal checks. SVA assertions run continuously during simulation, immediately flagging protocol violations at the exact clock cycle they occur.",
        "Extracts timing constraints from specifications (e.g., 'TREADY must assert within 4 cycles of TVALID') and generates formal SVA properties using overlapping (|->) or non-overlapping (|=>) implication operators with reset guards.",
        "Outputs assertions.sv bindable to DUT module instances."
    )

    add_deep_file_card(
        "verisight/plan/coverage_ingest.py",
        "Simulator UCDB & vDB Coverage Database Ingester",
        """class CoverageIngest:
    def ingest_coverage(self, coverage_path: str):
        if coverage_path.endswith(".ucdb") or coverage_path.endswith(".xml"):
            return self._parse_questa_ucdb(coverage_path)
        elif coverage_path.endswith(".vdb") or "vdb" in coverage_path:
            return self._parse_vcs_vdb(coverage_path)
        return self._parse_generic_report(coverage_path)""",
        "Closes the loop between planned coverage and actual simulation results. Chip teams use different commercial simulators; this module provides a unified ingestion layer for coverage databases.",
        "Parses XML/text exports from Siemens Questa UCDB and Synopsys VCS vDB databases, extracting covergroup hierarchies and hit count statistics for every defined bin.",
        "Feeds actual simulator coverage data to coverage_correlator.py."
    )

    add_deep_file_card(
        "verisight/plan/coverage_correlator.py",
        "Dynamic Coverage Hole Analyzer & Directed Stimulus Generator",
        """class CoverageCorrelator:
    def find_holes_and_synthesize_stimulus(self, planned_model, actual_coverage):
        unhit_bins = self._extract_zero_hit_bins(planned_model, actual_coverage)
        directed_sequences = []
        for hole in unhit_bins:
            seq = self._synthesize_directed_uvm_sequence(hole)
            directed_sequences.append(seq)
        return CoverageClosureReport(unhit=unhit_bins, directed_sequences=directed_sequences)""",
        "Eliminates the multi-week 'coverage closure stall'. Teams often get stuck at 85% coverage because random seeds cannot hit rare corner-case states. This code automatically creates targeted stimulus for unhit bins.",
        "Subtracts actual hit bins from the planned coverage matrix to isolate unreached corner cases (e.g., concurrent read/write during FIFO almost-full), then generates constrained-random UVM sequences to hit them in days.",
        "Outputs directed_sequences.sv and coverage_closure.md."
    )

    add_deep_file_card(
        "verisight/plan/traceability.py",
        "ISO 26262 ASIL-D & DO-254 Traceability Matrix Exporter",
        """class TraceabilityMatrix:
    def build_matrix(self, features, tests, coverage, assertions):
        matrix_rows = []
        for f in features:
            row = {
                "req_id": f.id,
                "text": f.description,
                "tests": [t.id for t in tests if f.id in t.req_refs],
                "coverage": [c.name for c in coverage if f.id in c.req_refs],
                "sva": [a.name for a in assertions if f.id in a.req_refs]
            }
            matrix_rows.append(row)
        return self._export_csv_and_html(matrix_rows)""",
        "Guarantees compliance for automotive and safety-critical chips. Standards like ISO 26262 ASIL-D and DO-254 require proving that 100% of functional requirements have corresponding tests, assertions, and coverage points.",
        "Constructs a bidirectional requirement-to-verification matrix and exports audit-ready CSV (traceability_matrix.csv) and HTML reports, providing proof of verification completeness for safety audits.",
        "Generates compliance deliverables in output/verification_plan/."
    )

    # =========================================================================
    # SUBSYSTEM 4: ENGINE 3 — SPEC-DRIVEN UVM 1.2 SYNTHESIS (verisight/uvm/)
    # =========================================================================
    story.append(Paragraph("4. Engine 3 Deep Dive: Spec-Driven UVM 1.2 Synthesis", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/uvm/uvm_architect.py",
        "Complete 14-Component UVM 1.2 VIP Environment Synthesizer",
        """class UVMArchitect:
    VIP_FILES = [
        "_if.sv", "_seq_item.sv", "_sequencer.sv", "_driver.sv", "_monitor.sv",
        "_agent.sv", "_reference_model.sv", "_scoreboard.sv", "_coverage.sv",
        "_sequence.sv", "_env.sv", "_test.sv", "_pkg.sv", "_tb_top.sv"
    ]
    def synthesize_suite(self, spec_truth, rtl_ports, output_dir):
        for f_type in self.VIP_FILES:
            code = self._generate_component(f_type, spec_truth, rtl_ports)
            self._write_and_validate(output_dir, f_type, code)""",
        "Automates the most labor-intensive task in silicon verification. Writing a production UVM 1.2 testbench takes senior engineers 3 to 4 weeks. This code synthesizes a complete, standards-compliant 14-file UVM environment in seconds.",
        "Generates all 14 modular components. Critically, it constructs an independent behavioral Golden Reference Model (_reference_model.sv) and Scoreboard (_scoreboard.sv) connected via UVM analysis FIFOs to discover RTL bugs independently.",
        "Outputs 14 SystemVerilog UVM files to output/spec_driven_uvm/ or output/uvm_environment/."
    )

    add_deep_file_card(
        "verisight/uvm/matrix_synthesizer.py",
        "Protocol Matrix & Transaction Decomposer",
        """class MatrixSynthesizer:
    def derive_sequence_item(self, protocol_info, features):
        rand_fields = []
        constraints = []
        for field in protocol_info.payload_fields:
            rand_fields.append(f"rand logic [{field.width-1}:0] {field.name};")
            constraints.append(f"constraint c_{field.name} {{ {field.name} inside {[field.legal_ranges]}; }}")
        return self._format_seq_item(rand_fields, constraints)""",
        "Translates protocol specification parameters into synthesizable SystemVerilog transaction objects. Manually writing sequence items with proper rand variables and distribution constraints is tedious and prone to typos.",
        "Decomposes protocol timing parameters and address boundaries into SystemVerilog sequence item fields, generating pre/post_randomize hooks and UVM automation macros (`uvm_field_int).",
        "Used by uvm_architect.py to build _seq_item.sv and _driver.sv."
    )

    # =========================================================================
    # SUBSYSTEM 5: IEEE-1800 AST COMPILERS & PARSERS (verisight/parsers/)
    # =========================================================================
    story.append(Paragraph("5. IEEE-1800 AST Compilers, Parsers & Waveform Slicing", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/parsers/pyslang_rtl.py",
        "SystemVerilog IEEE-1800 Compiler & AST Elaborator",
        """def _build_always_block(proc: Any, sm: Any) -> Optional[AlwaysBlock]:
    pk = str(getattr(proc, "procedureKind", "")).split(".")[-1] # AlwaysFF, AlwaysComb
    events = _timing_events(proc) # Extract (edge, signal) e.g. (PosEdge, clk)
    written, read, nb_flags = _collect_assignments(proc)
    # Check if sequential block has a valid reset branch:
    has_reset = bool(reset) or bool(_RESET_IF_RE.search(raw_text))
    if pk == "AlwaysFF" and not has_reset:
        flag_uninitialized_flop_candidate(written)""",
        "Solves the limitation of text-based AI. Generic LLMs cannot understand hardware semantics. We wrote this code to interface directly with Slang, the fastest modern C++ SystemVerilog compiler frontend.",
        "Elaborates the real AST, extracts module port directions and bitwidths, identifies clock and reset sensitivity lists, and statically flags registers written in sequential blocks that lack a reset branch—pinpointing uninitialized 'X' bugs without simulation.",
        "Provides compiler AST models to Agent 1, Agent 3, and the X-Tracer tool."
    )

    add_deep_file_card(
        "verisight/parsers/vcd_parser.py",
        "Rust-Backed Temporal Waveform Slicer (+/- 20 Clock Cycles)",
        """class VCDParser:
    def slice_window(self, vcd_path: str, fail_timestamp: int, window_cycles: int = 20):
        # Uses pywellen / vcdvcd to extract only +/- 20 cycles around failure
        start_time = max(0, fail_timestamp - (window_cycles * clock_period))
        end_time = fail_timestamp + (window_cycles * clock_period)
        return self._extract_transitions(vcd_path, start_time, end_time)""",
        "Solves the 50GB waveform memory explosion. Real SoC simulation dumps are tens of gigabytes, which crash Python processes and cannot fit into LLM context windows.",
        "Uses fast C++/Rust bindings (pywellen) to perform targeted temporal slicing: it reads only the 20 clock cycles immediately surrounding the assertion failure timestamp, reducing gigabytes of trace data into a sub-megabyte JSON slice.",
        "Provides temporal signal state transitions to Agent 1, Agent 3, and the Waveform Studio."
    )

    add_deep_file_card(
        "verisight/parsers/log_parser.py",
        "Simulation Log Tokenizer & Error Pattern Classifier",
        """class LogParser:
    ERROR_PATTERNS = [
        re.compile(r"UVM_ERROR\s+([A-Z0-9_\/.]+)\((\d+)\)\s+@\s+(\d+)\s*:\s*(.*)"),
        re.compile(r"\*E,([A-Z0-9]+)\s+\(([^)]+),(\d+)\):\s*(.*)"), # Cadence Xcelium
        re.compile(r"%\s*Error:\s*(.*)") # Verilator
    ]
    def tokenize(self, log_path: str) -> LogData:
        # Extracts timestamps, source locations, and error messages
        ...""",
        "Normalizes incompatible simulator outputs. Synopsys VCS, Siemens Questa, Cadence Xcelium, and Verilator all print errors in completely different formats. This code unifies them into a single standard schema.",
        "Scans raw simulation logs with pre-compiled regex tokenizers, extracting assertion failure timestamps, scoreboard mismatch payloads, and file:line locations.",
        "Feeds normalized error signatures to Agent 1 and Agent 2."
    )

    # =========================================================================
    # SUBSYSTEM 6: HARDWARE TOOLS & SANDBOX (verisight/tools/)
    # =========================================================================
    story.append(Paragraph("6. Hardware Execution, Simulation Sandbox & Tools", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/tools/sim_runner.py",
        "Closed-Loop Multi-Simulator Sandbox Runner",
        """class SimRunner:
    def run_sandbox_regression(self, patch_diff: str, base_dir: Path) -> bool:
        # Create isolated temporary workspace in /tmp
        sandbox_dir = Path(tempfile.mkdtemp(prefix="verisight_sandbox_"))
        shutil.copytree(base_dir, sandbox_dir / "src")
        # Apply proposed patch inside sandbox
        self._apply_patch(sandbox_dir / "src", patch_diff)
        # Execute simulator (Verilator, Icarus, or VCS)
        success = self._run_simulator(sandbox_dir / "src")
        shutil.rmtree(sandbox_dir)
        return success""",
        "Enforces the ultimate safety guardrail. Never allow an AI to commit code directly to a hardware repository. If an AI generates an invalid patch, this sandbox catches it before human engineers ever see it.",
        "Clones the design repository into a temporary /tmp workspace, applies the candidate git patch, runs compilation and regression simulation, and returns True only if all tests pass with zero errors.",
        "Used by Agent 5 during automated fix validation."
    )

    add_deep_file_card(
        "verisight/tools/sv_validate.py",
        "Static IEEE-1800 Compiler Syntax Pre-Check Gateway",
        """class SVValidator:
    def validate_syntax(self, code_str: str) -> Tuple[bool, List[str]]:
        # Pre-compiles code through pyslang before writing to disk
        tree = pyslang.SyntaxTree.fromText(code_str)
        diags = [str(d) for d in tree.diagnostics if d.severity == pyslang.DiagnosticSeverity.Error]
        return (len(diags) == 0, diags)""",
        "Prevents syntax hallucinations. An AI might generate a fix or testbench that misses a semicolon, misuses a keyword, or violates SystemVerilog grammar. This code acts as a compiler gatekeeper.",
        "Feeds generated SystemVerilog code through pyslang's syntax tree parser. If diagnostics report errors, it returns the compiler diagnostic messages back to the agent so it can self-correct the code.",
        "Invoked by Agent 5 and Engine 3 before saving any file."
    )

    add_deep_file_card(
        "verisight/tools/xtracer_runner.py",
        "Static and Runtime X-Propagation Tracer Driver",
        """class XTracerRunner:
    def find_uninitialized_regs(self, ast_tree) -> List[str]:
        # Traverses AST always_ff nodes to find registers missing reset logic
        uninitialized = []
        for block in ast_tree.always_blocks:
            if block.is_sequential and not block.has_reset:
                uninitialized.extend(block.assigned_signals)
        return uninitialized""",
        "Isolates uninitialized flip-flop bugs that cause 4-state 'X' logic propagation. Tracing 'X' values manually in waveforms is one of the most tedious tasks in verification.",
        "Scans sequential AST blocks for missing reset branches and traces driving gates backward from the failing cycle to pinpoint the uninitialized flop.",
        "Used by Agent 3 during RTL root-cause analysis."
    )

    add_deep_file_card(
        "verisight/tools/eda_playground_exporter.py",
        "Cloud EDA Playground 1-Click Exporter",
        """class EDAPlaygroundExporter:
    def export(self, tb_dir: Path, rtl_dir: Path) -> str:
        # Bundles testbench, RTL, and run scripts into a single cloud package
        bundle = self._create_bundle(tb_dir, rtl_dir)
        share_url = self._upload_to_edaplayground(bundle)
        return share_url""",
        "Facilitates collaboration. Remote team members or clients may not have local VCS or Questa licenses installed. This allows engineers to share a working simulation with one click.",
        "Packages synthesized UVM testbenches, RTL source files, and run scripts into a clean bundle and generates a direct link to edaplayground.com.",
        "Invoked by `./start edaplayground`."
    )

    # =========================================================================
    # SUBSYSTEM 7: WEB STUDIO & VISUALIZATION (verisight/server/ & reporter/)
    # =========================================================================
    story.append(Paragraph("7. Live Web Studio, FastAPI Server & Waveform Telemetry", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/server/app.py",
        "FastAPI Asynchronous Web Studio & WebSocket Bridge",
        """app = FastAPI(title="VeriSight Web Studio")
@app.websocket("/ws/simulate")
async def websocket_simulation_stream(websocket: WebSocket):
    await websocket.accept()
    async for log_line in stream_simulator_output():
        await websocket.send_json({"type": "log_line", "data": log_line})""",
        "Provides an interactive, sub-millisecond web interface for verification engineers. Enables live regression monitoring and dynamic coverage tracking in a modern browser UI.",
        "Launches an asynchronous FastAPI server on port 8000 (via `./start serve`), streaming real-time simulation stdout over WebSockets and serving the Sage/Burgundy single-page dashboard.",
        "Backend server powering verisight/server/static/app.js."
    )

    add_deep_file_card(
        "verisight/reporter/waveform_studio.py",
        "Sub-Cycle Waveform Cursor Synchronizer",
        """class WaveformStudio:
    def synchronize_cursor(self, assertion_fail_time_ns: int):
        # Automatically positions inspection cursor at exact assertion timestamp
        return {
            "cursor_time": assertion_fail_time_ns,
            "highlight_signals": ["clk", "rst_n", "tvld", "trdy", "state"],
            "radix": "hex"
        }""",
        "Eliminates manual waveform searching. In tools like Verdi, an engineer must manually copy an assertion timestamp from a log file and search for it in a giant waveform viewer. This code automates that cursor alignment.",
        "Generates interactive canvas visualizers that automatically jump the inspection cursor to the exact nanosecond where the assertion tripped, decoding bus signals in binary, hex, and FSM state names.",
        "Embedded into report.html and the Live Web Studio."
    )

    # =========================================================================
    # SUBSYSTEM 8: SECURITY, AIR-GAP & MEMORY (verisight/utils/ & rag/)
    # =========================================================================
    story.append(Paragraph("8. Enterprise Security, Sovereign Air-Gap & Memory", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=2, spaceAfter=8))

    add_deep_file_card(
        "verisight/utils/airgap.py",
        "Sovereign Air-Gapped Network Enforcer & Local Model Gateway",
        """class AirGapManager:
    def enforce_airgap(self):
        # Disables external socket connections; validates local Ollama / vLLM
        os.environ["HTTP_PROXY"] = ""
        os.environ["HTTPS_PROXY"] = ""
        assert self._probe_localhost_endpoint("http://localhost:11434")""",
        "Guarantees that proprietary silicon IP never leaks to public cloud servers. Defense, aerospace, and semiconductor fabless companies require strict air-gapped on-premise execution.",
        "Blocks external network requests, redirects LLM calls to local Ollama or vLLM server instances running open-weights models (DeepSeek-Coder-V2, Llama-3-70B), and verifies zero outbound packet transmission.",
        "Activated by the `--airgap` flag or wizard Option 1."
    )

    add_deep_file_card(
        "verisight/utils/anonymizer.py",
        "Proprietary RTL & Specification Identifier Scrambler",
        """class Anonymizer:
    def anonymize_code(self, code_str: str) -> Tuple[str, Dict[str, str]]:
        # Scrambles proprietary signal names: mem_array -> sig_001, secret_key -> sig_002
        anonymized = code_str
        mapping = {}
        for ident in extract_identifiers(code_str):
            fake_name = f"sig_{uuid.uuid4().hex[:6]}"
            mapping[fake_name] = ident
            anonymized = anonymized.replace(ident, fake_name)
        return (anonymized, mapping)""",
        "Enables safe cloud LLM usage. If a customer chooses to use Google Gemini or Claude for maximum reasoning power, this code scrubs all proprietary names before the prompt leaves the machine.",
        "Replaces module names, signal identifiers, and comments with randomized tokens, sends the scrubbed code to the cloud API, and then maps the original names back locally into the response.",
        "Activated when cloud APIs are selected with anonymization enabled."
    )

    add_deep_file_card(
        "verisight/rag/knowledge_base.py",
        "ChromaDB 11-Collection Vector Memory Store",
        """class KnowledgeBase:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=".chroma_db")
        # 11 specialized collections: specs, registers, protocol_rules, past_bugs, etc.
        self.collections = [self.client.get_or_create_collection(c) for c in COLLECTIONS]""",
        "Acts as institutional memory for the verification team. When an engineer debugs a tricky FIFO bug on one block, other engineers shouldn't have to re-solve the same bug 3 months later on a different block.",
        "Stores tokenized failure signatures, specification paragraphs, and verified patches in 11 persistent vector collections, using semantic similarity search to instantly recall past solutions.",
        "Queried by Agent 1 and Agent 2 during triage."
    )

    # Build PDF
    print(f"Building VeriSight Codebase Master Journal PDF: {output_path}...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"SUCCESS: Generated {output_path} successfully!")

    # Mirror to Windows Downloads
    win_download = "/mnt/c/Users/MIRAFRA_LP38/Downloads/VeriSight_Codebase_Master_Journal.pdf"
    try:
        shutil.copyfile(output_path, win_download)
        print(f"SUCCESS: Copied to Windows Downloads: {win_download}")
    except Exception as e:
        print(f"Note: Could not copy to Windows Downloads: {e}")

if __name__ == "__main__":
    out_name = sys.argv[1] if len(sys.argv) > 1 else "VeriSight_Codebase_Master_Journal.pdf"
    build_codebase_journal_pdf(out_name)
