import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path("docs/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Colors (Catppuccin Mocha / GitHub Dark blend)
BG_COLOR = (24, 24, 37)         # #181825
HEADER_BG = (17, 17, 27)       # #11111b
BORDER_COLOR = (49, 50, 68)     # #313244
TEXT_WHITE = (205, 214, 244)   # #cdd6f4
TEXT_DIM = (108, 112, 134)     # #6c7086
COLOR_CYAN = (137, 220, 235)   # #89dceb
COLOR_GREEN = (166, 227, 161)  # #a6e3a1
COLOR_YELLOW = (249, 226, 175) # #f9e2af
COLOR_RED = (243, 139, 168)    # #f38ba8
COLOR_BLUE = (137, 180, 250)   # #89b4fa
COLOR_MAGENTA = (203, 166, 247)# #cba6f7

# Window dots
DOT_RED = (255, 95, 86)
DOT_YELLOW = (255, 189, 46)
DOT_GREEN = (39, 201, 63)

# Fonts
FONT_REG_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

font_reg = ImageFont.truetype(FONT_REG_PATH, 14)
font_bold = ImageFont.truetype(FONT_BOLD_PATH, 14)
font_title = ImageFont.truetype(FONT_BOLD_PATH, 12)

def render_terminal(title: str, lines: list, output_filename: str):
    """
    lines: list of tuples: ([(text, color, is_bold), ...])
    """
    line_height = 22
    pad_x = 24
    pad_top = 48  # header + margin
    pad_bottom = 24

    width = 980
    height = pad_top + len(lines) * line_height + pad_bottom

    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rectangle([0, 0, width - 1, height - 1], outline=BORDER_COLOR, width=1)

    # Title bar
    draw.rectangle([1, 1, width - 2, 36], fill=HEADER_BG)
    draw.line([1, 36, width - 2, 36], fill=BORDER_COLOR, width=1)

    # Window dots
    draw.ellipse([14, 13, 24, 23], fill=DOT_RED)
    draw.ellipse([32, 13, 42, 23], fill=DOT_YELLOW)
    draw.ellipse([50, 13, 60, 23], fill=DOT_GREEN)

    # Title text
    bbox = font_title.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 11), title, font=font_title, fill=TEXT_DIM)

    # Render lines
    y = pad_top
    for line_segments in lines:
        x = pad_x
        for seg in line_segments:
            text = seg[0]
            color = seg[1]
            is_bold = seg[2] if len(seg) > 2 else False
            f = font_bold if is_bold else font_reg
            draw.text((x, y), text, font=f, fill=color)
            seg_bbox = f.getbbox(text)
            seg_w = seg_bbox[2] - seg_bbox[0]
            x += seg_w
        y += line_height

    out_path = OUTPUT_DIR / output_filename
    img.save(out_path, dpi=(150, 150))
    print(f"Generated {out_path} ({width}x{height})")

print("Rendering screens...")

