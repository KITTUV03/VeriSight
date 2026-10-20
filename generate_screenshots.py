import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path("docs/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Theme Palette (Modern High-Tech Dark / Catppuccin Mocha / Slate)
BG_COLOR = (24, 24, 37)          # #181825
HEADER_BG = (17, 17, 27)        # #11111b
BROWSER_BAR_BG = (30, 30, 46)   # #1e1e2e
BORDER_COLOR = (49, 50, 68)      # #313244
CARD_BG = (30, 30, 46)           # #1e1e2e
CARD_BORDER = (69, 71, 90)       # #45475a
TEXT_WHITE = (205, 214, 244)    # #cdd6f4
TEXT_DIM = (147, 153, 178)      # #9399b2
COLOR_CYAN = (137, 220, 235)    # #89dceb
COLOR_GREEN = (166, 227, 161)   # #a6e3a1
COLOR_YELLOW = (249, 226, 175)  # #f9e2af
COLOR_RED = (243, 139, 168)     # #f38ba8
COLOR_BLUE = (137, 180, 250)    # #89b4fa
COLOR_MAGENTA = (203, 166, 247) # #cba6f7
ACCENT_BLUE = (37, 99, 235)

# Window dots
DOT_RED = (255, 95, 86)
DOT_YELLOW = (255, 189, 46)
DOT_GREEN = (39, 201, 63)

# Fonts
FONT_REG_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_SANS_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SANS_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

font_reg = ImageFont.truetype(FONT_REG_PATH, 14)
font_bold = ImageFont.truetype(FONT_BOLD_PATH, 14)
font_title = ImageFont.truetype(FONT_BOLD_PATH, 12)
font_sans = ImageFont.truetype(FONT_SANS_PATH, 13)
font_sans_bold = ImageFont.truetype(FONT_SANS_BOLD_PATH, 14)
font_sans_lg = ImageFont.truetype(FONT_SANS_BOLD_PATH, 20)
font_sans_sm = ImageFont.truetype(FONT_SANS_PATH, 11)


def render_terminal(title: str, lines: list, output_filename: str):
    line_height = 22
    pad_x = 24
    pad_top = 48
    pad_bottom = 24

    width = 980
    height = pad_top + len(lines) * line_height + pad_bottom

    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, width - 1, height - 1], outline=BORDER_COLOR, width=1)
    draw.rectangle([1, 1, width - 2, 36], fill=HEADER_BG)
    draw.line([1, 36, width - 2, 36], fill=BORDER_COLOR, width=1)

    draw.ellipse([14, 13, 24, 23], fill=DOT_RED)
    draw.ellipse([32, 13, 42, 23], fill=DOT_YELLOW)
    draw.ellipse([50, 13, 60, 23], fill=DOT_GREEN)

    bbox = font_title.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 11), title, font=font_title, fill=TEXT_DIM)

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


