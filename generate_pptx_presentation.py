#!/usr/bin/env python3
"""
VeriSight Presentation Generator (Production v2.4)
Generates the complete 22-slide enterprise presentation with:
- 16:9 widescreen layout with official Mirafra / VeriSight template background
- Smooth <p:transition><p:fade/></p:transition> on every slide
- Sequential point-wise <p:timing> click animations on all cards, bullets, and diagrams
- User's animated vector block diagram on Slide 6 (System Architecture)
- Comprehensive point-wise breakdown of all 6 VeriSight workflows
- Complete alignment with all 14 Agenda topics (restoring Topic 13 Real-World Integration)
- Accurate technology claims: pyslang (IEEE-1800 frontend) instead of PyVerilog
- Authors / Presenters: Patel Kittu & Vinod Nikhil Monterio
"""

import os
import shutil
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml import parse_xml

# Destination Paths
PPTX_LOCAL_PATH = "VeriSight_Investor_Presentation.pptx"
PPTX_WORKSPACE_UPDATED = "VeriSight_Presentation_Updated.pptx"
WINDOWS_DOWNLOADS_1 = "/mnt/c/Users/MIRAFRA_LP38/Downloads/VeriSight_Presentation 1.pptx"
WINDOWS_DOWNLOADS_UPDATED = "/mnt/c/Users/MIRAFRA_LP38/Downloads/VeriSight_Presentation_Updated.pptx"
TEMPLATE_IMG = "docs/presentation/template_slide.png"

# Color Palette matching Mirafra template & VeriSight styling
C_PRIMARY = RGBColor(11, 77, 50)       # Dark Emerald Green (#0b4d32)
C_ACCENT = RGBColor(34, 197, 94)       # Vibrant Green (#22c55e)
C_DARK = RGBColor(15, 23, 42)          # Slate Navy (#0f172a)
C_TEXT = RGBColor(51, 65, 85)          # Slate Text (#334155)
C_MUTED = RGBColor(100, 116, 139)      # Slate Muted (#64748b)
C_CARD_BG = RGBColor(255, 255, 255)    # Card White
C_CARD_BORDER = RGBColor(203, 213, 225)# Border Slate (#cbd5e1)
C_BLUE = RGBColor(2, 132, 199)         # Sky Blue (#0284c7)
C_AMBER = RGBColor(217, 119, 6)        # Amber (#d97706)
C_RED = RGBColor(220, 38, 38)          # Red (#dc2626)
C_PURPLE = RGBColor(147, 51, 234)      # Purple (#9333ea)

def build_timing_xml(click_steps):
    """
    Builds an OpenXML <p:timing> element given a list of click steps.
    Each click step is a list of shape ID strings: [spid1, spid2, ...]
    First shape in a step gets nodeType='clickEffect', remaining shapes get nodeType='withEffect'.
    """
    node_id = 3
    pars_xml = []
    all_spids = []

    for step in click_steps:
        step_spids = [str(s) for s in step if str(s)]
        if not step_spids:
            continue
        step_pars = []
        for sp_idx, spid in enumerate(step_spids):
            all_spids.append(spid)
            node_type = "clickEffect" if sp_idx == 0 else "withEffect"
            click_id = node_id
            set_id = node_id + 1
            eff_id = node_id + 2
            node_id += 3
            step_pars.append(f"""
            <p:par>
              <p:cTn id="{click_id}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold" grpId="0" nodeType="{node_type}">
                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                <p:childTnLst>
                  <p:set>
                    <p:cBhvr>
                      <p:cTn id="{set_id}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
                      <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                    </p:cBhvr>
                    <p:to><p:strVal val="visible"/></p:to>
                  </p:set>
                  <p:animEffect transition="in" filter="fade">
                    <p:cBhvr>
                      <p:cTn id="{eff_id}" dur="500"><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cTn>
                    </p:cBhvr>
                  </p:animEffect>
                </p:childTnLst>
              </p:cTn>
            </p:par>
            """)

        par_id = node_id
        inner_par_id = node_id + 1
        node_id += 2

        par = f"""
        <p:par>
          <p:cTn id="{par_id}" fill="hold">
            <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
            <p:childTnLst>
              <p:par>
                <p:cTn id="{inner_par_id}" fill="hold">
                  <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                  <p:childTnLst>
                    {''.join(step_pars)}
                  </p:childTnLst>
                </p:cTn>
              </p:par>
            </p:childTnLst>
          </p:cTn>
        </p:par>
        """
        pars_xml.append(par)

    bld_items = "".join([f'<p:bldP spid="{s}" grpId="0" bldLvl="0" animBg="1"/>' for s in all_spids])

    timing_xml_str = f"""
    <p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
      <p:tnLst>
        <p:par>
          <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
            <p:childTnLst>
              <p:seq concurrent="1" nextAc="seek">
                <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
                  <p:childTnLst>
                    {''.join(pars_xml)}
                  </p:childTnLst>
                </p:cTn>
                <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
                <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
              </p:seq>
            </p:childTnLst>
          </p:cTn>
        </p:par>
      </p:tnLst>
      <p:bldLst>
        {bld_items}
      </p:bldLst>
    </p:timing>
    """
    return timing_xml_str

def apply_slide_effects(slide, click_steps=None):
    """Adds fade transition and sequential click animations to slide."""
    trans_xml = parse_xml('<p:transition xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:fade/></p:transition>')
    slide._element.append(trans_xml)
    if click_steps:
        timing_xml_str = build_timing_xml(click_steps)
        timing_xml = parse_xml(timing_xml_str)
        slide._element.append(timing_xml)