# Screen 1: Welcome & Main Menu
render_terminal(
    "Terminal — VeriSight Guided Wizard",
    [
        [("$ ./start.sh", COLOR_GREEN, True)],
        [("╔══════════════════════════════════════════════════════════════════════════════════╗", COLOR_CYAN, True)],
        [("║  🔍 VeriSight — Autonomous Verification & Debugging Platform                     ║", COLOR_CYAN, True)],
        [("║  Dual-Engine Autonomous Suite: VeriSight Debug & VeriSight Plan                 ║", TEXT_WHITE, True)],
        [("╚══════════════════════════════════════════════════════════════════════════════════╝", COLOR_CYAN, True)],
        [("Welcome! Select an autonomous workflow below to get started.", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("  [1] ", COLOR_YELLOW, True), ("🛠️  VeriSight Debug", COLOR_GREEN, True), ("  — Root-Cause Analysis & Fix for Sim Failures", TEXT_WHITE, False)],
        [("  [2] ", COLOR_YELLOW, True), ("📋 VeriSight Plan", COLOR_GREEN, True), ("   — Generate Test Plan, Coverage Model & SVA Suite", TEXT_WHITE, False)],
        [("  [3] ", COLOR_YELLOW, True), ("⚡ Quick Demos", COLOR_YELLOW, True), ("      — Instant 1-Click Run on ALU or FIFO", TEXT_WHITE, False)],
        [("  [4] ", COLOR_YELLOW, True), ("🚪 Exit", COLOR_RED, True), ("             — Terminate the VeriSight Session", TEXT_WHITE, False)],
        [("", TEXT_WHITE, False)],
        [("Select an option [1/2/3/4] (1): ", COLOR_YELLOW, True), ("1", COLOR_GREEN, True), (" █", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, True)]
    ],
    "screenshot_01_welcome_menu.png"
)

# Screen 2: LLM Configuration
render_terminal(
    "Terminal — VeriSight LLM Engine Setup",
    [
        [("Step 2: LLM Configuration", COLOR_CYAN, True)],
        [("╭────────────────── Detected LLM Environment ──────────────────╮", BORDER_COLOR, False)],
        [("│ Provider            │ Status                                  │", COLOR_CYAN, True)],
        [("├─────────────────────┼─────────────────────────────────────────┤", BORDER_COLOR, False)],
        [("│ Google Gemini       │ ", COLOR_CYAN, False), ("✓ Found in environment (AIza...9kL2)", COLOR_GREEN, True), ("   │", BORDER_COLOR, False)],
        [("│ Anthropic Claude    │ ", COLOR_CYAN, False), ("✓ Found in environment (sk-a...3mX1)", COLOR_GREEN, True), ("   │", BORDER_COLOR, False)],
        [("╰─────────────────────┴─────────────────────────────────────────╯", BORDER_COLOR, False)],
        [("", TEXT_WHITE, False)],
        [("Select LLM & API Key option:", TEXT_WHITE, True)],
        [("  1. Use detected Gemini API key (gemini-2.0-flash)", COLOR_CYAN, False)],
        [("  2. Use detected Claude API key (claude-sonnet-5)", COLOR_CYAN, False)],
        [("  3. Enter a new / custom Google Gemini API key", COLOR_CYAN, False)],
        [("  4. Enter a new / custom Anthropic Claude API key", COLOR_CYAN, False)],
        [("  5. Run in Offline / Deterministic Mode (no LLM, heuristic analysis)", COLOR_CYAN, False)],
        [("", TEXT_WHITE, False)],
        [("Your choice [1/2/3/4/5] (1): ", COLOR_YELLOW, True), ("1", COLOR_GREEN, True)],
        [("✓ Using Gemini API key.", COLOR_GREEN, True)]
    ],
    "screenshot_02_llm_config.png"
)

# Screen 3: Agent 1 Debug Inputs
render_terminal(
    "Terminal — VeriSight Debug: Input Gathering",
    [
        [("🛠️ VeriSight Debug — Autonomous Simulation RCA & Fix", COLOR_CYAN, True)],
        [("Analyze simulation logs, trace root cause, and generate automated code fixes.", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("Simulation Log file (.log) ", TEXT_WHITE, True), ("(Required): ", COLOR_RED, True), ("projects/fifo/logs/sim.log", COLOR_GREEN, False)],
        [("✓ Auto-matched file: sim.log", COLOR_GREEN, False)],
        [("RTL Source directory or file (.sv, .v) ", TEXT_WHITE, True), ("(Optional): ", TEXT_DIM, False), ("projects/fifo/rtl/", COLOR_GREEN, False)],
        [("✓ Discovered 2 RTL files in projects/fifo/rtl/", COLOR_GREEN, False)],
        [("UVM Testbench directory or file (.sv) ", TEXT_WHITE, True), ("(Optional): ", TEXT_DIM, False), ("projects/fifo/tb/", COLOR_GREEN, False)],
        [("✓ Discovered 3 TB files in projects/fifo/tb/", COLOR_GREEN, False)],
        [("Design Specification document (.md) ", TEXT_WHITE, True), ("(Optional): ", TEXT_DIM, False), ("projects/fifo/specs/spec.md", COLOR_GREEN, False)],
        [("Output directory for reports (output/custom_debug): ", COLOR_YELLOW, True), ("output/fifo_debug", COLOR_GREEN, False)],
        [("", TEXT_WHITE, False)],
        [("🚀 Launching VeriSight Debug Pipeline...", COLOR_CYAN, True)]
    ],
    "screenshot_03_agent1_debug_inputs.png"
)

# Screen 4: Agent 1 Debug Results & RCA
render_terminal(
    "Terminal — VeriSight Debug: Root-Cause Analysis & Fix",
    [
        [("[1/5] Parsing inputs (Log, RTL AST, UVM TB, Spec)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[2/5] Running Analyzer Suite (CDC, Lint, Protocol, Structure, XTracer)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[3/5] Querying ChromaDB Vector Knowledge Base for Historical Signoffs...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[4/5] Multi-Agent LLM Diagnostic Reasoning (Gemini-2.0-Flash)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[5/5] Generating Verifiable Patch & Corrected Snippet...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("══════════════════════════════════════════════════════════════════════════════", COLOR_GREEN, True)],
        [("🎉 Analysis Completed Successfully!", COLOR_GREEN, True)],
        [("══════════════════════════════════════════════════════════════════════════════", COLOR_GREEN, True)],
        [("  Classification:   ", TEXT_WHITE, True), ("RTL_BUG", COLOR_RED, True)],
        [("  Confidence:       ", TEXT_WHITE, True), ("95%", COLOR_GREEN, True)],
        [("  Root Cause:       ", TEXT_WHITE, True), ("Read pointer decrements improperly on empty condition causing underflow", COLOR_YELLOW, False)],
        [("  Category:         ", TEXT_WHITE, True), ("Sequential Logic Bug (Pointer Boundary)", TEXT_WHITE, False)],
        [("  Module:           ", TEXT_WHITE, True), ("fifo_mem.sv:L48", COLOR_CYAN, True)],
        [("", TEXT_WHITE, False)],
        [("  Generated Reports in output/fifo_debug/:", COLOR_CYAN, True)],
        [("    • ", COLOR_YELLOW, False), ("report.html", TEXT_WHITE, True), ("       (Visual interactive HTML diagnostic dashboard)", TEXT_DIM, False)],
        [("    • ", COLOR_YELLOW, False), ("report.md", TEXT_WHITE, True), ("         (Detailed engineering markdown report)", TEXT_DIM, False)],
        [("    • ", COLOR_YELLOW, False), ("error.json", TEXT_WHITE, True), ("        (Strict schema-validated JSON root-cause record)", TEXT_DIM, False)],
        [("    • ", COLOR_YELLOW, False), ("summary.txt", TEXT_WHITE, True), ("       (Concise executive summary for sign-off review)", TEXT_DIM, False)],
        [("    • ", COLOR_YELLOW, False), ("fix/proposed.patch", TEXT_WHITE, True), ("(Unified git patch directly applicable via git apply)", COLOR_GREEN, False)],
        [("", TEXT_WHITE, False)],
        [("Open the HTML report in your browser? [Y/n]: ", COLOR_YELLOW, True), ("Y", COLOR_GREEN, True)],
        [("✓ Opened: file:///home/mirafra_lp38/VeriSight/output/fifo_debug/report.html", COLOR_GREEN, False)]
    ],
    "screenshot_04_agent1_debug_results.png"
)

# Screen 5: Agent 2 Plan Inputs
render_terminal(
    "Terminal — VeriSight Plan: Input Gathering",
    [
        [("📋 VeriSight Plan — Verification & Architecture Plan", COLOR_CYAN, True)],
        [("Generate Test Plan, Feature Decomposition, SystemVerilog Coverage & SVA Suite.", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("Specification document file or directory (.md, .txt, .pdf) ", TEXT_WHITE, True), ("(Required): ", COLOR_RED, True), ("examples/specs/alu_spec.md", COLOR_GREEN, False)],
        [("✓ Found spec file: examples/specs/alu_spec.md", COLOR_GREEN, False)],
        [("RTL Source directory or file (.sv, .v) ", TEXT_WHITE, True), ("(Optional): ", TEXT_DIM, False), ("examples/rtl/", COLOR_GREEN, False)],
        [("✓ Discovered 1 RTL file: alu.sv", COLOR_GREEN, False)],
        [("Output directory for verification plan (output/verification_plan): ", COLOR_YELLOW, True), ("output/verification_plan", COLOR_GREEN, False)],
        [("", TEXT_WHITE, False)],
        [("🚀 Launching VeriSight Plan Architect...", COLOR_CYAN, True)]
    ],
    "screenshot_05_agent2_plan_inputs.png"
)

# Screen 6: Agent 2 Plan Results
render_terminal(
    "Terminal — VeriSight Plan: Generation Results",
    [
        [("[1/6] Ingesting Spec Document (Markdown / Text / Multi-page PDF)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[2/6] Parsing RTL Port Interface & FSM States (alu.sv)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[3/6] Synthesizing Hierarchical Feature Tree & Test Matrix...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[4/6] Generating SystemVerilog Functional Coverage Model (covergroup)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[5/6] Formulating SystemVerilog Assertions Suite (SVA Properties)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("[6/6] Computing Bi-Directional Traceability Matrix & HTML Dashboard...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("══════════════════════════════════════════════════════════════════════════════", COLOR_GREEN, True)],
        [("🎉 Verification Plan Generated Successfully!", COLOR_GREEN, True)],
        [("══════════════════════════════════════════════════════════════════════════════", COLOR_GREEN, True)],
        [("  Target Design:            ", TEXT_WHITE, True), ("ALU_Top (Arithmetic Logic Unit)", COLOR_CYAN, True)],
        [("  Decomposed Features:      ", TEXT_WHITE, True), ("8 verification functional units", COLOR_YELLOW, False)],
        [("  Defined Test Scenarios:   ", TEXT_WHITE, True), ("14 directed & constrained-random test cases", COLOR_GREEN, True)],
        [("  Coverage Points:          ", TEXT_WHITE, True), ("12 covergroups & cross coverage bins", COLOR_GREEN, True)],
        [("  SVA Formal Assertions:    ", TEXT_WHITE, True), ("10 temporal sequence & invariant properties", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("  Generated Artifacts in output/verification_plan/:", COLOR_CYAN, True)],
        [("    • ", COLOR_YELLOW, False), ("verification_plan.html", TEXT_WHITE, True), ("  (Interactive HTML Dashboard with Live Filtering)", TEXT_DIM, False)],
        [("    • ", COLOR_YELLOW, False), ("verification_plan.md", TEXT_WHITE, True), ("    (Engineering Markdown Plan for git repository)", TEXT_DIM, False)],
        [("    • ", COLOR_YELLOW, False), ("traceability_matrix.csv", TEXT_WHITE, True), (" (ISO 26262/DO-254 Certified Bi-directional Matrix)", COLOR_YELLOW, False)],
        [("    • ", COLOR_YELLOW, False), ("coverage_model.sv", TEXT_WHITE, True), ("      (Production-ready SystemVerilog Covergroups)", COLOR_GREEN, False)],
        [("    • ", COLOR_YELLOW, False), ("dut_assertions.sv", TEXT_WHITE, True), ("      (SystemVerilog Assertions Suite ready for TB bind)", COLOR_GREEN, False)],
        [("    • ", COLOR_YELLOW, False), ("verification_plan.json", TEXT_WHITE, True), ("  (Full Schema-Validated JSON Architecture)", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("Open the interactive HTML Verification Plan in your browser? [Y/n]: ", COLOR_YELLOW, True), ("Y", COLOR_GREEN, True)],
        [("✓ Opened: file:///home/mirafra_lp38/VeriSight/output/verification_plan/verification_plan.html", COLOR_GREEN, False)]
    ],
    "screenshot_06_agent2_plan_results.png"
)

# Screen 7: Option 3 Quick Demos
render_terminal(
    "Terminal — VeriSight Quick Demos Menu",
    [
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("Select an option [1/2/3/4] (1): ", COLOR_YELLOW, True), ("3", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("Step 2: LLM Configuration -> ✓ Using Gemini API key.", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("Select Pre-packaged Demo:", COLOR_CYAN, True)],
        [("  [1] ", COLOR_YELLOW, True), ("ALU Debug Demo", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, True), ("   (Detect Missing Reset Bug in Combinational Block)", TEXT_DIM, False)],
        [("  [2] ", COLOR_YELLOW, True), ("FIFO Debug Demo", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, True), ("  (Synchronous FIFO UVM Pointer Boundary Debug)", TEXT_DIM, False)],
        [("  [3] ", COLOR_YELLOW, True), ("ALU Plan Demo", COLOR_GREEN, True), ("    (Generate Full Test Plan, SV Coverage & SVA for ALU)", TEXT_WHITE, False)],
        [("  [4] ", COLOR_YELLOW, True), ("FIFO Plan Demo", COLOR_GREEN, True), ("   (Generate Full Test Plan, SV Coverage & SVA for FIFO)", TEXT_WHITE, False)],
        [("", TEXT_WHITE, False)],
        [("Your choice [1/2/3/4] (1): ", COLOR_YELLOW, True), ("3", COLOR_GREEN, True)],
        [("✓ Auto-configured inputs: spec=alu_spec.md, rtl=examples/rtl/", COLOR_GREEN, False)],
        [("🚀 Launching ALU Verification Plan Architect Demo...", COLOR_CYAN, True)]
    ],
    "screenshot_07_option3_demos.png"
)

# Screen 8: Option 4 Exit & CLI Power Mode
render_terminal(
    "Terminal — VeriSight Exit & CLI Direct Mode",
    [
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("Select an option [1/2/3/4] (1): ", COLOR_YELLOW, True), ("4", COLOR_RED, True)],
        [("Exiting VeriSight. Goodbye!", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("──────────────────────────────────────────────────────────────────────────────", BORDER_COLOR, False)],
        [("💡 VeriSight Advanced CLI Execution (Headless & CI/CD Mode):", COLOR_YELLOW, True)],
        [("──────────────────────────────────────────────────────────────────────────────", BORDER_COLOR, False)],
        [("# 1. Direct Debug Mode with full parameter overrides:", TEXT_DIM, False)],
        [("$ python main.py \\", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, False)],
        [("    --spec examples/specs/alu_spec.md \\", COLOR_CYAN, False)],
        [("    --rtl examples/rtl/ \\", COLOR_CYAN, False)],
        [("    --log examples/logs/sim.log \\", COLOR_CYAN, False)],
        [("    --output output/cli_debug_run", COLOR_CYAN, False)],
        [("", TEXT_WHITE, False)],
        [("# 2. Direct Verification Plan Synthesis Mode:", TEXT_DIM, False)],
        [("$ python main.py plan \\", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, False)],
        [("    --spec examples/specs/alu_spec.md \\", COLOR_CYAN, False)],
        [("    --rtl examples/rtl/ \\", COLOR_CYAN, False)],
        [("    --output output/verification_plan", COLOR_CYAN, False)],
        [("", TEXT_WHITE, False)],
        [("# 3. Quick Run via Shell wrapper:", TEXT_DIM, False)],
        [("$ ./start.sh", COLOR_GREEN, True)]
    ],
    "screenshot_08_cli_and_exit.png"
)

print("All screenshots generated successfully in docs/screenshots/!")