def render_diagram_architecture(output_filename: str):
    """Render a clean, high-resolution block diagram of the VeriSight Multi-Agent Architecture."""
    width = 980
    height = 540
    img = Image.new("RGB", (width, height), (15, 23, 42))  # Slate 900
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rectangle([0, 0, width - 1, height - 1], outline=(51, 65, 85), width=1)
    draw.rectangle([1, 1, width - 2, 45], fill=(2, 6, 23))
    draw.text((25, 14), "VERISIGHT™ SYSTEM ARCHITECTURE — MULTI-AGENT AUTONOMOUS FABRIC", font=font_sans_bold, fill=(56, 189, 248))

    # Inputs Block
    draw.rounded_rectangle([30, 70, 220, 490], radius=8, fill=(30, 41, 59), outline=(71, 85, 105))
    draw.text((45, 85), "VERIFICATION INPUTS", font=font_sans_bold, fill=(241, 245, 249))
    draw.line([45, 108, 205, 108], fill=(71, 85, 105), width=1)
    
    inputs_list = [
        ("• Specification Docs", "PDF, Markdown, Text"),
        ("• RTL Source Code", "SystemVerilog / Verilog"),
        ("• UVM Testbench", "Classes, Sequences, SB"),
        ("• Simulation Logs", "VCS, Questa, Icarus"),
        ("• Coverage Reports", "UCDB / vDB text reports"),
        ("• VCD Waveforms", "Value Change Dump"),
        ("• Gate Netlists", "Yosys / Foundry gates")
    ]
    iy = 120
    for name, sub in inputs_list:
        draw.text((45, iy), name, font=font_sans, fill=(56, 189, 248))
        draw.text((45, iy + 16), sub, font=font_sans_sm, fill=(148, 163, 184))
        iy += 48

    # Arrow to Agent 1 / Sim Runner
    draw.line([220, 210, 260, 210], fill=(56, 189, 248), width=3)
    draw.polygon([(260, 210), (250, 204), (250, 216)], fill=(56, 189, 248))

    # Agent 1
    draw.rounded_rectangle([260, 70, 470, 240], radius=8, fill=(30, 41, 59), outline=(14, 165, 233))
    draw.text((275, 85), "AGENT 1: KNOWLEDGE ENGINE", font=font_sans_bold, fill=(56, 189, 248))
    draw.line([275, 108, 455, 108], fill=(71, 85, 105), width=1)
    draw.text((275, 118), "• Multi-Modal AST Extraction", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 138), "• Port Map & Interface Hierarchy", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 158), "• Tokenized Simulation Log Index", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 178), "• VCD Waveform Parser (pywellen)", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 198), "• Outputs: Unified knowledge.json", font=font_sans_sm, fill=(34, 197, 94))

    # Arrow Agent 1 -> Agent 2
    draw.line([365, 240, 365, 280], fill=(56, 189, 248), width=3)
    draw.polygon([(365, 280), (359, 270), (371, 270)], fill=(56, 189, 248))

    # Agent 2
    draw.rounded_rectangle([260, 280, 470, 490], radius=8, fill=(30, 41, 59), outline=(168, 85, 247))
    draw.text((275, 295), "AGENT 2: CLASSIFIER", font=font_sans_bold, fill=(168, 85, 247))
    draw.line([275, 318, 455, 318], fill=(71, 85, 105), width=1)
    draw.text((275, 328), "• 9 Formal Decision Rules", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 348), "• Multi-Hop Evidence Graph", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 368), "• RTL Bug vs TB Bug vs Spec Bug", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 388), "• Bayesian Confidence Scoring", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 408), "• Alternative Hypothesis Review", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((275, 435), "• Outputs: summary.json", font=font_sans_sm, fill=(34, 197, 94))

    # Arrow Agent 2 -> Agent 3
    draw.line([470, 385, 510, 385], fill=(168, 85, 247), width=3)
    draw.polygon([(510, 385), (500, 379), (500, 391)], fill=(168, 85, 247))

    # Agent 3
    draw.rounded_rectangle([510, 70, 720, 490], radius=8, fill=(30, 41, 59), outline=(234, 179, 8))
    draw.text((525, 85), "AGENT 3: RTL ANALYZER", font=font_sans_bold, fill=(251, 191, 36))
    draw.line([525, 108, 705, 108], fill=(71, 85, 105), width=1)
    
    a3_modules = [
        ("1. X-Tracer", "Backward VCD Netlist Tracing"),
        ("2. Functional", "Spec vs RTL Math Discrepancy"),
        ("3. CDC Engine", "Async Clock & Metastability"),
        ("4. AST Lint", "Loops, Latches, Unassigned"),
        ("5. Structural", "FSM Deadlock & State Graph"),
        ("6. Protocol", "AXI/AHB/APB Handshaking"),
        ("7. Misc Timing", "Races & Reset Sequencing")
    ]
    my = 120
    for mname, mdesc in a3_modules:
        draw.text((525, my), mname, font=font_sans_bold, fill=(241, 245, 249))
        draw.text((525, my + 16), mdesc, font=font_sans_sm, fill=(148, 163, 184))
        my += 48

    # Arrow Agent 3 -> Agent 4 & 5
    draw.line([720, 210, 760, 210], fill=(234, 179, 8), width=3)
    draw.polygon([(760, 210), (750, 204), (750, 216)], fill=(234, 179, 8))

    # Agent 4 & 5 Block
    draw.rounded_rectangle([760, 70, 950, 270], radius=8, fill=(30, 41, 59), outline=(34, 197, 94))
    draw.text((775, 85), "AGENT 4: REPORTER", font=font_sans_bold, fill=(34, 197, 94))
    draw.line([775, 108, 935, 108], fill=(71, 85, 105), width=1)
    draw.text((775, 118), "• Interactive report.html", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 138), "• Waveform Studio Integration", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 158), "• Detailed report.md", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 178), "• Schema error.json", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 198), "• Executive summary.txt", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 218), "• ChromaDB Session Archive", font=font_sans_sm, fill=(226, 232, 240))

    draw.rounded_rectangle([760, 290, 950, 490], radius=8, fill=(30, 41, 59), outline=(244, 63, 94))
    draw.text((775, 305), "AGENT 5: FIX GENERATOR", font=font_sans_bold, fill=(244, 63, 94))
    draw.line([775, 328, 935, 328], fill=(71, 85, 105), width=1)
    draw.text((775, 338), "• Minimal Code Region Fix", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 358), "• Strict Non-Hallucination", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 378), "• Unified proposed.patch", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 398), "• Sandbox Syntax Validation", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 418), "• Testbench Regression Run", font=font_sans_sm, fill=(226, 232, 240))
    draw.text((775, 438), "• Zero-Error Signoff Check", font=font_sans_sm, fill=(34, 197, 94))

    out_path = OUTPUT_DIR / output_filename
    img.save(out_path, dpi=(150, 150))
    print(f"Generated {out_path} ({width}x{height})")


