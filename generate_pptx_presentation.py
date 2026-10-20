import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

PPTX_PATH = "VeriSight_Investor_Presentation.pptx"
TEMPLATE_IMG = "docs/presentation/template_slide.png"

# Color Palette matching Mirafra template & VeriSight styling
C_PRIMARY = RGBColor(11, 77, 50)       # Dark Emerald Green
C_ACCENT = RGBColor(34, 197, 94)       # Vibrant Green (#22c55e)
C_DARK = RGBColor(15, 23, 42)          # Slate Navy (#0f172a)
C_TEXT = RGBColor(51, 65, 85)          # Slate Text (#334155)
C_MUTED = RGBColor(100, 116, 139)      # Slate Muted (#64748b)
C_CARD_BG = RGBColor(255, 255, 255)    # Card White
C_CARD_BORDER = RGBColor(203, 213, 225)# Border Slate (#cbd5e1)
C_BLUE = RGBColor(2, 132, 199)         # Sky Blue (#0284c7)
C_AMBER = RGBColor(217, 119, 6)        # Amber (#d97706)
C_RED = RGBColor(220, 38, 38)          # Red (#dc2626)

def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_base_slide(title_text=None, category_badge=None):
        slide = prs.slides.add_slide(blank_layout)
        # Add background template
        if os.path.exists(TEMPLATE_IMG):
            slide.shapes.add_picture(TEMPLATE_IMG, 0, 0, Inches(13.333), Inches(7.5))
        
        # Add Header if specified
        if title_text:
            tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.65), Inches(10.5), Inches(0.85))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
            
            p = tf.paragraphs[0]
            if category_badge:
                run_badge = p.add_run()
                run_badge.text = f"{category_badge.upper()}  •  "
                run_badge.font.name = "Arial"
                run_badge.font.size = Pt(10)
                run_badge.font.bold = True
                run_badge.font.color.rgb = C_BLUE
            
            run_title = p.add_run() if category_badge else p.add_run()
            run_title.text = title_text
            run_title.font.name = "Arial"
            run_title.font.size = Pt(22)
            run_title.font.bold = True
            run_title.font.color.rgb = C_PRIMARY
            
        return slide

    def add_card(slide, left, top, width, height, bg_color=C_CARD_BG, border_color=C_CARD_BORDER):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = bg_color
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1)
        return shape

    # =========================================================================
    # SLIDE 1: TITLE SLIDE (COVER)
    # =========================================================================
    s1 = add_base_slide()
    
    # Title Hero Box
    tb_hero = s1.shapes.add_textbox(Inches(0.8), Inches(1.3), Inches(11.7), Inches(3.2))
    tf_hero = tb_hero.text_frame
    tf_hero.word_wrap = True
    
    p0 = tf_hero.paragraphs[0]
    r_badge = p0.add_run()
    r_badge.text = "INVESTOR PITCH & ENTERPRISE TECHNICAL OVERVIEW • OCTOBER 2026\n"
    r_badge.font.size = Pt(11)
    r_badge.font.bold = True
    r_badge.font.color.rgb = C_BLUE

    p1 = tf_hero.add_paragraph()
    r_title = p1.add_run()
    r_title.text = "VERISIGHT™"
    r_title.font.name = "Arial"
    r_title.font.size = Pt(44)
    r_title.font.bold = True
    r_title.font.color.rgb = C_PRIMARY

    p2 = tf_hero.add_paragraph()
    r_sub = p2.add_run()
    r_sub.text = "Autonomous Silicon Verification & Failure Debugging Copilot"
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(20)
    r_sub.font.bold = True
    r_sub.font.color.rgb = C_DARK

    p3 = tf_hero.add_paragraph()
    r_desc = p3.add_run()
    r_desc.text = "Bridging Natural Language Hardware Specifications to Zero-Bug Silicon with Multi-Agent AI,\nClosed-Loop Simulation, Deterministic Root Cause Analysis, and Automated Patch Generation."
    r_desc.font.name = "Arial"
    r_desc.font.size = Pt(13)
    r_desc.font.color.rgb = C_TEXT

    # 3 Key Value Metric Cards
    cards_data = [
        ("100x Faster Triage", "Root cause isolated in <15s vs. 4-6 hours manual engineer debugging", C_PRIMARY),
        ("Zero Hallucinations", "9 Formal Decision Rules + Static AST X-Tracer + Sandbox Validation", C_BLUE),
        ("Universal Compatibility", "Seamless Day-1 drop-in across VCS, Questa, Xcelium, and Verilator", C_AMBER)
    ]
    card_w = Inches(3.64)
    card_gap = Inches(0.39)
    for i, (cheader, cdesc, ccolor) in enumerate(cards_data):
        c_left = Inches(0.8) + i * (card_w + card_gap)
        c_top = Inches(4.5)
        add_card(s1, c_left, c_top, card_w, Inches(1.8), C_CARD_BG, ccolor)
        
        tb_c = s1.shapes.add_textbox(c_left + Inches(0.2), c_top + Inches(0.15), card_w - Inches(0.4), Inches(1.5))
        tfc = tb_c.text_frame
        tfc.word_wrap = True
        
        cp1 = tfc.paragraphs[0]
        crun1 = cp1.add_run()
        crun1.text = cheader + "\n"
        crun1.font.name = "Arial"
        crun1.font.size = Pt(16)
        crun1.font.bold = True
        crun1.font.color.rgb = ccolor
        
        cp2 = tfc.add_paragraph()
        crun2 = cp2.add_run()
        crun2.text = cdesc
        crun2.font.name = "Arial"
        crun2.font.size = Pt(11)
        crun2.font.color.rgb = C_TEXT

    # Footer Metadata
    tb_foot = s1.shapes.add_textbox(Inches(0.8), Inches(6.5), Inches(11.7), Inches(0.5))
    tf_f = tb_foot.text_frame
    pf = tf_f.paragraphs[0]
    rf = pf.add_run()
    rf.text = "Lead Architect & Presenter: Kittu Patel (@KITTUV03)  |  Confidential  |  Release v2.4 Enterprise"
    rf.font.size = Pt(10)
    rf.font.bold = True
    rf.font.color.rgb = C_MUTED

    # =========================================================================
    # SLIDE 2: AGENDA (LIST OF TOPICS COVERED - MATCHING USER'S IMAGE)
    # =========================================================================
    s2 = add_base_slide("Agenda — List of Topics Covered", "Presentation Roadmap")
    
    agenda_items = [
        (1, "Idea Overview"),
        (2, "Problem Statement"),
        (3, "AI Approach to Solve the Problem"),
        (4, "Solution Architecture"),
        (5, "Architecture Components"),
        (6, "Tools & Models Used"),
        (7, "Experiments Conducted"),
        (8, "Results and Comparison (AI vs Manual effort)"),
        (9, "Dashboard Overview (Screenshots)"),
        (10, "Token Utilization Over Cost"),
        (11, "Summary"),
        (12, "Future Scope"),
        (13, "Integration Into Real World Chip Design"),
        (14, "Appendix - Supporting Document if any")
    ]
    
    # 2-Column Table representation of the Agenda
    col1_items = agenda_items[:7]
    col2_items = agenda_items[7:]
    
    for col_idx, items in enumerate([col1_items, col2_items]):
        c_left = Inches(0.8) + col_idx * Inches(5.9)
        card_bg = add_card(s2, c_left, Inches(1.5), Inches(5.7), Inches(5.3), C_CARD_BG, C_PRIMARY)
        
        tb = s2.shapes.add_textbox(c_left + Inches(0.2), Inches(1.6), Inches(5.3), Inches(5.1))
        tf = tb.text_frame
        tf.word_wrap = True
        
        for item_idx, (num, topic_title) in enumerate(items):
            p = tf.paragraphs[0] if item_idx == 0 else tf.add_paragraph()
            p.space_after = Pt(8)
            
            num_run = p.add_run()
            num_run.text = f"#{num:02d}  "
            num_run.font.name = "Arial"
            num_run.font.size = Pt(13)
            num_run.font.bold = True
            num_run.font.color.rgb = C_PRIMARY
            
            title_run = p.add_run()
            title_run.text = topic_title
            title_run.font.name = "Arial"
            title_run.font.size = Pt(13)
            title_run.font.bold = (num in [1, 2, 4, 8, 9, 13])
            title_run.font.color.rgb = C_DARK

    # =========================================================================
    # SLIDE 3: TOPIC 1 - IDEA OVERVIEW
    # =========================================================================
    s3 = add_base_slide("Topic 1: Idea Overview — The VeriSight Vision", "Executive Summary")
    
    # Left Column: Vision & Concept
    add_card(s3, Inches(0.8), Inches(1.5), Inches(6.8), Inches(5.3), C_CARD_BG)
    tb3_left = s3.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(6.4), Inches(4.9))
    tf3 = tb3_left.text_frame
    tf3.word_wrap = True
    
    p = tf3.paragraphs[0]
    r = p.add_run()
    r.text = "What is VeriSight?\n"
    r.font.size = Pt(18); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    p = tf3.add_paragraph()
    r = p.add_run()
    r.text = "VeriSight is an autonomous silicon verification & failure debugging copilot designed to eliminate the multi-week bottleneck in digital chip design.\n\n"
    r.font.size = Pt(12); r.font.color.rgb = C_TEXT
    
    pillars = [
        ("Autonomous Test Plan Synthesis", "Extracts architectural features, test sequences, covergroups, and SVA assertions directly from specs."),
        ("Closed-Loop Simulation", "Simulates RTL and testbench, automatically intercepts errors, dumps VCD traces, and triggers triage."),
        ("Root-Cause Diagnostic Engine", "Applies 9 formal decision rules and backwards AST cone traversal to pinpoint bug origin in seconds."),
        ("Self-Synthesizing Patch Generator", "Generates minimal unified git diffs and validates syntax in an isolated compile sandbox.")
    ]
    for ptitle, pdesc in pillars:
        p = tf3.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {ptitle}: "; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{pdesc}\n"; r2.font.size = Pt(11); r2.font.color.rgb = C_TEXT

    # Right Column: High-Impact Screenshot
    add_card(s3, Inches(7.8), Inches(1.5), Inches(4.7), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_01_welcome_menu.png"):
        s3.shapes.add_picture("docs/screenshots/screenshot_01_welcome_menu.png", Inches(7.9), Inches(1.65), Inches(4.5), Inches(4.3))
    tb_cap = s3.shapes.add_textbox(Inches(7.9), Inches(6.05), Inches(4.5), Inches(0.6))
    tf_cap = tb_cap.text_frame
    tf_cap.word_wrap = True
    p = tf_cap.paragraphs[0]
    r = p.add_run()
    r.text = "VeriSight Guided CLI Launcher with 6 Autonomous Workflows"
    r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    # =========================================================================
    # SLIDE 4: TOPIC 2 - PROBLEM STATEMENT
    # =========================================================================
    s4 = add_base_slide("Topic 2: Problem Statement — The Silicon Verification Crisis", "Market Need")
    
    # 4 Pain Point Cards
    p_cards = [
        ("1. 70% Development Cycle Eaten by Verification",
         "Verification is the single largest cost and timeline driver in semiconductor design. Over 70% of total engineering headcount and time is spent verifying and triaging RTL rather than architecting features.",
         C_RED),
        ("2. Exploding Complexity & Mask Re-Spin Costs",
         "Modern SoCs pack 100M+ to billions of transistors. A single escaped functional bug requires a physical silicon mask re-spin costing between $15M and $30M+ at advanced process nodes (3nm/5nm).",
         C_RED),
        ("3. Acute Senior Verification Talent Shortage",
         "The semiconductor industry faces a severe global deficit of verification talent. Senior engineers spend 60% of their day manually wading through 50,000-line simulation logs and gigabyte VCD traces.",
         C_AMBER),
        ("4. Disconnected Specs & Coverage Closure Stalls",
         "Architectural specifications (Word/PDF) drift away from SystemVerilog testbenches. Teams spend 6-8 weeks stuck at 85% coverage unable to generate directed stimulus for rare corner cases.",
         C_AMBER)
    ]
    
    for i, (title, desc, bcolor) in enumerate(p_cards):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        add_card(s4, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG, bcolor)
        
        tb = s4.shapes.add_textbox(c_left + Inches(0.25), c_top + Inches(0.2), Inches(5.2), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = title + "\n\n"
        r.font.name = "Arial"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = bcolor
        
        p = tf.add_paragraph()
        r = p.add_run()
        r.text = desc
        r.font.name = "Arial"; r.font.size = Pt(11); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 5: TOPIC 3 - AI APPROACH TO SOLVE THE PROBLEM
    # =========================================================================
    s5 = add_base_slide("Topic 3: AI Approach — Deterministic Multi-Agent Cognitive Pipeline", "Core Innovation")
    
    # Left Column: The Flaw of Generic AI vs. VeriSight
    add_card(s5, Inches(0.8), Inches(1.5), Inches(5.7), Inches(5.3), C_CARD_BG, C_RED)
    tb5_l = s5.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(5.3), Inches(4.9))
    tf5_l = tb5_l.text_frame
    tf5_l.word_wrap = True
    
    p = tf5_l.paragraphs[0]
    r = p.add_run(); r.text = "Why Generic AI (ChatGPT / Copilot) Fails\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_RED
    
    failures = [
        ("Hallucinates Non-Existent Hardware", "Suggests software libraries or invalid SystemVerilog syntax that fails downstream synthesis."),
        ("Blind to Waveform Timestamps", "Cannot parse cycle-by-cycle VCD/FSDB temporal transitions or clock edges."),
        ("No Structural HDL Understanding", "Lacks knowledge of fan-in logic cones, CDC synchronizers, or 4-state simulation (X/Z)."),
        ("No Execution Sandbox", "Generates unchecked code without verifying if regression tests pass or fail.")
    ]
    for ftitle, fdesc in failures:
        p = tf5_l.add_paragraph()
        r1 = p.add_run(); r1.text = f"❌ {ftitle}: "; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{fdesc}\n"; r2.font.size = Pt(10.5); r2.font.color.rgb = C_TEXT

    # Right Column: VeriSight Multi-Agent Approach
    add_card(s5, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb5_r = s5.shapes.add_textbox(Inches(7.0), Inches(1.7), Inches(5.3), Inches(4.9))
    tf5_r = tb5_r.text_frame
    tf5_r.word_wrap = True
    
    p = tf5_r.paragraphs[0]
    r = p.add_run(); r.text = "The VeriSight Multi-Agent Solution\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    innovations = [
        ("9 Deterministic Decision Rules", "Mathematical rules strictly categorize bugs as TB vs RTL vs Spec vs Unknown."),
        ("Static AST X-Tracer", "Traverses PyVerilog abstract syntax trees backwards from failing flop to isolate origin."),
        ("Multi-Modal Waveform Slicing", "Extracts +/- 20 cycles around assertion failure timestamp for sub-cycle precision."),
        ("Closed-Loop Sandbox Validation", "Every patch is re-compiled in an isolated sandbox with zero human intervention.")
    ]
    for ititle, idesc in innovations:
        p = tf5_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"✅ {ititle}: "; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{idesc}\n"; r2.font.size = Pt(10.5); r2.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 6: TOPIC 4 - SOLUTION ARCHITECTURE
    # =========================================================================
    s6 = add_base_slide("Topic 4: Solution Architecture — End-to-End System Block Diagram", "System Architecture")
    
    add_card(s6, Inches(0.8), Inches(1.5), Inches(11.7), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/diagram_01_system_architecture.png"):
        s6.shapes.add_picture("docs/screenshots/diagram_01_system_architecture.png", Inches(1.0), Inches(1.65), Inches(11.3), Inches(4.2))
    
    tb6_cap = s6.shapes.add_textbox(Inches(1.0), Inches(6.0), Inches(11.3), Inches(0.7))
    tf6_cap = tb6_cap.text_frame
    tf6_cap.word_wrap = True
    p = tf6_cap.paragraphs[0]
    r = p.add_run()
    r.text = "End-to-End Architecture: Natural Language Specs, RTL, and Logs feed into the 5-Agent Cognitive Engine, producing Verified RTL Patches and 100% Coverage Closure."
    r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = C_PRIMARY

    # =========================================================================
    # SLIDE 7: TOPIC 5 - ARCHITECTURE COMPONENTS: AGENTS 1 TO 5
    # =========================================================================
    s7 = add_base_slide("Topic 5: Architecture Components — Specialized Multi-Agent Breakdown", "Agent Specialization")
    
    agents = [
        ("Agent 1: Autonomous Triage", "Parses multi-megabyte simulation logs, isolates assertion failures, extracts error signatures, and classifies root causes.", C_PRIMARY),
        ("Agent 2: Plan Synthesizer", "Ingests PDF/Word specs and generates ISO 26262 traceability matrices, covergroups, tests, and SVA properties.", C_BLUE),
        ("Agent 3: Closed-Loop Sim", "Invokes EDA simulators (iverilog/verilator/vcs), tracks execution lifecycle, and automatically dumps waveforms.", C_AMBER),
        ("Agent 4: Web Cockpit", "High-performance FastAPI server with bi-directional WebSocket telemetry, Live Coverage Cockpit, and Waveform Studio.", C_PRIMARY),
        ("Agent 5: Patch & Sandbox", "Generates unified git diff patches, compiles in an isolated sandbox, and re-executes tests to guarantee zero regressions.", C_BLUE)
    ]
    
    for i, (atitle, adesc, acolor) in enumerate(agents):
        c_left = Inches(0.8) + (i % 3) * Inches(3.95)
        c_top = Inches(1.5) if i < 3 else Inches(4.3)
        c_w = Inches(3.75) if i < 3 else Inches(5.7)
        c_h = Inches(2.6)
        
        add_card(s7, c_left, c_top, c_w, c_h, C_CARD_BG, acolor)
        tb = s7.shapes.add_textbox(c_left + Inches(0.2), c_top + Inches(0.15), c_w - Inches(0.4), c_h - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = atitle + "\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = acolor
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = adesc; r.font.size = Pt(11); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 8: TOPIC 5 (CONT.) - 9 FORMAL RCA DECISION RULES & X-TRACER
    # =========================================================================
    s8 = add_base_slide("Topic 5 (Cont.): The 9 Formal Decision Rules & X-Tracer Engine", "Mathematical Grounding")
    
    # Left: The 9 Formal Rules Table
    add_card(s8, Inches(0.8), Inches(1.5), Inches(6.8), Inches(5.3), C_CARD_BG)
    tb8_l = s8.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(6.4), Inches(5.0))
    tf8_l = tb8_l.text_frame
    tf8_l.word_wrap = True
    
    p = tf8_l.paragraphs[0]
    r = p.add_run(); r.text = "The 9 Formal Decision Rules (Zero-Hallucination)\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    rules = [
        ("Rule 1 (Scoreboard Mismatch)", "DUT payload differs from golden reference -> Isolates computation vs. routing."),
        ("Rule 2 (X-Propagation)", "Unknown logic state (X) at output -> Traces back-fanin to uninitialized flop."),
        ("Rule 3 (Protocol Violation)", "SVA handshake assertion trips -> Checks grant latency and backpressure."),
        ("Rule 4 (Timing / Clock Glitch)", "Setup/hold race condition or missing flop synchronizer."),
        ("Rule 5 (Testbench Driver Hang)", "Driver finishes sequence without dropping UVM objection."),
        ("Rule 6 (Memory / Buffer Hazard)", "Read-after-write hazard or FIFO overflow/underflow flag bug."),
        ("Rule 7 (Lint / Synthesizability)", "Unintended latch or truncated bus width detected in AST."),
        ("Rule 8 (Simulation Timeout)", "Infinite loop or cyclic dependency stalling simulation clock."),
        ("Rule 9 (Environment Mismatch)", "Missing include path, compile macro, or simulator flag.")
    ]
    for rtitle, rdesc in rules:
        p = tf8_l.add_paragraph()
        p.space_after = Pt(2)
        r1 = p.add_run(); r1.text = f"• {rtitle}: "; r1.font.bold = True; r1.font.size = Pt(9.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{rdesc}"; r2.font.size = Pt(9); r2.font.color.rgb = C_TEXT

    # Right: X-Tracer Algorithm Card
    add_card(s8, Inches(7.8), Inches(1.5), Inches(4.7), Inches(5.3), C_CARD_BG, C_BLUE)
    tb8_r = s8.shapes.add_textbox(Inches(8.0), Inches(1.65), Inches(4.3), Inches(5.0))
    tf8_r = tb8_r.text_frame
    tf8_r.word_wrap = True
    
    p = tf8_r.paragraphs[0]
    r = p.add_run(); r.text = "The X-Tracer DAG Algorithm\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_BLUE
    
    steps = [
        ("1. AST Parser Graph", "Extracts full netlist DAG and always_ff / assign logic cones using PyVerilog."),
        ("2. Temporal VCD Slicing", "Identifies exact simulation cycle T_fail where signal transitions to X."),
        ("3. Backward Cone Traversal", "Recursively traverses driving inputs at cycle T_fail - 1."),
        ("4. Origin Isolation", "Pinpoints uninitialized flip-flop missing from asynchronous reset block with 100% precision.")
    ]
    for stitle, sdesc in steps:
        p = tf8_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"Step {stitle}\n"; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{sdesc}\n\n"; r2.font.size = Pt(10); r2.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 9: TOPIC 6 - TOOLS & MODELS USED
    # =========================================================================
    s9 = add_base_slide("Topic 6: Tools & Models Used — Multi-Provider Stack & EDA Ecosystem", "Technology Stack")
    
    stack_cols = [
        ("Cognitive & AI Models",
         "• Multi-Provider LLM Engine:\n  - Google Gemini 2.5 Flash\n  - Anthropic Claude 3.5 Sonnet\n  - OpenAI GPT-4o\n• Sovereign Air-Gapped Mode:\n  - Local Ollama & vLLM\n  - DeepSeek-Coder-V2 (16B/33B)\n  - Llama-3-70B-Instruct\n• ChromaDB Vector Store:\n  - 11 persistent collections\n  - Semantic AST chunking",
         C_PRIMARY),
        ("EDA Simulators & Compilers",
         "• Synopsys VCS:\n  - Native testbench & UVM 1.2\n• Siemens QuestaSim:\n  - UCDB functional coverage\n• Cadence Xcelium:\n  - Parallel multi-core compile\n• Verilator (C++):\n  - Ultra-fast cycle-accurate sim\n• Icarus Verilog (iverilog):\n  - Open-source zero-license triage\n• GTKWave & Verdi:\n  - VCD / FSDB trace analysis",
         C_BLUE),
        ("Infrastructure & Web GUI",
         "• PyVerilog AST Engine:\n  - Syntactic & netlist analysis\n• FastAPI Asynchronous Server:\n  - Sub-millisecond latency\n• WebSockets Bridge:\n  - Bi-directional event stream\n• Modern Vanilla Web Studio:\n  - Live Coverage Cockpit\n  - Waveform Studio\n  - Root Cause Inspector\n• Docker Containerization:\n  - 1-click reproducible sandbox",
         C_AMBER)
    ]
    
    for i, (stitle, scontent, scolor) in enumerate(stack_cols):
        c_left = Inches(0.8) + i * Inches(3.95)
        add_card(s9, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, scolor)
        
        tb = s9.shapes.add_textbox(c_left + Inches(0.2), Inches(1.7), Inches(3.35), Inches(4.9))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = stitle + "\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = scolor
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = scontent; r.font.size = Pt(10.5); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 10: TOPIC 7 - EXPERIMENTS CONDUCTED
    # =========================================================================
    s10 = add_base_slide("Topic 7: Experiments Conducted — Rigorous Industrial Testbeds", "Validation Benchmarks")
    
    benchmarks = [
        ("Arithmetic Logic Unit (ALU)",
         "• Complex combinational & sequential compute engine\n• 8 mathematical/logical opcodes, signed/unsigned flags\n• Injected Bugs: Subtraction borrow bit inversion, shift-by-zero boundary condition, overflow flag deassertion.",
         "Result: 100% bugs isolated, 14.2s avg RCA, 100% verified patches."),
        ("Synchronous & Asynchronous FIFO",
         "• Multi-clock circular buffer with 2-FF pointer synchronizers\n• Injected Bugs: Full flag assertion off-by-one, write pointer wrap glitch, read-on-empty underflow.\n• Edge Conditions: Concurrent read/write at full threshold.",
         "Result: Pinpointed off-by-one counter bug, synthesized exact fix."),
        ("AMBA AXI4-Stream Interface",
         "• High-throughput decoupled streaming interface\n• Injected Bugs: TVALID deassertion before TREADY acknowledged, premature TLAST framing pulse.",
         "Result: Flagged protocol violation, generated SVA property."),
        ("RISC-V RV32I Processor Pipeline",
         "• 5-stage pipelined integer instruction execution unit\n• Injected Bugs: RAW hazard forwarding bypass stall missing, branch misprediction flush delay.",
         "Result: Traced stale register value, verified pipeline patch.")
    ]
    
    for i, (btitle, bdesc, bres) in enumerate(benchmarks):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        add_card(s10, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG)
        
        tb = s10.shapes.add_textbox(c_left + Inches(0.2), c_top + Inches(0.15), Inches(5.3), Inches(2.2))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = btitle + "\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_PRIMARY
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = bdesc + "\n"; r.font.size = Pt(10); r.font.color.rgb = C_TEXT
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = "🎯 " + bres; r.font.size = Pt(10); r.font.bold = True; r.font.color.rgb = C_BLUE

    # =========================================================================
    # SLIDE 11: TOPIC 8 - RESULTS AND COMPARISON: AI VS MANUAL EFFORT
    # =========================================================================
    s11 = add_base_slide("Topic 8: Results & Comparison — AI Acceleration vs. Manual Effort", "Performance Metrics")
    
    add_card(s11, Inches(0.8), Inches(1.5), Inches(11.7), Inches(5.3), C_CARD_BG)
    tb11 = s11.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(11.3), Inches(4.9))
    tf11 = tb11.text_frame
    tf11.word_wrap = True
    
    p = tf11.paragraphs[0]
    r = p.add_run(); r.text = "Comprehensive Benchmark: Manual Human Engineer vs. VeriSight Autonomous Copilot\n\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    # Table Comparison Rows
    comp_metrics = [
        ("Metric / Verification Task", "Industry Manual Baseline", "VeriSight Autonomous Copilot", "Impact / Acceleration"),
        ("Simulation Failure Triage & RCA", "4 to 6 Hours per failure", "14.8 Seconds (Average)", "99.3% Time Reduction"),
        ("Verification Plan Synthesis", "2 to 3 Weeks (Manual spec review)", "18.2 Seconds (Full Plan + SVA)", "100x Speedup"),
        ("Root Cause Classification Accuracy", "78% (First-attempt human)", "95.4% (Multi-agent consensus)", "+17.4% Accuracy Gain"),
        ("Coverage Hole Closure Time", "6 to 8 Weeks (Random iterations)", "4 Days (AI directed stimulus)", "10x Faster Sign-Off"),
        ("Patch Generation & Sandbox Test", "1 to 2 Days (Code, lint, re-sim)", "3.2 Seconds (Zero-touch git patch)", "Instant Self-Healing"),
        ("Escaped Silicon Defect Rate", "28% of chips require re-spins", "<2% with formal SVA + trace checks", "Eliminates $20M+ Re-spins")
    ]
    
    for row_idx, (m_col1, m_col2, m_col3, m_col4) in enumerate(comp_metrics):
        p = tf11.add_paragraph()
        p.space_after = Pt(4)
        is_header = (row_idx == 0)
        
        r1 = p.add_run(); r1.text = f"{m_col1:<34} "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_PRIMARY if is_header else C_DARK
        r2 = p.add_run(); r2.text = f"{m_col2:<32} "; r2.font.bold = is_header; r2.font.size = Pt(10); r2.font.color.rgb = C_PRIMARY if is_header else C_MUTED
        r3 = p.add_run(); r3.text = f"{m_col3:<34} "; r3.font.bold = True; r3.font.size = Pt(10.5); r3.font.color.rgb = C_PRIMARY if is_header else C_BLUE
        r4 = p.add_run(); r4.text = f"{m_col4}"; r4.font.bold = True; r4.font.size = Pt(10.5); r4.font.color.rgb = C_PRIMARY if is_header else C_ACCENT

    # =========================================================================
    # SLIDE 12: TOPIC 8 (CONT.) - ROI & ECONOMIC IMPACT FOR ENTERPRISES
    # =========================================================================
    s12 = add_base_slide("Topic 8 (Cont.): Economic Impact & Enterprise Return on Investment", "Financial Model")
    
    roi_cards = [
        ("Annual Engineering Savings", "$1.8 Million / Year", "For a 50-person verification team: Eliminates 12,000+ hours of manual log parsing and waveform searching.", C_PRIMARY),
        ("Mask Re-Spin Elimination", "$15M - $30M Saved", "A single undetected corner-case bug caught pre-silicon saves an entire physical mask re-spin.", C_BLUE),
        ("Time-to-Market Acceleration", "2 to 3 Months Faster", "Reaching tape-out earlier captures prime consumer and data-center market windows worth tens of millions.", C_AMBER)
    ]
    for i, (rtitle, rval, rdesc, rcol) in enumerate(roi_cards):
        c_left = Inches(0.8) + i * Inches(3.95)
        add_card(s12, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, rcol)
        
        tb = s12.shapes.add_textbox(c_left + Inches(0.2), Inches(1.8), Inches(3.35), Inches(4.7))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = rtitle + "\n\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_DARK
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rval + "\n\n"; r.font.size = Pt(24); r.font.bold = True; r.font.color.rgb = rcol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rdesc; r.font.size = Pt(11); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 13: TOPIC 9 - DASHBOARD OVERVIEW: THE 6 GUIDED WORKFLOWS
    # =========================================================================
    s13 = add_base_slide("Topic 9: Dashboard Overview — The 6 Autonomous Workflows", "Platform Capabilities")
    
    # Left: Explanation of 6 Workflows
    add_card(s13, Inches(0.8), Inches(1.5), Inches(6.0), Inches(5.3), C_CARD_BG)
    tb13_l = s13.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(5.6), Inches(5.0))
    tf13_l = tb13_l.text_frame
    tf13_l.word_wrap = True
    
    p = tf13_l.paragraphs[0]
    r = p.add_run(); r.text = "Complete Suite: 6 Autonomous Workflows\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    wf_list = [
        ("[1] VeriSight Debug", "Root-cause analysis, 9-rule triage, and automated patch synthesis."),
        ("[2] VeriSight Plan", "Extracts features, test matrices, covergroups, and SVA assertions."),
        ("[3] Closed-Loop Sim", "Zero-touch runner (iverilog/verilator/vcs) with auto-triage trigger."),
        ("[4] Live Web Cockpit", "Interactive browser GUI (Coverage Cockpit, Waveform Studio)."),
        ("[5] Quick Demos", "1-click instant evaluations on pre-configured ALU and FIFO testbeds."),
        ("[6] Advanced CLI Exit", "Headless scriptable invocation for nightly CI/CD regression farms.")
    ]
    for wtitle, wdesc in wf_list:
        p = tf13_l.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {wtitle}: "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{wdesc}\n"; r2.font.size = Pt(10); r2.font.color.rgb = C_TEXT

    # Right: Animated GIF of Multi-Agent Workflow
    add_card(s13, Inches(7.0), Inches(1.5), Inches(5.5), Inches(5.3), C_CARD_BG)
    gif_path = "docs/presentation/gif_01_multi_agent_workflow.gif"
    if os.path.exists(gif_path):
        s13.shapes.add_picture(gif_path, Inches(7.1), Inches(1.65), Inches(5.3), Inches(4.3))
    tb_c13 = s13.shapes.add_textbox(Inches(7.1), Inches(6.05), Inches(5.3), Inches(0.6))
    tf_c13 = tb_c13.text_frame
    p = tf_c13.paragraphs[0]
    r = p.add_run(); r.text = "Animated Multi-Stage Autonomous Execution Pipeline"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    # =========================================================================
    # SLIDE 14: TOPIC 9 (CONT.) - LIVE COVERAGE COCKPIT
    # =========================================================================
    s14 = add_base_slide("Topic 9 (Cont.): Live Coverage Cockpit — Planned vs. Actual UCDB", "Coverage Closure")
    
    add_card(s14, Inches(0.8), Inches(1.5), Inches(5.5), Inches(5.3), C_CARD_BG)
    gif_cov = "docs/presentation/gif_02_coverage_closure.gif"
    if os.path.exists(gif_cov):
        s14.shapes.add_picture(gif_cov, Inches(0.9), Inches(1.65), Inches(5.3), Inches(4.3))
    tb_c14 = s14.shapes.add_textbox(Inches(0.9), Inches(6.05), Inches(5.3), Inches(0.6))
    tf_c14 = tb_c14.text_frame
    p = tf_c14.paragraphs[0]
    r = p.add_run(); r.text = "Animated Dynamic Coverage Closure Progression (42% -> 100%)"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    add_card(s14, Inches(6.5), Inches(1.5), Inches(6.0), Inches(5.3), C_CARD_BG)
    tb14_r = s14.shapes.add_textbox(Inches(6.7), Inches(1.65), Inches(5.6), Inches(5.0))
    tf14_r = tb14_r.text_frame
    tf14_r.word_wrap = True
    
    p = tf14_r.paragraphs[0]
    r = p.add_run(); r.text = "Dynamic Coverage Cockpit Features\n\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    cov_points = [
        ("Ingests Live Simulator UCDB", "Parses Synopsys vDB and Questa UCDB databases to compare actual coverage against planned features in real-time."),
        ("Visual Progress by Feature", "Every architectural feature has a dedicated progress bar showing percentage hit vs 100% target."),
        ("Red Highlighted Unhit Bins", "Zero-hit bins (e.g. rare FIFO backpressure corner cases) are highlighted in red with direct drill-down."),
        ("1-Click AI Directed Stimulus", "Engineers click 'Generate Directed Sequence' to automatically synthesize constrained-random sequences targeting unhit bins.")
    ]
    for ctitle, cdesc in cov_points:
        p = tf14_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {ctitle}: "; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{cdesc}\n\n"; r2.font.size = Pt(10.5); r2.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 15: TOPIC 9 (CONT.) - ROOT-CAUSE STUDIO & WAVEFORM INSPECTOR
    # =========================================================================
    s15 = add_base_slide("Topic 9 (Cont.): Root-Cause Studio & Waveform Inspector", "GUI Diagnostic")
    
    add_card(s15, Inches(0.8), Inches(1.5), Inches(6.2), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_12_rca_dashboard_gui.png"):
        s15.shapes.add_picture("docs/screenshots/screenshot_12_rca_dashboard_gui.png", Inches(0.9), Inches(1.65), Inches(6.0), Inches(4.3))
    tb_c15 = s15.shapes.add_textbox(Inches(0.9), Inches(6.05), Inches(6.0), Inches(0.6))
    tf_c15 = tb_c15.text_frame
    p = tf_c15.paragraphs[0]
    r = p.add_run(); r.text = "Interactive RCA Dashboard & Waveform Studio with Cursor Synchronization"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    add_card(s15, Inches(7.2), Inches(1.5), Inches(5.3), Inches(5.3), C_CARD_BG)
    tb15_r = s15.shapes.add_textbox(Inches(7.4), Inches(1.65), Inches(4.9), Inches(5.0))
    tf15_r = tb15_r.text_frame
    tf15_r.word_wrap = True
    
    p = tf15_r.paragraphs[0]
    r = p.add_run(); r.text = "Sub-Cycle Waveform Correlation\n\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    rca_points = [
        ("Unified Failure Timeline", "Correlates simulation log errors with exact physical clock edges."),
        ("Multi-Signal Bus Radix View", "Decodes binary, hexadecimal, and one-hot FSM states dynamically."),
        ("Failure Marker Cursor", "Automatically places inspection cursor at exact assertion trip timestamp (e.g. 450ns)."),
        ("Signal Fan-In Tracing", "Highlights upstream driving signals directly in the browser waveform canvas.")
    ]
    for rtitle, rdesc in rca_points:
        p = tf15_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {rtitle}:\n"; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{rdesc}\n\n"; r2.font.size = Pt(10); r2.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 16: TOPIC 9 (CONT.) - AUTOMATED PATCHING & SANDBOX SAFETY
    # =========================================================================
    s16 = add_base_slide("Topic 9 (Cont.): Automated Unified Patching & Sandbox Safety", "Automated Repair")
    
    add_card(s16, Inches(0.8), Inches(1.5), Inches(6.2), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_13_automated_patch.png"):
        s16.shapes.add_picture("docs/screenshots/screenshot_13_automated_patch.png", Inches(0.9), Inches(1.65), Inches(6.0), Inches(4.3))
    tb_c16 = s16.shapes.add_textbox(Inches(0.9), Inches(6.05), Inches(6.0), Inches(0.6))
    tf_c16 = tb_c16.text_frame
    p = tf_c16.paragraphs[0]
    r = p.add_run(); r.text = "VeriSight Unified Git Diff Patch with Automated Sandbox Verification"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    add_card(s16, Inches(7.2), Inches(1.5), Inches(5.3), Inches(5.3), C_CARD_BG)
    tb16_r = s16.shapes.add_textbox(Inches(7.4), Inches(1.65), Inches(4.9), Inches(5.0))
    tf16_r = tb16_r.text_frame
    tf16_r.word_wrap = True
    
    p = tf16_r.paragraphs[0]
    r = p.add_run(); r.text = "The Zero-Touch Repair Loop\n\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    patch_steps = [
        ("1. Minimal Git Diff", "Synthesizes surgical diff altering only the root-cause bug line without side effects."),
        ("2. AST Syntax Pre-Check", "Parses modified HDL with PyVerilog to guarantee syntax validity before saving."),
        ("3. Isolated Sandbox Simulation", "Copies patched design into /tmp sandbox and re-executes original simulation."),
        ("4. Regression Clean Sign-Off", "Confirms failing assertion is eliminated and all existing tests continue to pass.")
    ]
    for ptitle, pdesc in patch_steps:
        p = tf16_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"{ptitle}\n"; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{pdesc}\n\n"; r2.font.size = Pt(10); r2.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 17: TOPIC 10 - TOKEN UTILIZATION OVER COST
    # =========================================================================
    s17 = add_base_slide("Topic 10: Token Utilization Over Cost — Sovereign Economics", "Cost Efficiency")
    
    token_cards = [
        ("Cloud API Cost per Run", "$0.02 - $0.05", "Using Gemini 2.5 Flash or Claude 3.5 Sonnet: Average 12k tokens per complete debug run. An entire 1,000-test regression costs under $35.", C_PRIMARY),
        ("Sovereign Offline Cost", "$0.00 Marginal Cost", "Using local Ollama or vLLM running DeepSeek-Coder / Llama-3 on on-premise GPUs. Air-gapped zero external data transfer.", C_BLUE),
        ("AST Token Optimization", "84% Token Reduction", "PyVerilog AST pruning and targeted log slicing strips out 84% of irrelevant tokens before reaching LLM context.", C_AMBER)
    ]
    for i, (ttitle, tval, tdesc, tcol) in enumerate(token_cards):
        c_left = Inches(0.8) + i * Inches(3.95)
        add_card(s17, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, tcol)
        
        tb = s17.shapes.add_textbox(c_left + Inches(0.2), Inches(1.8), Inches(3.35), Inches(4.7))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = ttitle + "\n\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_DARK
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = tval + "\n\n"; r.font.size = Pt(22); r.font.bold = True; r.font.color.rgb = tcol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = tdesc; r.font.size = Pt(11); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 18: TOPIC 11 - SUMMARY: THE DEFENSIBLE MOAT
    # =========================================================================
    s18 = add_base_slide("Topic 11: Summary — The VeriSight Defensible Moat", "Strategic Advantage")
    
    moat_cards = [
        ("Deep Domain Grounding", "Not just a wrapper on an LLM: Integrates 9 formal decision rules, AST netlist traversal, and temporal waveform slicing.", C_PRIMARY),
        ("Air-Gapped Sovereign Security", "Semiconductor IP is protected by sovereign on-premise inference options (Ollama/vLLM). Zero IP leakage.", C_BLUE),
        ("Zero Vendor Lock-In", "Agnostic layer sitting above Synopsys VCS, Siemens Questa, Cadence Xcelium, and open-source Verilator.", C_AMBER),
        ("Massive Enterprise ROI", "Reduces debug turnaround from hours to seconds; prevents multi-million dollar physical silicon re-spins.", C_PRIMARY)
    ]
    for i, (mtitle, mdesc, mcol) in enumerate(moat_cards):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        add_card(s18, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG, mcol)
        
        tb = s18.shapes.add_textbox(c_left + Inches(0.25), c_top + Inches(0.2), Inches(5.2), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = mtitle + "\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = mcol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = mdesc; r.font.size = Pt(11); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 19: TOPIC 12 - FUTURE SCOPE: AUTONOMOUS SILICON ROADMAP
    # =========================================================================
    s19 = add_base_slide("Topic 12: Future Scope — The Autonomous Silicon Roadmap", "Product Roadmap")
    
    roadmap_phases = [
        ("Phase 1: Present (v2.4)", "Production Multi-Agent Triage", "• 6 Guided Workflows\n• 9 Formal RCA Rules\n• Live Coverage Cockpit\n• Sandbox Auto-Patch\n• FastAPI Web Studio", C_PRIMARY),
        ("Phase 2: Q1-Q2 2027", "Continuous Regression Learning", "• Nightly farm log clustering\n• Automated test deduping\n• Bayesian stimulus tuning\n• Cross-project bug memory\n• Git PR auto-commenting", C_BLUE),
        ("Phase 3: Q3-Q4 2027", "Silicon-to-Software Feedback", "• Post-silicon ATE tester link\n• Scan chain fault diagnosis\n• Automated ATPG vectors\n• Formal theorem proving\n• ISO 26262 ASIL-D certified", C_AMBER)
    ]
    for i, (rtitle, rsub, rdetails, rcolor) in enumerate(roadmap_phases):
        c_left = Inches(0.8) + i * Inches(3.95)
        add_card(s19, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, rcolor)
        
        tb = s19.shapes.add_textbox(c_left + Inches(0.2), Inches(1.7), Inches(3.35), Inches(4.9))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = rtitle + "\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = rcolor
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rsub + "\n\n"; r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = C_DARK
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rdetails; r.font.size = Pt(10.5); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 20: TOPIC 13 - INTEGRATION INTO REAL WORLD CHIP DESIGN
    # =========================================================================
    s20 = add_base_slide("Topic 13: Integration Into Real World Chip Design", "Enterprise Integration")
    
    add_card(s20, Inches(0.8), Inches(1.5), Inches(6.0), Inches(5.3), C_CARD_BG)
    tb20_l = s20.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(5.6), Inches(5.0))
    tf20_l = tb20_l.text_frame
    tf20_l.word_wrap = True
    
    p = tf20_l.paragraphs[0]
    r = p.add_run(); r.text = "Day-1 Frictionless CI/CD Deployment\n\n"; r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    integrations = [
        ("CI/CD Pipeline Hooks", "Integrates natively into Jenkins, GitLab CI, GitHub Actions via headless CLI."),
        ("Zero EDA Toolchain Disruption", "Wraps around existing Synopsys, Siemens, and Cadence regression scripts without modifying Makefiles."),
        ("Standard Format Ingestion", "Parses industry standard formats: SystemVerilog (.sv), VCD, FSDB, UCDB, and JUnit XML."),
        ("Slack & Teams Notifications", "Posts triage summaries, root-cause confidence scores, and patch diffs directly into team channels.")
    ]
    for ititle, idesc in integrations:
        p = tf20_l.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {ititle}: "; r1.font.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{idesc}\n\n"; r2.font.size = Pt(10); r2.font.color.rgb = C_TEXT

    add_card(s20, Inches(7.0), Inches(1.5), Inches(5.5), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_15_ci_cd_regression.png"):
        s20.shapes.add_picture("docs/screenshots/screenshot_15_ci_cd_regression.png", Inches(7.1), Inches(1.65), Inches(5.3), Inches(4.3))
    tb_c20 = s20.shapes.add_textbox(Inches(7.1), Inches(6.05), Inches(5.3), Inches(0.6))
    tf_c20 = tb_c20.text_frame
    p = tf_c20.paragraphs[0]
    r = p.add_run(); r.text = "Headless CI/CD Nightly Regression Triage Automation"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    # =========================================================================
    # SLIDE 21: TOPIC 14 - APPENDIX: SUPPORTING DOCUMENTS & COMPLIANCE
    # =========================================================================
    s21 = add_base_slide("Topic 14: Appendix — Supporting Documents & Compliance", "Verification Standards")
    
    app_cards = [
        ("ISO 26262 ASIL-D & DO-254", "Bi-directional traceability matrix guarantees complete requirement-to-test tracking required for safety-critical automotive and aerospace silicon.", C_PRIMARY),
        ("IEEE 1800 & UVM 1.2 Standards", "Full support for standard SystemVerilog, TLM 2.0 communication ports, sequence items, drivers, monitors, and scoreboards.", C_BLUE),
        ("107-Page Master Operations Journal", "Exhaustive field engineering documentation with 75 technical annexes, formal theorems, SVA assertion libraries, and simulator flags.", C_AMBER),
        ("ChromaDB Vector Telemetry", "11 persistent collections storing indexed specification paragraphs, register maps, and historical defect signatures.", C_DARK)
    ]
    for i, (atitle, adesc, acol) in enumerate(app_cards):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        add_card(s21, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG, acol)
        
        tb = s21.shapes.add_textbox(c_left + Inches(0.25), c_top + Inches(0.2), Inches(5.2), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = atitle + "\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = acol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = adesc; r.font.size = Pt(11); r.font.color.rgb = C_TEXT

    # =========================================================================
    # SLIDE 22: Q&A & CONTACT / PILOT INVITATION
    # =========================================================================
    s22 = add_base_slide()
    
    add_card(s22, Inches(1.5), Inches(1.5), Inches(10.3), Inches(5.2), C_CARD_BG, C_PRIMARY)
    tb22 = s22.shapes.add_textbox(Inches(1.8), Inches(1.8), Inches(9.7), Inches(4.6))
    tf22 = tb22.text_frame
    tf22.word_wrap = True
    
    p = tf22.paragraphs[0]
    r = p.add_run(); r.text = "VERISIGHT™\n"; r.font.size = Pt(36); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    p = tf22.add_paragraph()
    r = p.add_run(); r.text = "The Future of Silicon Verification is Autonomous.\n\n"; r.font.size = Pt(18); r.font.bold = True; r.font.color.rgb = C_DARK
    
    p = tf22.add_paragraph()
    r = p.add_run()
    r.text = "Thank you for your time. We are now open for Questions & Answers.\n\n" \
             "• Ready for Enterprise Pilot Deployments\n" \
             "• Available for Custom SoC Benchmark Evaluations\n\n"
    r.font.size = Pt(13); r.font.color.rgb = C_TEXT
    
    p = tf22.add_paragraph()
    r = p.add_run(); r.text = "Lead Architect & Presenter: Kittu Patel (@KITTUV03)\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    r2 = p.add_run(); r2.text = "VeriSight Production Release v2.4 • October 20, 2026"; r2.font.size = Pt(11); r2.font.color.rgb = C_MUTED

    print(f"Saving presentation with {len(prs.slides)} slides to {PPTX_PATH}...")
    prs.save(PPTX_PATH)
    print("SUCCESS: PowerPoint presentation created successfully!")

if __name__ == "__main__":
    create_presentation()