def generate_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_base_slide(title_text=None, category_badge=None):
        slide = prs.slides.add_slide(blank_layout)
        if os.path.exists(TEMPLATE_IMG):
            slide.shapes.add_picture(TEMPLATE_IMG, 0, 0, Inches(13.333), Inches(7.5))
        
        if title_text:
            tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.65), Inches(11.7), Inches(0.85))
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
            
            run_title = p.add_run()
            run_title.text = title_text
            run_title.font.name = "Arial"
            run_title.font.size = Pt(21)
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
    # SLIDE 1: COVER / TITLE SLIDE
    # =========================================================================
    s1 = add_base_slide()
    
    # Title Hero Box
    tb_hero = s1.shapes.add_textbox(Inches(0.8), Inches(1.1), Inches(11.7), Inches(3.2))
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
    r_sub.text = "Autonomous Silicon Verification, Plan Synthesis & Failure Debugging Copilot"
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(20)
    r_sub.font.bold = True
    r_sub.font.color.rgb = C_DARK

    p3 = tf_hero.add_paragraph()
    r_desc = p3.add_run()
    r_desc.text = "Bridging Natural Language Hardware Specifications to Zero-Bug Silicon with Tri-Engine Multi-Agent AI,\n" \
                 "Spec-Driven UVM Testbench Synthesis, Closed-Loop Simulation, and Deterministic Root Cause Analysis."
    r_desc.font.name = "Arial"
    r_desc.font.size = Pt(13)
    r_desc.font.color.rgb = C_TEXT

    # 3 Key Value Metric Cards
    cards_data = [
        ("100x Faster Triage", "Root cause isolated in <15s vs. 4-6 hours manual engineer debugging", C_PRIMARY),
        ("Zero Hallucinations", "9 Formal Decision Rules + Static pyslang AST X-Tracer + Sandbox Validation", C_BLUE),
        ("Universal Compatibility", "Seamless Day-1 drop-in across VCS, Questa, Xcelium, and Verilator", C_AMBER)
    ]
    card_w = Inches(3.64)
    card_gap = Inches(0.39)
    s1_steps = []
    
    for i, (cheader, cdesc, ccolor) in enumerate(cards_data):
        c_left = Inches(0.8) + i * (card_w + card_gap)
        c_top = Inches(4.35)
        card_shp = add_card(s1, c_left, c_top, card_w, Inches(1.8), C_CARD_BG, ccolor)
        
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

        s1_steps.append([card_shp.shape_id, tb_c.shape_id])

    # Presenter & Team Card
    tb_team = s1.shapes.add_textbox(Inches(0.8), Inches(6.35), Inches(11.7), Inches(0.7))
    tf_team = tb_team.text_frame
    tf_team.word_wrap = True
    pt = tf_team.paragraphs[0]
    rt1 = pt.add_run()
    rt1.text = "Team Members: Patel Kittu & Vinod Nikhil Monterio   |   Lead Architect: Kittu Patel (@KITTUV03)\n"
    rt1.font.size = Pt(11)
    rt1.font.bold = True
    rt1.font.color.rgb = C_DARK
    rt2 = pt.add_run()
    rt2.text = "VeriSight Production Release v2.4 • Confidential Enterprise Edition • October 2026"
    rt2.font.size = Pt(10)
    rt2.font.color.rgb = C_MUTED
    s1_steps.append([tb_team.shape_id])

    apply_slide_effects(s1, s1_steps)

    # =========================================================================
    # SLIDE 2: AGENDA (MATCHING ALL 14 TOPICS)
    # =========================================================================
    s2 = add_base_slide("Presentation Roadmap & Table of Contents", "Agenda")
    
    # Left Column: Topics 1-7
    card_l2 = add_card(s2, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb2_l = s2.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(5.2), Inches(4.9))
    tf2_l = tb2_l.text_frame
    tf2_l.word_wrap = True
    
    p = tf2_l.paragraphs[0]
    r = p.add_run(); r.text = "PART I: FOUNDATIONAL TECHNOLOGY\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    agenda_part1 = [
        ("01", "Idea Overview", "The VeriSight Vision & Autonomous Triage"),
        ("02", "Problem Statement", "The Silicon Verification Crisis ($30M+ Re-Spins)"),
        ("03", "AI Approach to Solve Problem", "Deterministic Multi-Agent Cognitive Pipeline"),
        ("04", "Solution Architecture", "End-to-End System Block Diagram & Fabric"),
        ("05", "Architecture Components", "5-Agent Breakdown & 9 Formal RCA Rules"),
        ("06", "Tools & Models Used", "Multi-Provider Stack, pyslang & EDA Ecosystem"),
        ("07", "Experiments Conducted", "Rigorous Testbeds (ALU, FIFO, AXI-Stream, RISC-V)")
    ]
    for num, title, desc in agenda_part1:
        p = tf2_l.add_paragraph()
        r1 = p.add_run(); r1.text = f"{num}  {title} — "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{desc}\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    # Right Column: Topics 8-14
    card_r2 = add_card(s2, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3), C_CARD_BG, C_BLUE)
    tb2_r = s2.shapes.add_textbox(Inches(7.0), Inches(1.7), Inches(5.3), Inches(4.9))
    tf2_r = tb2_r.text_frame
    tf2_r.word_wrap = True
    
    p = tf2_r.paragraphs[0]
    r = p.add_run(); r.text = "PART II: WORKFLOWS, METRICS & DEPLOYMENT\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_BLUE
    
    agenda_part2 = [
        ("08", "Results & Comparison", "AI vs. Manual Effort Benchmark & Enterprise ROI"),
        ("09", "Platform Tri-Engine Suite", "VeriSight Debug, Plan Architect & Spec-Driven TestBench"),
        ("10", "Token Utilization Over Cost", "Sovereign Offline Economics & AST Optimization"),
        ("11", "Summary & Defensible Moat", "Domain Grounding, Security & Zero Vendor Lock-In"),
        ("12", "Future Scope & Roadmap", "Autonomous Silicon Evolution (Phase 1, 2, 3)"),
        ("13", "Real-World Chip Integration", "Day-1 Frictionless CI/CD & EDA Tool Wrapping"),
        ("14", "Appendix & Standards", "ISO 26262 ASIL-D, DO-254, IEEE 1800 & UVM 1.2")
    ]
    for num, title, desc in agenda_part2:
        p = tf2_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"{num}  {title} — "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{desc}\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    s2_steps = [
        [card_l2.shape_id, tb2_l.shape_id],
        [card_r2.shape_id, tb2_r.shape_id]
    ]
    apply_slide_effects(s2, s2_steps)

    # =========================================================================
    # SLIDE 3: TOPIC 01 - IDEA OVERVIEW
    # =========================================================================
    s3 = add_base_slide("Topic 1: Idea Overview — The VeriSight Vision", "Idea Overview")
    
    # Left: What is VeriSight?
    c3_1 = add_card(s3, Inches(0.8), Inches(1.5), Inches(6.8), Inches(2.6), C_CARD_BG, C_PRIMARY)
    tb3_1 = s3.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(6.4), Inches(2.3))
    tf3_1 = tb3_1.text_frame
    tf3_1.word_wrap = True
    p = tf3_1.paragraphs[0]
    r = p.add_run(); r.text = "What is VeriSight?\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    vision_points = [
        "Autonomous silicon verification, testbench synthesis & failure debugging copilot designed for digital ASIC & SoC design.",
        "Eliminates the multi-week verification bottleneck between RTL design freeze and tape-out sign-off.",
        "Tri-Engine Architecture: Diagnostic Debug, Verification Plan Synthesis, and Spec-Driven UVM 1.2 Testbench Generation."
    ]
    for vp in vision_points:
        p = tf3_1.add_paragraph()
        r1 = p.add_run(); r1.text = "• "; r1.font.bold = True; r1.font.color.rgb = C_PRIMARY
        r2 = p.add_run(); r2.text = f"{vp}\n"; r2.font.size = Pt(10.5); r2.font.color.rgb = C_TEXT

    # Left Bottom: Core Autonomous Pillars
    c3_2 = add_card(s3, Inches(0.8), Inches(4.25), Inches(6.8), Inches(2.55), C_CARD_BG, C_BLUE)
    tb3_2 = s3.shapes.add_textbox(Inches(1.0), Inches(4.35), Inches(6.4), Inches(2.35))
    tf3_2 = tb3_2.text_frame
    tf3_2.word_wrap = True
    p = tf3_2.paragraphs[0]
    r = p.add_run(); r.text = "Core Autonomous Capabilities\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_BLUE
    
    pillars = [
        ("Spec-Driven UVM Synthesis", "Synthesizes 14-component UVM 1.2 VIP suites with specification-grounded golden reference models."),
        ("Autonomous Verification Plan", "Extracts 50+ testcases across 8 categories, 90+ coverage points, and 30+ SVA assertions from specs."),
        ("Root-Cause Diagnostic Engine", "Applies 9 formal decision rules and backwards AST cone traversal to isolate bugs in <15s."),
        ("Self-Synthesizing Patch Generator", "Generates minimal unified git diffs and validates syntax in an isolated compile sandbox.")
    ]
    for ptitle, pdesc in pillars:
        p = tf3_2.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {ptitle}: "; r1.font.bold = True; r1.font.size = Pt(9.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{pdesc}"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    # Right: CLI Launcher Screenshot
    c3_3 = add_card(s3, Inches(7.8), Inches(1.5), Inches(4.7), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_01_welcome_menu.png"):
        pic3 = s3.shapes.add_picture("docs/screenshots/screenshot_01_welcome_menu.png", Inches(8.0), Inches(1.7), Inches(4.3), Inches(4.4))
    else:
        pic3 = None
    tb_c3 = s3.shapes.add_textbox(Inches(8.0), Inches(6.2), Inches(4.3), Inches(0.5))
    tf_c3 = tb_c3.text_frame
    p = tf_c3.paragraphs[0]
    r = p.add_run(); r.text = "VeriSight Guided CLI Launcher with Tri-Engine Architecture"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    s3_steps = [
        [c3_1.shape_id, tb3_1.shape_id],
        [c3_2.shape_id, tb3_2.shape_id],
        [c3_3.shape_id, pic3.shape_id, tb_c3.shape_id] if pic3 else [c3_3.shape_id, tb_c3.shape_id]
    ]
    apply_slide_effects(s3, s3_steps)

    # =========================================================================
    # SLIDE 4: TOPIC 02 - PROBLEM STATEMENT
    # =========================================================================
    s4 = add_base_slide("Topic 2: Problem Statement — The Silicon Verification Crisis", "Market Need")
    
    problems = [
        ("1. 70% Development Cycle Eaten by Verification",
         "• Verification is the single largest cost and timeline driver in semiconductor design.\n"
         "• Over 70% of total engineering headcount and project schedule is spent triaging RTL.\n"
         "• Regressions tie up compute clusters for days waiting for failure classification.",
         C_RED),
        ("2. Exploding Complexity & Mask Re-Spin Costs",
         "• Modern SoCs pack 100M+ to tens of billions of transistors with complex clock domains.\n"
         "• A single escaped functional bug requires a physical silicon mask re-spin costing $15M to $30M+.\n"
         "• Tape-out slips lead to severe market share erosion and revenue loss.",
         C_AMBER),
        ("3. Acute Senior Verification Talent Shortage",
         "• The global semiconductor industry faces a deficit of 30,000+ verification engineers.\n"
         "• Senior engineers spend 60% of their day manually wading through 50,000-line simulation logs.\n"
         "• Repetitive manual triage causes engineer burnout and high turnover.",
         C_PRIMARY),
        ("4. Disconnected Specs & Coverage Closure Stalls",
         "• Architectural specifications (Word/PDF) drift away from SystemVerilog testbenches.\n"
         "• Verification teams spend 6-8 weeks stuck at 85% coverage unable to hit corner-case bins.\n"
         "• Lack of automated requirement-to-test traceability creates ISO 26262 audit compliance risk.",
         C_BLUE)
    ]
    s4_steps = []
    for i, (ptitle, pcontent, pcol) in enumerate(problems):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        card_shp = add_card(s4, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG, pcol)
        
        tb = s4.shapes.add_textbox(c_left + Inches(0.25), c_top + Inches(0.15), Inches(5.2), Inches(2.2))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = ptitle + "\n\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = pcol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = pcontent; r.font.size = Pt(10); r.font.color.rgb = C_TEXT
        s4_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s4, s4_steps)

    # =========================================================================
    # SLIDE 5: TOPIC 03 - AI APPROACH TO SOLVE THE PROBLEM
    # =========================================================================
    s5 = add_base_slide("Topic 3: AI Approach — Deterministic Multi-Agent Cognitive Pipeline", "Core Innovation")
    
    # Left: Why Generic AI Fails
    c5_l = add_card(s5, Inches(0.8), Inches(1.5), Inches(5.7), Inches(5.3), C_CARD_BG, C_RED)
    tb5_l = s5.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(5.3), Inches(5.0))
    tf5_l = tb5_l.text_frame
    tf5_l.word_wrap = True
    
    p = tf5_l.paragraphs[0]
    r = p.add_run(); r.text = "Why Generic AI (ChatGPT / Copilot) Fails in Silicon\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_RED
    
    fails = [
        ("Hallucinates Non-Existent Hardware", "Suggests software libraries or invalid SystemVerilog syntax that fails downstream synthesis."),
        ("Blind to Waveform Timestamps", "Cannot parse cycle-by-cycle VCD/FSDB temporal transitions or physical clock edges."),
        ("No Structural HDL Understanding", "Lacks semantic knowledge of fan-in logic cones, CDC synchronizers, or 4-state simulation (X/Z)."),
        ("No Execution Sandbox", "Generates unchecked code without verifying whether regression tests pass or fail.")
    ]
    for ftitle, fdesc in fails:
        p = tf5_l.add_paragraph()
        r1 = p.add_run(); r1.text = f"❌ {ftitle}: "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{fdesc}\n\n"; r2.font.size = Pt(10); r2.font.color.rgb = C_TEXT

    # Right: The VeriSight Solution
    c5_r = add_card(s5, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb5_r = s5.shapes.add_textbox(Inches(7.0), Inches(1.65), Inches(5.3), Inches(5.0))
    tf5_r = tb5_r.text_frame
    tf5_r.word_wrap = True
    
    p = tf5_r.paragraphs[0]
    r = p.add_run(); r.text = "The VeriSight Multi-Agent Solution\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    solves = [
        ("9 Deterministic Decision Rules", "Mathematical rules strictly categorize bugs as RTL vs TB vs Spec vs Unknown (Zero Hallucination)."),
        ("Static pyslang AST X-Tracer", "Traverses genuine elaborated SystemVerilog AST to flag reset-less sequential registers without simulation."),
        ("Multi-Modal Waveform Slicing", "Extracts +/- 20 cycles around assertion failure timestamp for sub-cycle precision using pywellen."),
        ("Closed-Loop Sandbox Validation", "Every patch is re-compiled in an isolated sandbox with zero human intervention.")
    ]
    for stitle, sdesc in solves:
        p = tf5_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"✅ {stitle}: "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{sdesc}\n\n"; r2.font.size = Pt(10); r2.font.color.rgb = C_TEXT

    s5_steps = [
        [c5_l.shape_id, tb5_l.shape_id],
        [c5_r.shape_id, tb5_r.shape_id]
    ]
    apply_slide_effects(s5, s5_steps)

    # =========================================================================
    # SLIDE 6: TOPIC 04 - SOLUTION ARCHITECTURE (USER'S ANIMATED VECTOR DIAGRAM)
    # =========================================================================
    # We copy the user's vector shapes and sequential animations from Slide 6 of VeriSight_Presentation 1.pptx
    s6 = prs.slides.add_slide(blank_layout)
    if os.path.exists(TEMPLATE_IMG):
        s6.shapes.add_picture(TEMPLATE_IMG, 0, 0, Inches(13.333), Inches(7.5))
    
    # Load source slide 6 from user's presentation
    src_candidates = [
        "/home/mirafra_lp38/.gemini/antigravity/brain/ebda9bdb-6793-40cd-9d90-a1b3aa94d7eb/.user_uploaded/media_1793207608125_41b06f95.pptx",
        WINDOWS_DOWNLOADS_1,
        WINDOWS_DOWNLOADS_UPDATED,
        "VeriSight_Presentation_Updated.pptx",
        "VeriSight_Investor_Presentation.pptx"
    ]
    src_path = None
    for cand in src_candidates:
        if os.path.exists(cand):
            src_path = cand
            break
            
    if src_path is not None:
        src_p = pptx.Presentation(src_path)
        slide6_src = src_p.slides[5]
        
        for shape in slide6_src.shapes:
            if shape.name != "Picture 1":
                s6._element.spTree.append(shape._element)
                
        timing_xml_s6 = None
        for child in slide6_src._element:
            if child.tag.endswith("timing"):
                timing_xml_s6 = child
                
        trans_xml_s6 = parse_xml('<p:transition xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:fade/></p:transition>')
        s6._element.append(trans_xml_s6)
        if timing_xml_s6 is not None:
            s6._element.append(timing_xml_s6)

    # =========================================================================
    # SLIDE 7: TOPIC 05 - ARCHITECTURE COMPONENTS: AGENTS 1 TO 5
    # =========================================================================
    s7 = add_base_slide("Topic 5: Architecture Components — Specialized Multi-Agent Breakdown", "Agent Specialization")
    
    agents = [
        ("Agent 1: Knowledge Engine",
         "• Multi-Modal AST Extraction with pyslang\n"
         "• Port Map, Interfaces & Clock Domain Hierarchy\n"
         "• Tokenized Simulation Log Error Signatures\n"
         "• Waveform parser (pywellen) -> knowledge.json",
         C_PRIMARY),
        ("Agent 2: Root Cause Classifier",
         "• 9 Formal Deterministic Decision Rules\n"
         "• Multi-Hop Evidence Graph Construction\n"
         "• RTL Bug vs TB Bug vs Spec Bug vs Unknown\n"
         "• Bayesian Confidence Scoring -> summary.json",
         C_BLUE),
        ("Agent 3: RTL Root Cause Analyzer",
         "• Static Reset-Less Register Scan via pyslang\n"
         "• WaveTrace Backward Fan-In Cone Traversal\n"
         "• Multi-Clock CDC Hazard & FSM Deadlock Check\n"
         "• Deterministic Evidence -> rtl_analysis.json",
         C_AMBER),
        ("Agent 4: Interactive Reporter",
         "• High-Performance FastAPI Asynchronous Server\n"
         "• Interactive HTML Cockpit (`report.html`)\n"
         "• Sub-Cycle Waveform Cursor Correlation\n"
         "• Machine-Readable Schemas (`error.json`)",
         C_PRIMARY),
        ("Agent 5: Fix Generator & Sandbox",
         "• Synthesizes Minimal Surgical Git Diff Patches\n"
         "• pyslang AST Syntax Pre-Check Before Write\n"
         "• Isolated Compilation Sandbox (`/tmp`)\n"
         "• Regression Re-Simulation Sign-Off Verification",
         C_PURPLE)
    ]
    s7_steps = []
    for i, (atitle, adesc, acolor) in enumerate(agents):
        c_left = Inches(0.8) + (i % 3) * Inches(3.95)
        c_top = Inches(1.5) if i < 3 else Inches(4.35)
        c_w = Inches(3.75) if i < 3 else Inches(5.7)
        c_h = Inches(2.6)
        
        card_shp = add_card(s7, c_left, c_top, c_w, c_h, C_CARD_BG, acolor)
        tb = s7.shapes.add_textbox(c_left + Inches(0.2), c_top + Inches(0.15), c_w - Inches(0.4), c_h - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = atitle + "\n\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = acolor
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = adesc; r.font.size = Pt(10); r.font.color.rgb = C_TEXT
        s7_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s7, s7_steps)

    # =========================================================================
    # SLIDE 8: TOPIC 05 (CONT.) - 9 FORMAL RCA RULES & X-TRACER
    # =========================================================================
    s8 = add_base_slide("Topic 5 (Cont.): The 9 Formal Decision Rules & X-Tracer Engine", "Mathematical Grounding")
    
    # Left: The 9 Formal Rules Table
    c8_l = add_card(s8, Inches(0.8), Inches(1.5), Inches(6.8), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb8_l = s8.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(6.4), Inches(5.0))
    tf8_l = tb8_l.text_frame
    tf8_l.word_wrap = True
    
    p = tf8_l.paragraphs[0]
    r = p.add_run(); r.text = "The 9 Formal Decision Rules (Zero-Hallucination)\n"; r.font.size = Pt(13.5); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    rules = [
        ("Rule 1 (Scoreboard Mismatch)", "DUT payload differs from golden reference -> Isolates computation vs. routing."),
        ("Rule 2 (X-Propagation)", "Unknown logic state (X) at output -> Traces back-fanin to uninitialized flop."),
        ("Rule 3 (Protocol Violation)", "SVA handshake assertion trips -> Checks grant latency, ready/valid backpressure."),
        ("Rule 4 (Timing / Clock Glitch)", "Setup/hold race condition or missing 2-FF synchronizer across CDC boundary."),
        ("Rule 5 (Testbench Driver Hang)", "UVM driver finishes sequence without dropping objection or hangs in loop."),
        ("Rule 6 (Memory / Buffer Hazard)", "Read-after-write hazard, FIFO overflow/underflow flag bug, or pointer wrap glitch."),
        ("Rule 7 (Lint / Synthesizability)", "Unintended inferred latch or truncated bus width detected in AST."),
        ("Rule 8 (Simulation Timeout)", "Infinite loop or cyclic combinational dependency stalling simulation clock."),
        ("Rule 9 (Environment Mismatch)", "Missing compiler include path, macro define, or simulator tool flag.")
    ]
    for rtitle, rdesc in rules:
        p = tf8_l.add_paragraph()
        p.space_after = Pt(2)
        r1 = p.add_run(); r1.text = f"• {rtitle}: "; r1.font.bold = True; r1.font.size = Pt(9.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{rdesc}"; r2.font.size = Pt(9); r2.font.color.rgb = C_TEXT

    # Right: X-Tracer Algorithm Card
    c8_r = add_card(s8, Inches(7.8), Inches(1.5), Inches(4.7), Inches(5.3), C_CARD_BG, C_BLUE)
    tb8_r = s8.shapes.add_textbox(Inches(8.0), Inches(1.65), Inches(4.3), Inches(5.0))
    tf8_r = tb8_r.text_frame
    tf8_r.word_wrap = True
    
    p = tf8_r.paragraphs[0]
    r = p.add_run(); r.text = "The pyslang X-Tracer DAG Algorithm\n\n"; r.font.size = Pt(13.5); r.font.bold = True; r.font.color.rgb = C_BLUE
    
    steps = [
        ("1. AST Parse & Elaborate", "pyslang (Slang SystemVerilog frontend) parses the RTL into a real elaborated AST — always_ff / assign / reset logic, with types and source locations."),
        ("2. Static X-Origin Scan", "Flags sequential registers written in clock block but not assigned in reset branch (candidate X origins) — source-only, zero-sim overhead."),
        ("3. Temporal VCD Slicing", "Identifies exact simulation cycle T_fail where a failing signal transitions to 4-state X/Z."),
        ("4. Backward Cone Traversal", "WaveTrace recursively traverses driving inputs at cycle T_fail - 1 through logic netlist to isolate origin flop.")
    ]
    for stitle, sdesc in steps:
        p = tf8_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"Step {stitle}\n"; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{sdesc}\n\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    s8_steps = [
        [c8_l.shape_id, tb8_l.shape_id],
        [c8_r.shape_id, tb8_r.shape_id]
    ]
    apply_slide_effects(s8, s8_steps)

    # =========================================================================
    # SLIDE 9: TOPIC 06 - TOOLS & MODELS USED
    # =========================================================================
    s9 = add_base_slide("Topic 6: Tools & Models Used — Multi-Provider Stack & EDA Ecosystem", "Technology Stack")
    
    stack_cols = [
        ("Cognitive & AI Models",
         "• Multi-Provider Cloud LLMs:\n"
         "  - Google Gemini 2.5 Flash\n"
         "  - Anthropic Claude 3.5 Sonnet\n"
         "  - OpenAI GPT-4o\n\n"
         "• Sovereign Air-Gapped Mode:\n"
         "  - Local Ollama & vLLM\n"
         "  - DeepSeek-Coder-V2 (16B/33B)\n"
         "  - Llama-3-70B-Instruct\n\n"
         "• ChromaDB Vector Store:\n"
         "  - 11 persistent collections\n"
         "  - Semantic AST chunking & retrieval",
         C_PRIMARY),
        ("EDA Simulators & Compilers",
         "• Synopsys VCS:\n"
         "  - Native testbench & UVM 1.2\n"
         "  - vDB functional coverage\n\n"
         "• Siemens QuestaSim:\n"
         "  - UCDB functional coverage database\n\n"
         "• Cadence Xcelium:\n"
         "  - Parallel multi-core compile\n\n"
         "• Verilator (C++):\n"
         "  - Cycle-accurate open-source sim\n\n"
         "• Icarus Verilog (iverilog):\n"
         "  - Open-source zero-license triage",
         C_BLUE),
        ("Infrastructure & Web Studio",
         "• pyslang / Slang Frontend:\n"
         "  - IEEE-1800 SystemVerilog frontend\n"
         "  - AST elaboration & diagnostics\n\n"
         "• FastAPI Asynchronous Server:\n"
         "  - Sub-millisecond latency REST API\n"
         "  - Bi-directional WebSockets bridge\n\n"
         "• Modern Vanilla Web Studio:\n"
         "  - Live Coverage Cockpit\n"
         "  - Waveform Studio & RCA Inspector\n\n"
         "• Docker Containerization:\n"
         "  - 1-click reproducible sandbox",
         C_AMBER)
    ]
    s9_steps = []
    for i, (stitle, scontent, scolor) in enumerate(stack_cols):
        c_left = Inches(0.8) + i * Inches(3.95)
        card_shp = add_card(s9, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, scolor)
        
        tb = s9.shapes.add_textbox(c_left + Inches(0.2), Inches(1.7), Inches(3.35), Inches(4.9))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = stitle + "\n\n"; r.font.size = Pt(13.5); r.font.bold = True; r.font.color.rgb = scolor
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = scontent; r.font.size = Pt(10); r.font.color.rgb = C_TEXT
        s9_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s9, s9_steps)

    # =========================================================================
    # SLIDE 10: TOPIC 07 - EXPERIMENTS CONDUCTED
    # =========================================================================
    s10 = add_base_slide("Topic 7: Experiments Conducted — Rigorous Industrial Testbeds", "Validation Benchmarks")
    
    testbeds = [
        ("Arithmetic Logic Unit (ALU)",
         "• Complex combinational & sequential compute engine\n"
         "• 8 mathematical/logical opcodes, signed/unsigned flags\n"
         "• Injected Bugs: Subtraction borrow bit inversion, shift-by-zero boundary, missing reset state\n"
         "🎯 Result: 100% bugs isolated, 14.2s avg RCA, 100% verified patches, zero regression.",
         C_PRIMARY),
        ("Synchronous & Asynchronous FIFO",
         "• Multi-clock circular buffer with 2-FF pointer synchronizers\n"
         "• Injected Bugs: Full flag assertion off-by-one, write pointer wrap glitch, read-on-empty underflow\n"
         "• Edge Conditions: Concurrent read/write at full threshold\n"
         "🎯 Result: Pinpointed off-by-one counter bug, synthesized surgical fix, verified in 15.1s.",
         C_BLUE),
        ("AMBA AXI4-Stream Interface",
         "• High-throughput decoupled streaming interface with handshakes\n"
         "• Injected Bugs: TVALID deassertion before TREADY acknowledged, premature TLAST framing pulse\n"
         "• Protocol Checks: Ready/valid handshake latency and backpressure\n"
         "🎯 Result: Caught protocol violation, generated formal SVA assertion, verified in 13.8s.",
         C_AMBER),
        ("RISC-V RV32I Processor Pipeline",
         "• 5-stage pipelined integer instruction execution unit\n"
         "• Injected Bugs: RAW hazard forwarding bypass stall missing, branch misprediction flush delay\n"
         "• Hazard Detection: Inter-instruction data dependencies\n"
         "🎯 Result: Traced stale register value, verified pipeline hazard patch in 18.4s.",
         C_PURPLE)
    ]
    s10_steps = []
    for i, (ttitle, tcontent, tcolor) in enumerate(testbeds):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        card_shp = add_card(s10, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG, tcolor)
        
        tb = s10.shapes.add_textbox(c_left + Inches(0.25), c_top + Inches(0.15), Inches(5.2), Inches(2.2))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = ttitle + "\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = tcolor
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = tcontent; r.font.size = Pt(9.5); r.font.color.rgb = C_TEXT
        s10_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s10, s10_steps)

    # =========================================================================
    # SLIDE 11: TOPIC 08 - RESULTS AND COMPARISON (TABLE)
    # =========================================================================
    s11 = add_base_slide("Topic 8: Results & Comparison — AI Acceleration vs. Manual Effort", "Performance Metrics")
    
    # Header Subtitle Box
    tb11_sub = s11.shapes.add_textbox(Inches(0.8), Inches(1.35), Inches(11.7), Inches(0.4))
    tf11_sub = tb11_sub.text_frame
    p = tf11_sub.paragraphs[0]
    r = p.add_run(); r.text = "Comprehensive Benchmark: Manual Human Engineer vs. VeriSight Autonomous Copilot"; r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = C_DARK

    rows, cols = 7, 4
    left = Inches(0.8)
    top = Inches(1.85)
    width = Inches(11.7)
    height = Inches(4.9)
    table_shape = s11.shapes.add_table(rows, cols, left, top, width, height)
    tbl = table_shape.table
    
    tbl.columns[0].width = Inches(3.2)
    tbl.columns[1].width = Inches(3.0)
    tbl.columns[2].width = Inches(3.0)
    tbl.columns[3].width = Inches(2.5)
    
    headers = ["Metric / Verification Task", "Industry Manual Baseline", "VeriSight Autonomous Copilot", "Impact / Acceleration"]
    for j, h in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_PRIMARY
        p = cell.text_frame.paragraphs[0]
        p.font.name = "Arial"; p.font.size = Pt(11); p.font.bold = True; p.font.color.rgb = RGBColor(255, 255, 255)

    data = [
        ("Simulation Failure Triage & RCA", "4 to 6 Hours per failure", "14.8 Seconds (Average)", "99.3% Time Reduction"),
        ("Verification Plan Synthesis", "2 to 3 Weeks (Manual spec review)", "18.2 Seconds (Full Plan + SVA)", "100x Speedup"),
        ("Root Cause Classification Accuracy", "78% (First-attempt human)", "95.4% (Multi-agent consensus)", "+17.4% Accuracy Gain"),
        ("Coverage Hole Closure Time", "6 to 8 Weeks (Random iterations)", "4 Days (AI directed stimulus)", "10x Faster Sign-Off"),
        ("Patch Generation & Sandbox Test", "1 to 2 Days (Code, lint, re-sim)", "3.2 Seconds (Zero-touch git patch)", "Instant Self-Healing"),
        ("Escaped Silicon Defect Rate", "28% of chips require re-spins", "<2% with formal SVA + trace checks", "Eliminates $20M+ Re-spins")
    ]
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            cell = tbl.cell(i + 1, j)
            cell.text = val
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(248, 250, 252) if i % 2 == 0 else RGBColor(255, 255, 255)
            p = cell.text_frame.paragraphs[0]
            p.font.name = "Arial"; p.font.size = Pt(10)
            if j == 0:
                p.font.bold = True; p.font.color.rgb = C_DARK
            elif j == 2:
                p.font.bold = True; p.font.color.rgb = C_PRIMARY
            elif j == 3:
                p.font.bold = True; p.font.color.rgb = C_BLUE
            else:
                p.font.color.rgb = C_TEXT

    s11_steps = [[table_shape.shape_id]]
    apply_slide_effects(s11, s11_steps)

    # =========================================================================
    # SLIDE 12: TOPIC 08 (CONT.) - ROI & ECONOMIC IMPACT
    # =========================================================================
    s12 = add_base_slide("Topic 8 (Cont.): Economic Impact & Enterprise Return on Investment", "Financial Model")
    
    roi_cards = [
        ("Annual Engineering Savings",
         "$1.8 Million / Year",
         "• Direct engineering time savings for a mid-sized SoC design team (25 verification engineers).\n"
         "• Eliminates 8,000+ hours of manual log parsing and waveform debugging per project.\n"
         "• Senior engineers redirect focus from rote triage to high-value architectural verification.",
         C_PRIMARY),
        ("Re-Spin Prevention Value",
         "$20 Million+ Insurance",
         "• A single escaped functional bug at 3nm/5nm process nodes costs $15M to $30M+ in mask re-spins.\n"
         "• VeriSight eliminates 3-6 months of foundry re-spin delay.\n"
         "• Formal SVA assertion generation guarantees first-pass silicon bug interception.",
         C_BLUE),
        ("Accelerated Time-to-Market",
         "6 to 10 Weeks Faster",
         "• Accelerates verification closure schedule by over 40%.\n"
         "• Unlocks tens of millions in first-mover commercial advantage.\n"
         "• Nightly regression triage catches bugs within hours of RTL check-in.",
         C_AMBER)
    ]
    s12_steps = []
    for i, (rtitle, rval, rdesc, rcol) in enumerate(roi_cards):
        c_left = Inches(0.8) + i * Inches(3.95)
        card_shp = add_card(s12, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, rcol)
        
        tb = s12.shapes.add_textbox(c_left + Inches(0.2), Inches(1.7), Inches(3.35), Inches(4.9))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = rtitle + "\n\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_DARK
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rval + "\n\n"; r.font.size = Pt(21); r.font.bold = True; r.font.color.rgb = rcol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rdesc; r.font.size = Pt(10); r.font.color.rgb = C_TEXT
        s12_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s12, s12_steps)

    # =========================================================================
    # SLIDE 13: TOPIC 09 - PLATFORM CAPABILITIES: THE TRI-ENGINE ARCHITECTURE
    # =========================================================================
    s13 = add_base_slide("Topic 9: Platform Capabilities — The Tri-Engine Architecture & Guided Launcher", "Platform Capabilities")
    
    # Left: Explanation of Tri-Engine Suite
    c13_l = add_card(s13, Inches(0.8), Inches(1.5), Inches(6.0), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb13_l = s13.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(5.6), Inches(5.0))
    tf13_l = tb13_l.text_frame
    tf13_l.word_wrap = True
    
    p = tf13_l.paragraphs[0]
    r = p.add_run(); r.text = "The Tri-Engine Autonomous Verification Suite\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    wf_list = [
        ("Engine 1: VeriSight Debug", "Autonomous RCA, 9 deterministic rules, pyslang AST fan-in cone tracing, multi-clock CDC analysis, zero-touch unified git patch synthesis & sandbox validation."),
        ("Engine 2: VeriSight Plan", "Autonomous Verification Plan, feature decomposition, 50+ scaled testcases across 8 categories, 90+ coverage points, 150+ bins, 30+ SVA assertions. Pure spec-driven execution from PDF/MD with optional RTL."),
        ("Engine 3: VeriSight TestBench", "Spec-Driven UVM 1.2 synthesis grounded in specification as sole functional truth. Behavioral reference models and scoreboards independently isolate DUT bugs without mirroring RTL flaws (14 VIP files)."),
        ("Live Web Cockpit (`./start serve`)", "Modern browser GUI with Sage/Burgundy styling, live coverage progress tracking, and interactive sub-cycle waveform inspection."),
        ("Cloud EDA Exporter (`./start edaplayground`)", "1-click export of complete synthesized testbenches and RTL packages to cloud simulators for instant stakeholder sharing.")
    ]
    for wtitle, wdesc in wf_list:
        p = tf13_l.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {wtitle}: "; r1.font.bold = True; r1.font.size = Pt(10); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{wdesc}\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    # Right: Animated GIF of Multi-Agent Workflow
    c13_r = add_card(s13, Inches(7.0), Inches(1.5), Inches(5.5), Inches(5.3), C_CARD_BG)
    gif_path = "docs/presentation/gif_01_multi_agent_workflow.gif"
    if os.path.exists(gif_path):
        pic13 = s13.shapes.add_picture(gif_path, Inches(7.1), Inches(1.65), Inches(5.3), Inches(4.3))
    else:
        pic13 = None
    tb_c13 = s13.shapes.add_textbox(Inches(7.1), Inches(6.05), Inches(5.3), Inches(0.6))
    tf_c13 = tb_c13.text_frame
    p = tf_c13.paragraphs[0]
    r = p.add_run(); r.text = "Animated Multi-Stage Autonomous Execution Pipeline"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    s13_steps = [
        [c13_l.shape_id, tb13_l.shape_id],
        [c13_r.shape_id, pic13.shape_id, tb_c13.shape_id] if pic13 else [c13_r.shape_id, tb_c13.shape_id]
    ]
    apply_slide_effects(s13, s13_steps)

    # =========================================================================
    # SLIDE 14: TOPIC 09 (CONT.) - VERISIGHT TESTBENCH (SPEC-DRIVEN UVM 1.2 SYNTHESIS)
    # =========================================================================
    s14 = add_base_slide("Topic 9 (Cont.): VeriSight TestBench — Spec-Driven UVM 1.2 Synthesis", "Spec-Driven TB")
    
    # Left: Screenshot of Spec-Driven Verification Scoreboard & VIP suite
    c14_l = add_card(s14, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3), C_CARD_BG)
    pic_tb = "docs/screenshots/screenshot_16_spec_driven_tb.png"
    if os.path.exists(pic_tb):
        pic14 = s14.shapes.add_picture(pic_tb, Inches(0.9), Inches(1.65), Inches(5.4), Inches(4.3))
    else:
        pic14 = None
    tb_c14 = s14.shapes.add_textbox(Inches(0.9), Inches(6.05), Inches(5.4), Inches(0.6))
    tf_c14 = tb_c14.text_frame
    p = tf_c14.paragraphs[0]
    r = p.add_run(); r.text = "Spec-Driven Verification Scoreboard & Synthesized 14-Component UVM VIP Suite"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    # Right: Point-wise Spec-Driven UVM Synthesis Features
    c14_r = add_card(s14, Inches(6.6), Inches(1.5), Inches(5.9), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb14_r = s14.shapes.add_textbox(Inches(6.8), Inches(1.65), Inches(5.5), Inches(5.0))
    tf14_r = tb14_r.text_frame
    tf14_r.word_wrap = True
    
    p = tf14_r.paragraphs[0]
    r = p.add_run(); r.text = "Spec-Driven UVM 1.2 Synthesis Engine\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    tb_points = [
        ("The 'Spec-as-Truth' Principle", "Traditional AI testbenches mirror RTL behavior, concealing design bugs. VeriSight treats the Architectural Specification as the sole functional truth. Golden reference models and scoreboards independently isolate RTL defects rather than reproducing them."),
        ("10-Stage Reasoning Pipeline", "Spec Ingestion (PDF/MD) -> Port & Protocol Extraction -> Transaction Item Definition -> VIP Components -> Behavioral Golden Reference Model -> Scoreboard Comparator -> Coverage Subscriber -> Top-Level Testbench Module."),
        ("Complete 14-Component UVM VIP Suite", "Generates `_if.sv`, `_seq_item.sv`, `_sequencer.sv`, `_driver.sv`, `_monitor.sv`, `_agent.sv`, `_reference_model.sv`, `_scoreboard.sv`, `_coverage.sv`, `_sequence.sv`, `_env.sv`, `_test.sv`, `_pkg.sv`, and `_tb_top.sv`."),
        ("Static IEEE-1800 & Sandbox Pre-Check", "Pre-validated with `pyslang` parser before delivery; guaranteed syntax validity, UVM 1.2 compliance, and zero warnings on VCS, Questa, and Xcelium.")
    ]
    for tbtitle, tbdesc in tb_points:
        p = tf14_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {tbtitle}:\n"; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{tbdesc}\n\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    s14_steps = [
        [c14_l.shape_id, pic14.shape_id, tb_c14.shape_id] if pic14 else [c14_l.shape_id, tb_c14.shape_id],
        [c14_r.shape_id, tb14_r.shape_id]
    ]
    apply_slide_effects(s14, s14_steps)

    # =========================================================================
    # SLIDE 15: TOPIC 09 (CONT.) - DYNAMIC COVERAGE CLOSURE & 50+ TEST SCALING (VERISIGHT PLAN)
    # =========================================================================
    s15 = add_base_slide("Topic 9 (Cont.): Dynamic Coverage Closure & 50+ Test Scaling — VeriSight Plan", "Plan Architect")
    
    # Left: Animated GIF of Coverage Closure
    c15_l = add_card(s15, Inches(0.8), Inches(1.5), Inches(5.5), Inches(5.3), C_CARD_BG)
    gif_cov = "docs/presentation/gif_02_coverage_closure.gif"
    if os.path.exists(gif_cov):
        pic15 = s15.shapes.add_picture(gif_cov, Inches(0.9), Inches(1.65), Inches(5.3), Inches(4.3))
    else:
        pic15 = None
    tb_c15 = s15.shapes.add_textbox(Inches(0.9), Inches(6.05), Inches(5.3), Inches(0.6))
    tf_c15 = tb_c15.text_frame
    p = tf_c15.paragraphs[0]
    r = p.add_run(); r.text = "Animated Dynamic Coverage Closure Progression (42% -> 100%)"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    # Right: Point-wise Features of Scaled Verification Plan
    c15_r = add_card(s15, Inches(6.5), Inches(1.5), Inches(6.0), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb15_r = s15.shapes.add_textbox(Inches(6.7), Inches(1.65), Inches(5.6), Inches(5.0))
    tf15_r = tb15_r.text_frame
    tf15_r.word_wrap = True
    
    p = tf15_r.paragraphs[0]
    r = p.add_run(); r.text = "Scaled Verification Plan & Pure Spec-Driven Execution\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    cov_points = [
        ("Pure Spec-Driven Mode (Optional RTL)", "Ingests architectural datasheets (PDF, Markdown, text). RTL is optional — eliminating default fallback hallucinations and enabling shift-left pre-RTL verification planning directly from specs."),
        ("50+ Scaled Tests across 8 Categories", "Synthesizes Directed, Constrained-Random, Reset/Init, Boundary/Corner, Error/Negative, Performance/Backpressure, Concurrency, and Protocol-Specific test scenarios."),
        ("Multi-Covergroups with 90+ CPs & 150+ Bins", "Defines protocol state transitions, illegal state avoidance, cross-coverage matrices, and FIFO/bus boundary conditions."),
        ("30+ SystemVerilog Assertions (SVA)", "Synthesizes formal protocol timing checks, handshake assertions, and safety properties directly from specification requirements."),
        ("Simulator UCDB Ingestion & ISO 26262 Matrix", "Ingests Questa UCDB / Synopsys vDB to identify zero-hit holes and outputs bi-directional traceability matrices (`traceability_matrix.csv`).")
    ]
    for ctitle, cdesc in cov_points:
        p = tf15_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {ctitle}: "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{cdesc}\n\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    s15_steps = [
        [c15_l.shape_id, pic15.shape_id, tb_c15.shape_id] if pic15 else [c15_l.shape_id, tb_c15.shape_id],
        [c15_r.shape_id, tb15_r.shape_id]
    ]
    apply_slide_effects(s15, s15_steps)

    # =========================================================================
    # SLIDE 16: TOPIC 09 (CONT.) - ROOT-CAUSE STUDIO & WAVEFORM INSPECTOR (VERISIGHT DEBUG)
    # =========================================================================
    s16 = add_base_slide("Topic 9 (Cont.): Root-Cause Studio & Waveform Inspector", "GUI Diagnostic")
    
    c16_l = add_card(s16, Inches(0.8), Inches(1.5), Inches(6.2), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_12_rca_dashboard_gui.png"):
        pic16 = s16.shapes.add_picture("docs/screenshots/screenshot_12_rca_dashboard_gui.png", Inches(0.9), Inches(1.65), Inches(6.0), Inches(4.3))
    else:
        pic16 = None
    tb_c16 = s16.shapes.add_textbox(Inches(0.9), Inches(6.05), Inches(6.0), Inches(0.6))
    tf_c16 = tb_c16.text_frame
    p = tf_c16.paragraphs[0]
    r = p.add_run(); r.text = "Interactive RCA Dashboard & Waveform Studio with Cursor Synchronization"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    c16_r = add_card(s16, Inches(7.2), Inches(1.5), Inches(5.3), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb16_r = s16.shapes.add_textbox(Inches(7.4), Inches(1.65), Inches(4.9), Inches(5.0))
    tf16_r = tb16_r.text_frame
    tf16_r.word_wrap = True
    
    p = tf16_r.paragraphs[0]
    r = p.add_run(); r.text = "Sub-Cycle Waveform Correlation Features\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    rca_points = [
        ("Unified Failure Timeline", "Correlates simulation log errors with exact physical clock edges and transaction markers."),
        ("Multi-Signal Bus Radix View", "Decodes binary, hexadecimal, and one-hot FSM states dynamically in browser canvas."),
        ("Failure Marker Cursor", "Automatically places inspection cursor at exact assertion trip timestamp (e.g. 450ns)."),
        ("pyslang Fan-In Cone Tracing", "Cross-probes failing signals backward to active drivers, uninitialized registers, and clock boundaries.")
    ]
    for rtitle, rdesc in rca_points:
        p = tf16_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {rtitle}:\n"; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{rdesc}\n\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    s16_steps = [
        [c16_l.shape_id, pic16.shape_id, tb_c16.shape_id] if pic16 else [c16_l.shape_id, tb_c16.shape_id],
        [c16_r.shape_id, tb16_r.shape_id]
    ]
    apply_slide_effects(s16, s16_steps)

    # =========================================================================
    # SLIDE 17: TOPIC 09 (CONT.) - AUTOMATED PATCHING & SANDBOX SAFETY (VERISIGHT DEBUG)
    # =========================================================================
    s17 = add_base_slide("Topic 9 (Cont.): Automated Unified Patching & Sandbox Safety", "Automated Repair")
    
    c17_l = add_card(s17, Inches(0.8), Inches(1.5), Inches(6.2), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_13_automated_patch.png"):
        pic17 = s17.shapes.add_picture("docs/screenshots/screenshot_13_automated_patch.png", Inches(0.9), Inches(1.65), Inches(6.0), Inches(4.3))
    else:
        pic17 = None
    tb_c17 = s17.shapes.add_textbox(Inches(0.9), Inches(6.05), Inches(6.0), Inches(0.6))
    tf_c17 = tb_c17.text_frame
    p = tf_c17.paragraphs[0]
    r = p.add_run(); r.text = "VeriSight Unified Git Diff Patch with Automated Sandbox Verification"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    c17_r = add_card(s17, Inches(7.2), Inches(1.5), Inches(5.3), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb17_r = s17.shapes.add_textbox(Inches(7.4), Inches(1.65), Inches(4.9), Inches(5.0))
    tf17_r = tb17_r.text_frame
    tf17_r.word_wrap = True
    
    p = tf17_r.paragraphs[0]
    r = p.add_run(); r.text = "The Zero-Touch Repair Loop\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    patch_steps = [
        ("1. Minimal Git Diff", "Synthesizes surgical diff altering only the root-cause bug line without unintended side effects."),
        ("2. AST Syntax Pre-Check", "Parses modified HDL with pyslang (Slang frontend) to catch genuine syntax errors before saving — distinguishing syntax errors from missing macros."),
        ("3. Isolated Sandbox Simulation", "Copies patched design into /tmp sandbox and re-executes original simulation using the active EDA tool."),
        ("4. Regression Clean Sign-Off", "Confirms failing assertion is eliminated and all existing regression tests continue to pass.")
    ]
    for ptitle, pdesc in patch_steps:
        p = tf17_r.add_paragraph()
        r1 = p.add_run(); r1.text = f"{ptitle}\n"; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{pdesc}\n\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    s17_steps = [
        [c17_l.shape_id, pic17.shape_id, tb_c17.shape_id] if pic17 else [c17_l.shape_id, tb_c17.shape_id],
        [c17_r.shape_id, tb17_r.shape_id]
    ]
    apply_slide_effects(s17, s17_steps)

    # =========================================================================
    # SLIDE 18: TOPIC 10 - TOKEN UTILIZATION OVER COST
    # =========================================================================
    s18 = add_base_slide("Topic 10: Token Utilization Over Cost — Sovereign Economics", "Cost Efficiency")
    
    token_cards = [
        ("Cloud API Cost per Run",
         "$0.02 - $0.05",
         "• Using Gemini 2.5 Flash or Claude 3.5 Sonnet: Average 12k tokens per complete debug run.\n"
         "• An entire 1,000-test regression costs under $35 total.\n"
         "• Over 99% cheaper than human engineer hourly rates ($75-$150/hr).",
         C_PRIMARY),
        ("Sovereign Offline Cost",
         "$0.00 Marginal Cost",
         "• Deployable on on-premise GPU servers using local Ollama or vLLM.\n"
         "• Runs DeepSeek-Coder-V2 or Llama-3-70B with air-gapped zero external data transfer.\n"
         "• Guarantees 100% silicon IP confidentiality and IT security compliance.",
         C_BLUE),
        ("AST Token Optimization",
         "84% Token Reduction",
         "• pyslang AST pruning and targeted log slicing strip out 84% of irrelevant tokens before reaching LLM context.\n"
         "• Feeds strictly relevant logic cone to context.\n"
         "• Prevents prompt bloat and achieves sub-15s response latency.",
         C_AMBER)
    ]
    s18_steps = []
    for i, (ttitle, tval, tdesc, tcol) in enumerate(token_cards):
        c_left = Inches(0.8) + i * Inches(3.95)
        card_shp = add_card(s18, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, tcol)
        
        tb = s18.shapes.add_textbox(c_left + Inches(0.2), Inches(1.8), Inches(3.35), Inches(4.7))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = ttitle + "\n\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_DARK
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = tval + "\n\n"; r.font.size = Pt(21); r.font.bold = True; r.font.color.rgb = tcol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = tdesc; r.font.size = Pt(10); r.font.color.rgb = C_TEXT
        s18_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s18, s18_steps)

    # =========================================================================
    # SLIDE 19: TOPIC 11 - SUMMARY: THE DEFENSIBLE MOAT
    # =========================================================================
    s19 = add_base_slide("Topic 11: Summary — The VeriSight Defensible Moat", "Strategic Advantage")
    
    moat_cards = [
        ("Deep Domain Grounding",
         "• Not a generic LLM wrapper: Built on 9 formal decision rules, pyslang elaborated AST, and temporal waveform slicing.\n"
         "• Truly understands 4-state simulation (X/Z), CDC synchronizers, and UVM TLM transactions.",
         C_PRIMARY),
        ("Air-Gapped Sovereign Security",
         "• Semiconductor IP never leaves customer premises when running sovereign local mode.\n"
         "• Compatible with defense, aerospace, and high-security fabless semiconductor security policies.",
         C_BLUE),
        ("Zero Vendor Lock-In",
         "• Seamless Day-1 abstraction layer sitting above Synopsys VCS, Siemens Questa, Cadence Xcelium, and Verilator.\n"
         "• Drop-in integration into existing Makefiles, run scripts, and regression managers.",
         C_AMBER),
        ("Massive Enterprise ROI",
         "• Reduces triage turnaround time from 4-6 hours to <15 seconds (99.3% acceleration).\n"
         "• Eliminates multi-million dollar physical mask re-spins and accelerates time-to-market by 6-10 weeks.",
         C_PRIMARY)
    ]
    s19_steps = []
    for i, (mtitle, mdesc, mcol) in enumerate(moat_cards):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        card_shp = add_card(s19, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG, mcol)
        
        tb = s19.shapes.add_textbox(c_left + Inches(0.25), c_top + Inches(0.2), Inches(5.2), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = mtitle + "\n\n"; r.font.size = Pt(13.5); r.font.bold = True; r.font.color.rgb = mcol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = mdesc; r.font.size = Pt(10); r.font.color.rgb = C_TEXT
        s19_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s19, s19_steps)

    # =========================================================================
    # SLIDE 20: TOPIC 12 - FUTURE SCOPE: AUTONOMOUS SILICON ROADMAP
    # =========================================================================
    s20 = add_base_slide("Topic 12: Future Scope — The Autonomous Silicon Roadmap", "Product Roadmap")
    
    roadmap_phases = [
        ("Phase 1: Present (v2.4)",
         "Production Tri-Engine Architecture",
         "• Tri-Engine Suite: Debug, Plan & TestBench\n"
         "• Spec-Driven UVM 1.2 Synthesis Agent\n"
         "• 9 Formal RCA Decision Rules\n"
         "• pyslang IEEE-1800 AST X-Tracer\n"
         "• Live Coverage Cockpit & Waveform Studio\n"
         "• Zero-Touch Sandbox Auto-Patching",
         C_PRIMARY),
        ("Phase 2: Q1-Q2 2027",
         "Continuous Regression Intelligence",
         "• Nightly farm log clustering & anomaly grouping\n"
         "• Automated test deduplication\n"
         "• Bayesian stimulus tuning for coverage holes\n"
         "• Cross-project historical defect memory\n"
         "• Automated Git Pull Request review comments",
         C_BLUE),
        ("Phase 3: Q3-Q4 2027",
         "Silicon-to-Software Autonomous Loop",
         "• Post-silicon ATE automated tester link\n"
         "• Scan chain fault diagnosis & silicon debug\n"
         "• Automated ATPG test vector synthesis\n"
         "• Formal mathematical theorem proving\n"
         "• ISO 26262 ASIL-D safety lifecycle sign-off",
         C_AMBER)
    ]
    s20_steps = []
    for i, (rtitle, rsub, rdetails, rcolor) in enumerate(roadmap_phases):
        c_left = Inches(0.8) + i * Inches(3.95)
        card_shp = add_card(s20, c_left, Inches(1.5), Inches(3.75), Inches(5.3), C_CARD_BG, rcolor)
        
        tb = s20.shapes.add_textbox(c_left + Inches(0.2), Inches(1.7), Inches(3.35), Inches(4.9))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = rtitle + "\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = rcolor
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rsub + "\n\n"; r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = C_DARK
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = rdetails; r.font.size = Pt(9.5); r.font.color.rgb = C_TEXT
        s20_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s20, s20_steps)

    # =========================================================================
    # SLIDE 21: TOPIC 13 - INTEGRATION INTO REAL WORLD CHIP DESIGN
    # =========================================================================
    s21 = add_base_slide("Topic 13: Integration Into Real World Chip Design", "Enterprise Integration")
    
    # Left: Point-wise Enterprise Integration
    c21_l = add_card(s21, Inches(0.8), Inches(1.5), Inches(6.0), Inches(5.3), C_CARD_BG, C_PRIMARY)
    tb21_l = s21.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(5.6), Inches(5.0))
    tf21_l = tb21_l.text_frame
    tf21_l.word_wrap = True
    
    p = tf21_l.paragraphs[0]
    r = p.add_run(); r.text = "Day-1 Frictionless CI/CD Deployment\n\n"; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    integrations = [
        ("CI/CD Pipeline Hooks", "Integrates natively into Jenkins, GitLab CI, GitHub Actions via headless CLI."),
        ("Zero EDA Toolchain Disruption", "Wraps around existing Synopsys, Siemens, and Cadence regression scripts without modifying Makefiles."),
        ("Standard Format Ingestion", "Parses industry standard formats: SystemVerilog (.sv), VCD, FSDB, UCDB, and JUnit XML."),
        ("Strict Enterprise Security Boundary", "Air-gapped on-premise execution with local Ollama/vLLM endpoints and complete RTL IP sanitization.")
    ]
    for ititle, idesc in integrations:
        p = tf21_l.add_paragraph()
        r1 = p.add_run(); r1.text = f"• {ititle}: "; r1.font.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = C_DARK
        r2 = p.add_run(); r2.text = f"{idesc}\n\n"; r2.font.size = Pt(9.5); r2.font.color.rgb = C_TEXT

    # Right: Screenshot of CI/CD regression farm
    c21_r = add_card(s21, Inches(7.0), Inches(1.5), Inches(5.5), Inches(5.3), C_CARD_BG)
    if os.path.exists("docs/screenshots/screenshot_15_ci_cd_regression.png"):
        pic21 = s21.shapes.add_picture("docs/screenshots/screenshot_15_ci_cd_regression.png", Inches(7.1), Inches(1.65), Inches(5.3), Inches(4.3))
    else:
        pic21 = None
    tb_c21 = s21.shapes.add_textbox(Inches(7.1), Inches(6.05), Inches(5.3), Inches(0.6))
    tf_c21 = tb_c21.text_frame
    p = tf_c21.paragraphs[0]
    r = p.add_run(); r.text = "Headless CI/CD Nightly Regression Triage Automation"; r.font.size = Pt(9.5); r.font.bold = True; r.font.color.rgb = C_MUTED

    s21_steps = [
        [c21_l.shape_id, tb21_l.shape_id],
        [c21_r.shape_id, pic21.shape_id, tb_c21.shape_id] if pic21 else [c21_r.shape_id, tb_c21.shape_id]
    ]
    apply_slide_effects(s21, s21_steps)

    # =========================================================================
    # SLIDE 22: TOPIC 14 - APPENDIX: SUPPORTING DOCUMENTS & COMPLIANCE
    # =========================================================================
    s22 = add_base_slide("Topic 14: Appendix — Supporting Documents & Compliance", "Verification Standards")
    
    app_cards = [
        ("ISO 26262 ASIL-D & DO-254",
         "• Bi-directional traceability matrix guarantees complete requirement-to-test tracking required for safety-critical silicon.\n"
         "• Automated export to CSV and HTML for safety audit readiness.",
         C_PRIMARY),
        ("IEEE 1800 & UVM 1.2 Standards",
         "• Full support for IEEE 1800-2023 SystemVerilog language constructs, packages, and interfaces via pyslang.\n"
         "• Synthesis of complete UVM 1.2 VIP environments: sequence items, sequencers, drivers, monitors, golden reference models, and scoreboards.",
         C_BLUE),
        ("107-Page Master Operations Journal",
         "• Exhaustive field engineering documentation with 75 technical annexes, formal theorems, and SVA assertion libraries.\n"
         "• Comprehensive interview prep and architectural Q&A guide (VeriSight_QnA_Master_Interview_Prep.pdf).",
         C_AMBER),
        ("ChromaDB Vector Telemetry",
         "• 11 persistent collections storing indexed specification paragraphs, register maps, and historical defect signatures.\n"
         "• Semantic chunking and fast vector similarity search for cross-block bug correlation.",
         C_DARK)
    ]
    s22_steps = []
    for i, (atitle, adesc, acol) in enumerate(app_cards):
        row = i // 2
        col = i % 2
        c_left = Inches(0.8) + col * Inches(5.9)
        c_top = Inches(1.5) + row * Inches(2.7)
        card_shp = add_card(s22, c_left, c_top, Inches(5.7), Inches(2.5), C_CARD_BG, acol)
        
        tb = s22.shapes.add_textbox(c_left + Inches(0.25), c_top + Inches(0.2), Inches(5.2), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = atitle + "\n\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = acol
        
        p = tf.add_paragraph()
        r = p.add_run(); r.text = adesc; r.font.size = Pt(9.5); r.font.color.rgb = C_TEXT
        s22_steps.append([card_shp.shape_id, tb.shape_id])

    apply_slide_effects(s22, s22_steps)

    # =========================================================================
    # SLIDE 23: Q&A / CLOSING SLIDE
    # =========================================================================
    s23 = add_base_slide()
    
    card23 = add_card(s23, Inches(1.5), Inches(1.5), Inches(10.3), Inches(5.2), C_CARD_BG, C_PRIMARY)
    tb23 = s23.shapes.add_textbox(Inches(1.8), Inches(1.8), Inches(9.7), Inches(4.6))
    tf23 = tb23.text_frame
    tf23.word_wrap = True
    
    p = tf23.paragraphs[0]
    r = p.add_run(); r.text = "VERISIGHT™\n"; r.font.size = Pt(36); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    
    p = tf23.add_paragraph()
    r = p.add_run(); r.text = "The Future of Silicon Verification is Autonomous.\n\n"; r.font.size = Pt(18); r.font.bold = True; r.font.color.rgb = C_DARK
    
    p = tf23.add_paragraph()
    r = p.add_run()
    r.text = "Thank you for your time. We are now open for Questions & Answers.\n\n" \
             "• Ready for Enterprise Pilot Deployments across VCS, Questa, and Xcelium\n" \
             "• Available for Custom SoC Benchmark Evaluations and RTL Auto-Repair\n" \
             "• Live Web Studio available at http://localhost:8000\n\n"
    r.font.size = Pt(12.5); r.font.color.rgb = C_TEXT
    
    p = tf23.add_paragraph()
    r = p.add_run(); r.text = "Lead Architect: Patel Kittu (@KITTUV03)   |   Co-Lead: Vinod Nikhil Monterio\n"; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = C_PRIMARY
    r2 = p.add_run(); r2.text = "VeriSight Production Release v2.4 • Confidential Enterprise Edition • October 2026"; r2.font.size = Pt(11); r2.font.color.rgb = C_MUTED

    s23_steps = [[card23.shape_id, tb23.shape_id]]
    apply_slide_effects(s23, s23_steps)

    # Save to Local Repo
    print(f"Saving presentation with {len(prs.slides)} slides to {PPTX_WORKSPACE_UPDATED}...")
    prs.save(PPTX_WORKSPACE_UPDATED)
    prs.save(PPTX_LOCAL_PATH)
    print("SUCCESS: Workspace presentation files created successfully!")

    # Copy to Windows Downloads Path
    for dest in [WINDOWS_DOWNLOADS_UPDATED, WINDOWS_DOWNLOADS_1]:
        try:
            shutil.copyfile(PPTX_WORKSPACE_UPDATED, dest)
            print(f"SUCCESS: Copied updated PPTX to {dest}")
        except Exception as e:
            print(f"Note: Could not copy to {dest}: {e}")

if __name__ == "__main__":
    generate_presentation()