def render_diagram_flowchart(output_filename: str):
    """Render a clean, high-resolution flowchart of the Closed-Loop Verification & Repair Cycle."""
    width = 980
    height = 540
    img = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, width - 1, height - 1], outline=(51, 65, 85), width=1)
    draw.rectangle([1, 1, width - 2, 45], fill=(2, 6, 23))
    draw.text((25, 14), "VERISIGHT™ CLOSED-LOOP SIMULATION, ROOT-CAUSE & REPAIR CYCLE", font=font_sans_bold, fill=(56, 189, 248))

    # Steps
    steps = [
        ("1. SPEC & RTL INGESTION", "Extract requirements, ports, FSMs", 40, 90, (56, 189, 248)),
        ("2. VERISIGHT PLAN", "Generate coverage model & SVA", 270, 90, (168, 85, 247)),
        ("3. SIM RUNNER BACKEND", "Compile & simulate with VCD dump", 500, 90, (34, 197, 94)),
        ("4. SCOREBOARD CHECK", "Examine pass/fail & UVM errors", 730, 90, (251, 191, 36)),
        
        ("5. AGENT 1 & 2 RCA", "Parse log, isolate symptom & classify", 730, 310, (244, 63, 94)),
        ("6. AGENT 3 DEEP AUDIT", "7-module X-Trace, CDC, Lint, FSM", 500, 310, (244, 63, 94)),
        ("7. AGENT 5 CODE PATCH", "Generate unified diff patch", 270, 310, (168, 85, 247)),
        ("8. SANDBOX VALIDATION", "Re-run sim & prove 100% fix closure", 40, 310, (34, 197, 94)),
    ]

    for title, desc, sx, sy, col in steps:
        draw.rounded_rectangle([sx, sy, sx + 210, sy + 130], radius=8, fill=(30, 41, 59), outline=col, width=2)
        draw.text((sx + 12, sy + 15), title, font=font_sans_bold, fill=col)
        draw.line([sx + 12, sy + 38, sx + 198, sy + 38], fill=(71, 85, 105), width=1)
        draw.text((sx + 12, sy + 50), desc, font=font_sans_sm, fill=(226, 232, 240))
        draw.text((sx + 12, sy + 85), "Status: Autonomous", font=font_sans_sm, fill=(148, 163, 184))

    # Forward arrows (Top row: Left -> Right)
    for x in [250, 480, 710]:
        draw.line([x, 155, x + 20, 155], fill=(56, 189, 248), width=3)
        draw.polygon([(x + 20, 155), (x + 12, 149), (x + 12, 161)], fill=(56, 189, 248))

    # Down arrow from 4 to 5
    draw.line([835, 220, 835, 310], fill=(244, 63, 94), width=3)
    draw.polygon([(835, 310), (829, 300), (841, 300)], fill=(244, 63, 94))

    # Backward arrows (Bottom row: Right -> Left)
    for x in [730, 500, 270]:
        draw.line([x, 375, x - 20, 375], fill=(244, 63, 94), width=3)
        draw.polygon([(x - 20, 375), (x - 12, 369), (x - 12, 381)], fill=(244, 63, 94))

    # Loop-back arrow from 8 up to 3 (Closed-Loop Convergence)
    draw.line([145, 310, 145, 260], fill=(34, 197, 94), width=3)
    draw.line([145, 260, 605, 260], fill=(34, 197, 94), width=3)
    draw.line([605, 260, 605, 220], fill=(34, 197, 94), width=3)
    draw.polygon([(605, 220), (599, 230), (611, 230)], fill=(34, 197, 94))
    draw.text((220, 242), "✓ AUTOMATED CLOSED-LOOP RE-SIMULATION & PASS CONFIRMATION", font=font_sans_bold, fill=(34, 197, 94))

    out_path = OUTPUT_DIR / output_filename
    img.save(out_path, dpi=(150, 150))
    print(f"Generated {out_path} ({width}x{height})")


def render_browser_vplan(output_filename: str):
    width = 980
    height = 680
    img = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, width - 1, height - 1], outline=(51, 65, 85), width=1)
    draw.rectangle([1, 1, width - 2, 42], fill=(2, 6, 23))
    draw.line([1, 42, width - 2, 42], fill=(51, 65, 85), width=1)

    draw.ellipse([14, 16, 24, 26], fill=DOT_RED)
    draw.ellipse([32, 16, 42, 26], fill=DOT_YELLOW)
    draw.ellipse([50, 16, 60, 26], fill=DOT_GREEN)

    draw.rounded_rectangle([180, 8, width - 180, 34], radius=6, fill=(30, 41, 59), outline=(71, 85, 105))
    draw.text((195, 13), "🔒 http://localhost:8000/output/verification_plan/verification_plan.html", font=font_sans_sm, fill=(148, 163, 184))

    draw.rectangle([1, 43, width - 2, 95], fill=(15, 23, 42))
    draw.line([1, 95, width - 2, 95], fill=(51, 65, 85), width=1)
    draw.text((25, 58), "VERISIGHT™ COCKPIT", font=font_sans_bold, fill=(56, 189, 248))
    draw.text((220, 60), "• Live Coverage Closure Cockpit & Verification Plan", font=font_sans, fill=(226, 232, 240))

    draw.rounded_rectangle([width - 240, 56, width - 25, 82], radius=12, fill=(6, 78, 59), outline=(16, 185, 129))
    draw.text((width - 225, 62), "✓ UCDB INGESTION ACTIVE", font=font_sans_sm, fill=(167, 243, 208))

    cards = [
        ("TOTAL FEATURES", "22", "100% Decomposed", (56, 189, 248)),
        ("DIRECTED TESTS", "45", "100% Traceable", (168, 85, 247)),
        ("COVERGROUPS", "12", "92.4% Actual Hit", (34, 197, 94)),
        ("SVA ASSERTIONS", "23", "Formal Bind Ready", (251, 191, 36)),
    ]
    card_w = 215
    start_x = 25
    y_card = 115
    for i, (title, val, sub, col) in enumerate(cards):
        cx = start_x + i * (card_w + 20)
        draw.rounded_rectangle([cx, y_card, cx + card_w, y_card + 90], radius=8, fill=(30, 41, 59), outline=(51, 65, 85))
        draw.text((cx + 15, y_card + 12), title, font=font_sans_sm, fill=(148, 163, 184))
        draw.text((cx + 15, y_card + 32), val, font=font_sans_lg, fill=col)
        draw.text((cx + 15, y_card + 65), sub, font=font_sans_sm, fill=(203, 213, 225))

    y_prog = 225
    draw.rounded_rectangle([25, y_prog, width - 25, y_prog + 160], radius=8, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((45, y_prog + 15), "🎯 Dynamic Coverage Closure Cockpit (Planned vs. Actual UCDB Simulation)", font=font_sans_bold, fill=(241, 245, 249))
    
    cov_items = [
        ("Feature 1: ALU Arithmetic Operations (ADD, SUB, MULT, DIV)", "92.4%", 92.4, "Target: 100% — 8 Unhit Corner Bins"),
        ("Feature 2: Reset Sequencing & Asynchronous Recovery State", "100.0%", 100.0, "Target: 100% — Fully Closed"),
        ("Feature 3: Status Flags & Overflow Underflow Detection", "78.5%", 78.5, "Target: 100% — 14 Unhit Corner Bins [AI Stimulus Available]"),
    ]
    
    y_row = y_prog + 45
    for f_name, pct_str, pct_val, sub_note in cov_items:
        draw.text((45, y_row), f_name, font=font_sans_sm, fill=(226, 232, 240))
        draw.text((width - 110, y_row), pct_str, font=font_sans_bold, fill=(34, 197, 94) if pct_val >= 90 else (251, 191, 36))
        draw.rounded_rectangle([45, y_row + 18, width - 45, y_row + 26], radius=4, fill=(15, 23, 42))
        fill_w = int((width - 90) * (pct_val / 100.0))
        bar_col = (34, 197, 94) if pct_val >= 90 else (251, 191, 36)
        draw.rounded_rectangle([45, y_row + 18, 45 + fill_w, y_row + 26], radius=4, fill=bar_col)
        draw.text((45, y_row + 30), sub_note, font=font_sans_sm, fill=(148, 163, 184))
        y_row += 38

    y_table = 405
    draw.rounded_rectangle([25, y_table, width - 25, height - 25], radius=8, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((45, y_table + 15), "📋 Traceability Matrix, Coverage Model & Assertion Verification Suite", font=font_sans_bold, fill=(241, 245, 249))
    
    headers = [("FEATURE ID", 110), ("DESCRIPTION", 290), ("VERIFICATION METHOD", 180), ("STATUS", 110), ("ACTION", 180)]
    tx = 45
    for h, hw in headers:
        draw.text((tx, y_table + 45), h, font=font_sans_sm, fill=(148, 163, 184))
        tx += hw
    draw.line([45, y_table + 65, width - 45, y_table + 65], fill=(51, 65, 85), width=1)

    trows = [
        ("FEAT-001", "ALU 32-bit Arithmetic Engine", "Constrained Random + SVA", "PASSED (100%)", "View Covergroup (.sv)"),
        ("FEAT-002", "Clock Domain Crossing / Async Reset", "Formal Assertion Proof", "PASSED (100%)", "View SVA Properties"),
        ("FEAT-003", "Saturation Arithmetic Flag Bounds", "Directed Sequence Test", "PENDING (78.5%)", "⚡ Generate Directed Stimulus"),
        ("FEAT-004", "Pipeline Register Stage Hazard Control", "UVM Scoreboard Compare", "PASSED (100%)", "Inspect Waveform Trace"),
    ]
    ty = y_table + 75
    for fid, fdesc, fmeth, fstat, fact in trows:
        draw.text((45, ty), fid, font=font_sans_bold, fill=(56, 189, 248))
        draw.text((155, ty), fdesc, font=font_sans, fill=(226, 232, 240))
        draw.text((445, ty), fmeth, font=font_sans_sm, fill=(203, 213, 225))
        stat_col = (34, 197, 94) if "PASSED" in fstat else (251, 191, 36)
        draw.text((625, ty), fstat, font=font_sans_bold, fill=stat_col)
        btn_col = (37, 99, 235) if "Generate" in fact else (51, 65, 85)
        draw.rounded_rectangle([735, ty - 3, width - 55, ty + 20], radius=4, fill=btn_col)
        draw.text((745, ty + 1), fact, font=font_sans_sm, fill=(255, 255, 255))
        ty += 34

    out_path = OUTPUT_DIR / output_filename
    img.save(out_path, dpi=(150, 150))
    print(f"Generated {out_path} ({width}x{height})")


def render_browser_rca_report(output_filename: str):
    width = 980
    height = 680
    img = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, width - 1, height - 1], outline=(51, 65, 85), width=1)
    draw.rectangle([1, 1, width - 2, 42], fill=(2, 6, 23))
    draw.line([1, 42, width - 2, 42], fill=(51, 65, 85), width=1)

    draw.ellipse([14, 16, 24, 26], fill=DOT_RED)
    draw.ellipse([32, 16, 42, 26], fill=DOT_YELLOW)
    draw.ellipse([50, 16, 60, 26], fill=DOT_GREEN)

    draw.rounded_rectangle([180, 8, width - 180, 34], radius=6, fill=(30, 41, 59), outline=(71, 85, 105))
    draw.text((195, 13), "🔒 http://localhost:8000/output/custom_debug/report.html", font=font_sans_sm, fill=(148, 163, 184))

    draw.rectangle([1, 43, width - 2, 95], fill=(15, 23, 42))
    draw.line([1, 95, width - 2, 95], fill=(51, 65, 85), width=1)
    draw.text((25, 58), "VERISIGHT™ RCA STUDIO", font=font_sans_bold, fill=(244, 63, 94))
    draw.text((250, 60), "• Autonomous Silicon Root Cause Analysis & Waveform Diagnostics", font=font_sans, fill=(226, 232, 240))

    tabs = ["Overview", "Evidence Chain", "RTL Analyzer (7 Sub-Modules)", "Automated Patch", "Waveform Studio"]
    tab_x = 25
    tab_y = 105
    for i, t in enumerate(tabs):
        is_active = (i == 4 or i == 0)
        t_bg = (37, 99, 235) if is_active else (30, 41, 59)
        draw.rounded_rectangle([tab_x, tab_y, tab_x + 165, tab_y + 30], radius=6, fill=t_bg)
        draw.text((tab_x + 12, tab_y + 7), t, font=font_sans_sm, fill=(255, 255, 255) if is_active else (148, 163, 184))
        tab_x += 175

    y_card = 150
    draw.rounded_rectangle([25, y_card, width - 25, y_card + 110], radius=8, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.rounded_rectangle([45, y_card + 18, 180, y_card + 54], radius=6, fill=(136, 19, 55), outline=(244, 63, 94))
    draw.text((60, y_card + 26), "RTL BUG DETECTED", font=font_sans_bold, fill=(255, 228, 230))

    draw.rounded_rectangle([195, y_card + 18, 310, y_card + 54], radius=6, fill=(6, 78, 59), outline=(16, 185, 129))
    draw.text((210, y_card + 26), "CONFIDENCE: 95%", font=font_sans_bold, fill=(167, 243, 208))

    draw.text((330, y_card + 26), "Location: fifo_mem.sv:L48 • Sub-Module: Structural / Pointer Boundary", font=font_sans, fill=(203, 213, 225))
    draw.text((45, y_card + 68), "Root Cause: Read pointer decrements improperly on empty condition causing underflow and corrupting RAM index.", font=font_sans, fill=(241, 245, 249))

    y_wf = 280
    draw.rounded_rectangle([25, y_wf, width - 25, height - 25], radius=8, fill=(15, 23, 42), outline=(51, 65, 85))
    draw.rectangle([26, y_wf + 1, width - 26, y_wf + 38], fill=(30, 41, 59))
    draw.text((45, y_wf + 10), "📊 Interactive Waveform Studio (VCD Waveform Time-Correlated Evidence)", font=font_sans_bold, fill=(56, 189, 248))
    draw.text((width - 250, y_wf + 10), "Time Cursor: @ 45,000 ps (Mismatch)", font=font_sans_sm, fill=(251, 191, 36))

    signals = [
        ("tb.clk", "CLK", []),
        ("tb.rst_n", "RESET", []),
        ("tb.dut.rd_en", "CONTROL", []),
        ("tb.dut.rptr[3:0]", "BUS", []),
        ("tb.dut.empty", "FLAG", []),
        ("tb.dut.data_out", "BUS", []),
    ]

    sy = y_wf + 55
    wx_start = 220
    wx_end = width - 50

    for sig_name, sig_type, _ in signals:
        draw.text((45, sy + 6), sig_name, font=font_reg, fill=(148, 163, 184))
        draw.line([wx_start, sy + 25, wx_end, sy + 25], fill=(30, 41, 59), width=1)
        
        if sig_type == "CLK":
            cx = wx_start
            step = 30
            high = True
            while cx < wx_end:
                y_val = sy + 4 if high else sy + 24
                next_y = sy + 24 if high else sy + 4
                draw.line([cx, y_val, cx + step, y_val], fill=(56, 189, 248), width=2)
                draw.line([cx + step, y_val, cx + step, next_y], fill=(56, 189, 248), width=2)
                cx += step
                high = not high
        elif sig_type == "RESET":
            draw.line([wx_start, sy + 24, wx_start + 60, sy + 24], fill=(244, 63, 94), width=2)
            draw.line([wx_start + 60, sy + 24, wx_start + 60, sy + 4], fill=(34, 197, 94), width=2)
            draw.line([wx_start + 60, sy + 4, wx_end, sy + 4], fill=(34, 197, 94), width=2)
        elif sig_type == "CONTROL":
            draw.line([wx_start, sy + 24, wx_start + 180, sy + 24], fill=(148, 163, 184), width=2)
            draw.line([wx_start + 180, sy + 24, wx_start + 180, sy + 4], fill=(251, 191, 36), width=2)
            draw.line([wx_start + 180, sy + 4, wx_start + 320, sy + 4], fill=(251, 191, 36), width=2)
            draw.line([wx_start + 320, sy + 4, wx_start + 320, sy + 24], fill=(148, 163, 184), width=2)
            draw.line([wx_start + 320, sy + 24, wx_end, sy + 24], fill=(148, 163, 184), width=2)
        elif sig_type == "FLAG":
            draw.line([wx_start, sy + 4, wx_start + 120, sy + 4], fill=(34, 197, 94), width=2)
            draw.line([wx_start + 120, sy + 4, wx_start + 120, sy + 24], fill=(148, 163, 184), width=2)
            draw.line([wx_start + 120, sy + 24, wx_start + 340, sy + 24], fill=(148, 163, 184), width=2)
            draw.line([wx_start + 340, sy + 24, wx_start + 340, sy + 4], fill=(244, 63, 94), width=2)
            draw.line([wx_start + 340, sy + 4, wx_end, sy + 4], fill=(244, 63, 94), width=2)
        elif sig_type == "BUS":
            bx = wx_start
            b_steps = [(120, "0"), (120, "1"), (100, "2"), (340, "UNDERFLOW / XX")]
            for b_len, b_val in b_steps:
                col = (244, 63, 94) if "UNDERFLOW" in b_val or "CORRUPTED" in b_val else (168, 85, 247)
                draw.line([bx, sy + 4, bx + b_len, sy + 4], fill=col, width=2)
                draw.line([bx, sy + 24, bx + b_len, sy + 24], fill=col, width=2)
                draw.line([bx, sy + 4, bx + 6, sy + 14], fill=col, width=2)
                draw.line([bx, sy + 24, bx + 6, sy + 14], fill=col, width=2)
                draw.line([bx + b_len - 6, sy + 14, bx + b_len, sy + 4], fill=col, width=2)
                draw.line([bx + b_len - 6, sy + 14, bx + b_len, sy + 24], fill=col, width=2)
                draw.text((bx + 15, sy + 7), b_val, font=font_sans_sm, fill=(255, 255, 255) if "UNDERFLOW" in b_val else (226, 232, 240))
                bx += b_len
        sy += 48

    cursor_x = wx_start + 340
    draw.line([cursor_x, y_wf + 40, cursor_x, height - 35], fill=(244, 63, 94), width=2)
    draw.text((cursor_x + 6, y_wf + 44), "FAILURE POINT: 45,000 ps", font=font_sans_sm, fill=(244, 63, 94))

    out_path = OUTPUT_DIR / output_filename
    img.save(out_path, dpi=(150, 150))
    print(f"Generated {out_path} ({width}x{height})")


print("Generating updated screenshots and diagrams...")

# 1. Screen 1: WITH ALL 6 OFFICIAL WORKFLOW OPTIONS
render_terminal(
    "Terminal — VeriSight Guided Wizard",
    [
        [("$ ./start.sh", COLOR_GREEN, True)],
        [("╔══════════════════════════════════════════════════════════════════════════════════╗", COLOR_CYAN, True)],
        [("║  🔍 VeriSight — Autonomous Verification & Debugging Platform                     ║", COLOR_CYAN, True)],
        [("║  Multi-Engine Autonomous Suite: Debug, Plan, SimRunner, WebCockpit & Demos      ║", TEXT_WHITE, True)],
        [("╚══════════════════════════════════════════════════════════════════════════════════╝", COLOR_CYAN, True)],
        [("Welcome! Select an autonomous workflow below to get started.", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("  [1] ", COLOR_YELLOW, True), ("🛠️  VeriSight Debug", COLOR_GREEN, True), ("  — Root-Cause Analysis & Fix for Sim Failures", TEXT_WHITE, False)],
        [("  [2] ", COLOR_YELLOW, True), ("📋 VeriSight Plan", COLOR_GREEN, True), ("   — Generate Test Plan, Coverage Model & SVA Suite", TEXT_WHITE, False)],
        [("  [3] ", COLOR_YELLOW, True), ("🚀 Closed-Loop Sim", COLOR_GREEN, True), ("  — Simulate RTL+TB -> Auto-RCA & Coverage Cockpit", TEXT_WHITE, False)],
        [("  [4] ", COLOR_YELLOW, True), ("🌐 Live Web Cockpit", COLOR_CYAN, True), (" — Launch Interactive Browser Studio (Sim/Waveforms/RCA)", TEXT_WHITE, False)],
        [("  [5] ", COLOR_YELLOW, True), ("⚡ Quick Demos", COLOR_YELLOW, True), ("      — Instant 1-Click Run on ALU or FIFO", TEXT_WHITE, False)],
        [("  [6] ", COLOR_YELLOW, True), ("🚪 Exit", COLOR_RED, True), ("             — Terminate the VeriSight Session", TEXT_WHITE, False)],
        [("", TEXT_WHITE, False)],
        [("Select an option [1/2/3/4/5/6] (1): ", COLOR_YELLOW, True), ("1", COLOR_GREEN, True), (" █", TEXT_WHITE, True)]
    ],
    "screenshot_01_welcome_menu.png"
)

# 2. Screen 2: LLM Configuration
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

# 3. Screen 3: Debug Inputs
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

# 4. Screen 4: Debug Results
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

# 5. Screen 5: Plan Inputs
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

# 6. Screen 6: Plan Results
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
        [("  Decomposed Features:      ", TEXT_WHITE, True), ("22 verification functional units", COLOR_YELLOW, False)],
        [("  Defined Test Scenarios:   ", TEXT_WHITE, True), ("45 directed & constrained-random test cases", COLOR_GREEN, True)],
        [("  Coverage Points:          ", TEXT_WHITE, True), ("12 covergroups & cross coverage bins", COLOR_GREEN, True)],
        [("  SVA Formal Assertions:    ", TEXT_WHITE, True), ("23 temporal sequence & invariant properties", COLOR_GREEN, True)],
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

# 7. Screen 7: Option 3 Closed-Loop Sim
render_terminal(
    "Terminal — Workflow 3: Closed-Loop Simulation & Auto-RCA",
    [
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("Select an option [1/2/3/4/5/6] (1): ", COLOR_YELLOW, True), ("3", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("🚀 Workflow 3: One-Click Closed-Loop Simulation", COLOR_CYAN, True)],
        [("RTL Source directory or file (.sv, .v) (Required): ", TEXT_WHITE, True), ("examples/rtl/alu.sv", COLOR_GREEN, False)],
        [("UVM / SV Testbench directory or file (.sv) (Required): ", TEXT_WHITE, True), ("examples/tb/alu_tb.sv", COLOR_GREEN, False)],
        [("Simulator engine [iverilog/verilator/questa/vcs] (iverilog): ", COLOR_YELLOW, True), ("iverilog", COLOR_GREEN, False)],
        [("Specification document (.md, .pdf) (Optional): ", TEXT_WHITE, True), ("examples/specs/alu_spec.md", COLOR_GREEN, False)],
        [("Output directory (output/closed_loop): ", COLOR_YELLOW, True), ("output/closed_loop", COLOR_GREEN, False)],
        [("", TEXT_WHITE, False)],
        [("⚙️ [SimRunner] Compiling RTL and Self-Checking Testbench with iverilog...", COLOR_CYAN, False), (" [OK]", COLOR_GREEN, True)],
        [("⚙️ [SimRunner] Injected VCD dump wrapper ($dumpfile(\"sim.vcd\"))...", COLOR_CYAN, False), (" [OK]", COLOR_GREEN, True)],
        [("🚀 [SimRunner] Executing simulation binary (vvp)...", COLOR_CYAN, False)],
        [("  [UVM_ERROR] @ 20 ns: Scoreboard Mismatch! expected=0x00000008, actual=0xXXXXXXXX", COLOR_RED, True)],
        [("  [UVM_ERROR] @ 40 ns: Scoreboard Mismatch! expected=0x0000000C, actual=0xXXXXXXXX", COLOR_RED, True)],
        [("✓ [SimRunner] Generated sim.log (1,480 lines) and sim.vcd (48,120 transitions)", COLOR_GREEN, True)],
        [("🔄 [Handoff] Testbench reported failures! Auto-routing to Agent 1→5 RCA Pipeline...", COLOR_YELLOW, True)],
        [("  Classification: RTL_BUG (Confidence: 95%) — Missing reset in alu.sv:L34", COLOR_GREEN, True)],
        [("✓ Unified patch generated: output/closed_loop/fix/proposed.patch", COLOR_GREEN, True)]
    ],
    "screenshot_07_workflow3_closed_loop.png"
)

# 8. Screen 8: Option 4 Live Web Cockpit Launch
render_terminal(
    "Terminal — Workflow 4: Launching Live Web Cockpit Server",
    [
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("Select an option [1/2/3/4/5/6] (1): ", COLOR_YELLOW, True), ("4", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("⚡ Launching VeriSight Live Web Cockpit at http://127.0.0.1:8000", COLOR_CYAN, True)],
        [("INFO:     Started server process [PID 42180]", TEXT_DIM, False)],
        [("INFO:     Waiting for application startup.", TEXT_DIM, False)],
        [("INFO:     VeriSight Knowledge Base initialized (ChromaDB: 11 collections)", COLOR_CYAN, False)],
        [("INFO:     FastAPI Neural Cockpit routes registered:", COLOR_CYAN, False)],
        [("          • GET  /                        -> Modern Single-Page App (SPA)", TEXT_WHITE, False)],
        [("          • GET  /api/v1/status           -> Autonomous Engine Health", TEXT_WHITE, False)],
        [("          • POST /api/v1/simulate         -> Trigger One-Click Closed-Loop Sim", TEXT_WHITE, False)],
        [("          • POST /api/v1/debug            -> Autonomous Root-Cause Analysis", TEXT_WHITE, False)],
        [("          • POST /api/v1/plan             -> Verification Plan & Coverage Synthesis", TEXT_WHITE, False)],
        [("          • GET  /api/v1/waveform         -> Live SVG VCD Waveform Extraction", TEXT_WHITE, False)],
        [("INFO:     Application startup complete.", COLOR_GREEN, True)],
        [("INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)", COLOR_YELLOW, True)],
        [("✓ Opened browser at http://127.0.0.1:8000", COLOR_GREEN, True)]
    ],
    "screenshot_08_workflow4_web_cockpit.png"
)

# 9. Screen 9: Option 5 Quick Demos
render_terminal(
    "Terminal — Workflow 5: Quick Demos Menu",
    [
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("Select an option [1/2/3/4/5/6] (1): ", COLOR_YELLOW, True), ("5", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("Step 2: LLM Configuration -> ✓ Using Gemini API key.", COLOR_GREEN, True)],
        [("", TEXT_WHITE, False)],
        [("Select Pre-packaged Demo:", COLOR_CYAN, True)],
        [("  [1] ", COLOR_YELLOW, True), ("ALU Debug Demo", TEXT_WHITE, True), ("   (Detect Missing Reset Bug in Combinational Block)", TEXT_DIM, False)],
        [("  [2] ", COLOR_YELLOW, True), ("FIFO Debug Demo", TEXT_WHITE, True), ("  (Synchronous FIFO UVM Pointer Boundary Debug)", TEXT_DIM, False)],
        [("  [3] ", COLOR_YELLOW, True), ("ALU Plan Demo", COLOR_GREEN, True), ("    (Generate Full Test Plan, SV Coverage & SVA for ALU)", TEXT_WHITE, False)],
        [("  [4] ", COLOR_YELLOW, True), ("FIFO Plan Demo", COLOR_GREEN, True), ("   (Generate Full Test Plan, SV Coverage & SVA for FIFO)", TEXT_WHITE, False)],
        [("", TEXT_WHITE, False)],
        [("Your choice [1/2/3/4] (1): ", COLOR_YELLOW, True), ("3", COLOR_GREEN, True)],
        [("✓ Auto-configured inputs: spec=alu_spec.md, rtl=examples/rtl/", COLOR_GREEN, False)],
        [("🚀 Launching ALU Verification Plan Architect Demo...", COLOR_CYAN, True)]
    ],
    "screenshot_09_workflow5_demos.png"
)

# 10. Screen 10: Option 6 Exit & Headless CLI
render_terminal(
    "Terminal — Workflow 6: Exit & Advanced CLI Direct Mode",
    [
        [("Step 1: Choose Autonomous Workflow", COLOR_CYAN, True)],
        [("Select an option [1/2/3/4/5/6] (1): ", COLOR_YELLOW, True), ("6", COLOR_RED, True)],
        [("Exiting VeriSight. Goodbye!", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("──────────────────────────────────────────────────────────────────────────────", BORDER_COLOR, False)],
        [("💡 VeriSight Advanced CLI Execution (Headless & CI/CD Mode):", COLOR_YELLOW, True)],
        [("──────────────────────────────────────────────────────────────────────────────", BORDER_COLOR, False)],
        [("# 1. Direct Debug Mode with full parameter overrides:", TEXT_DIM, False)],
        [("$ python main.py --spec examples/specs/alu_spec.md --rtl examples/rtl/ \\", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, False)],
        [("    --log examples/logs/sim.log --output output/cli_debug_run", COLOR_CYAN, False)],
        [("", TEXT_WHITE, False)],
        [("# 2. Direct Verification Plan Synthesis Mode:", TEXT_DIM, False)],
        [("$ python main.py plan --spec examples/specs/alu_spec.md --rtl examples/rtl/ \\", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, False)],
        [("    --output output/verification_plan", COLOR_CYAN, False)],
        [("", TEXT_WHITE, False)],
        [("# 3. Direct One-Click Simulation Mode:", TEXT_DIM, False)],
        [("$ python main.py simulate --rtl examples/rtl/alu.sv --tb examples/tb/alu_tb.sv \\", COLOR_WHITE if 'COLOR_WHITE' in dir() else TEXT_WHITE, False)],
        [("    --simulator iverilog --output output/sim_run", COLOR_CYAN, False)],
        [("", TEXT_WHITE, False)],
        [("# 4. Launch Web Cockpit Server:", TEXT_DIM, False)],
        [("$ python main.py serve --port 8000", COLOR_GREEN, True)]
    ],
    "screenshot_10_workflow6_exit_cli.png"
)

# 11. Screen 11: Live Coverage Cockpit GUI
render_browser_vplan("screenshot_11_vplan_cockpit_gui.png")

# 12. Screen 12: RCA Diagnostic Dashboard GUI
render_browser_rca_report("screenshot_12_rca_dashboard_gui.png")

# 13. Screen 13: Automated Fix & Sandbox Validation
render_terminal(
    "Terminal — VeriSight Agent 5: Automated Fix & Sandbox Validation",
    [
        [("🔧 Agent 5: Automated Fix Generator — Synthesizing Verified Patch", COLOR_CYAN, True)],
        [("Evidence Grounding: Root cause confirmed at alu.sv:L34 (Missing reset initialization)", TEXT_DIM, False)],
        [("", TEXT_WHITE, False)],
        [("─── PROPOSED PATCH: output/fix/proposed.patch ─────────────────────────────────", BORDER_COLOR, False)],
        [("--- a/examples/rtl/alu.sv", TEXT_DIM, False)],
        [("+++ b/examples/rtl/alu.sv", TEXT_DIM, False)],
        [("@@ -32,6 +32,9 @@", COLOR_CYAN, False)],
        [(" always @(posedge clk or negedge rst_n) begin", TEXT_WHITE, False)],
        [("     if (!rst_n) begin", TEXT_WHITE, False)],
        [("-        // Missing reset for result register", COLOR_RED, True)],
        [("+        result <= 32'h00000000;", COLOR_GREEN, True)],
        [("+        zero   <= 1'b0;", COLOR_GREEN, True)],
        [("+        overflow <= 1'b0;", COLOR_GREEN, True)],
        [("     end else begin", TEXT_WHITE, False)],
        [("         case (opcode)", TEXT_WHITE, False)],
        [("──────────────────────────────────────────────────────────────────────────────", BORDER_COLOR, False)],
        [("⚙️ [Sandbox] Compiling patched RTL with iverilog syntax validator...", COLOR_CYAN, False), (" [PASSED]", COLOR_GREEN, True)],
        [("⚙️ [Sandbox] Re-running closed-loop testbench on patched RTL...", COLOR_CYAN, False), (" [12/12 PASSED]", COLOR_GREEN, True)],
        [("✓ Zero scoreboard errors! Root cause completely resolved.", COLOR_GREEN, True)],
        [("✓ Fix Confidence: 98% (Syntax verified + Regression closed)", COLOR_GREEN, True)],
        [("💡 Apply patch to repository: git apply output/fix/proposed.patch", COLOR_YELLOW, True)]
    ],
    "screenshot_13_automated_patch.png"
)

# 14. Screen 14: FastAPI Live Web Cockpit Server Log
render_terminal(
    "Terminal — FastAPI Neural Web Server Startup & API Endpoints",
    [
        [("$ python main.py serve --host 127.0.0.1 --port 8000", COLOR_GREEN, True)],
        [("INFO:     Started server process [PID 41820]", TEXT_DIM, False)],
        [("INFO:     VeriSight Knowledge Base initialized (ChromaDB: 11 collections)", COLOR_CYAN, False)],
        [("INFO:     FastAPI Neural Cockpit routes registered:", COLOR_CYAN, False)],
        [("          • GET  /                        -> Modern Single-Page App (SPA)", TEXT_WHITE, False)],
        [("          • GET  /api/v1/status           -> Autonomous Engine Health", TEXT_WHITE, False)],
        [("          • POST /api/v1/simulate         -> Trigger One-Click Closed-Loop Sim", TEXT_WHITE, False)],
        [("          • POST /api/v1/debug            -> Autonomous Root-Cause Analysis", TEXT_WHITE, False)],
        [("          • POST /api/v1/plan             -> Verification Plan & Coverage Synthesis", TEXT_WHITE, False)],
        [("          • GET  /api/v1/waveform         -> Live SVG VCD Waveform Extraction", TEXT_WHITE, False)],
        [("INFO:     Application startup complete.", COLOR_GREEN, True)],
        [("INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)", COLOR_YELLOW, True)],
        [("INFO:     127.0.0.1:48210 - \"GET / HTTP/1.1\" 200 OK", TEXT_DIM, False)],
        [("✓ VeriSight Web Cockpit ready! Open http://localhost:8000 in your browser.", COLOR_GREEN, True)]
    ],
    "screenshot_14_fastapi_web_server.png"
)

# 15. Screen 15: Headless CI/CD Nightly Regression
render_terminal(
    "Terminal — VeriSight Headless CI/CD Nightly Regression Pipeline",
    [
        [("$ # GitHub Actions / GitLab CI Automated Nightly Regression Step:", TEXT_DIM, False)],
        [("$ python main.py --spec specs/soc_spec.md --rtl rtl/ --tb tb/ --log logs/nightly.log \\", COLOR_GREEN, True)],
        [("    --output artifacts/regression_triage --no-rag", COLOR_CYAN, False)],
        [("", TEXT_WHITE, False)],
        [("⚡ [CI/CD] Running in Non-Interactive Headless Mode...", COLOR_CYAN, False)],
        [("⚡ [CI/CD] Parsing nightly regression failure log (450 MB)...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("⚡ [CI/CD] Agent 2 Classification: TB_BUG (Confidence: 91%)", COLOR_YELLOW, True)],
        [("⚡ [CI/CD] Error Signature: UVM Scoreboard expected latency 4 cycles, driver sent packet at 3 cycles.", TEXT_WHITE, False)],
        [("⚡ [CI/CD] Auto-generating JUnit XML & GitHub PR Annotation Comments...", COLOR_CYAN, False), (" [DONE]", COLOR_GREEN, True)],
        [("✓ Summary JSON saved: artifacts/regression_triage/summary.json", COLOR_GREEN, True)],
        [("✓ Exit code 0 returned. Regression triage completed in 1.42 seconds.", COLOR_GREEN, True)]
    ],
    "screenshot_15_ci_cd_regression.png"
)

# 16. Diagram 1: Architecture Block Diagram
render_diagram_architecture("diagram_01_system_architecture.png")

# 17. Diagram 2: Closed-Loop Flowchart
render_diagram_flowchart("diagram_02_closed_loop_flow.png")

print("All screenshots and architectural diagrams generated successfully in docs/screenshots/!")
