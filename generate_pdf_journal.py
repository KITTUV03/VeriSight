import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

PDF_FILENAME = "VeriSight_Operations_Journal.pdf"

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
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        if self._pageNumber == 1:
            return  # Suppress running header & footer on cover page

        self.saveState()
        # Header
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#0f172a"))
        self.drawString(42, 755, "VERISIGHT™ SILICON VERIFICATION COPILOT")
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawRightString(570, 755, "COMPREHENSIVE TECHNICAL JOURNAL & USER GUIDE")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(42, 747, 570, 747)

        # Footer
        self.line(42, 45, 570, 45)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(42, 32, "Author: Kittu Patel (@KITTUV03) • VeriSight Autonomous Verification Platform")
        self.drawRightString(570, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        PDF_FILENAME,
        pagesize=letter,
        leftMargin=42,
        rightMargin=42,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Palette
    c_primary = colors.HexColor("#0f172a")     # Slate 900
    c_secondary = colors.HexColor("#0284c7")   # Sky 600
    c_accent = colors.HexColor("#0369a1")      # Sky 700
    c_text = colors.HexColor("#1e293b")        # Slate 800
    c_muted = colors.HexColor("#64748b")       # Slate 500
    c_code_bg = colors.HexColor("#f8fafc")     # Slate 50

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=30,
        leading=36,
        textColor=c_primary,
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=18,
        textColor=c_secondary,
        alignment=TA_CENTER
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=c_accent,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'Heading3_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=c_primary,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_text,
        alignment=TA_LEFT,
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.8,
        leading=10.5,
        textColor=colors.HexColor("#0f172a")
    )

    caption_style = ParagraphStyle(
        'Caption_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.8,
        leading=10.5,
        textColor=c_muted,
        alignment=TA_CENTER,
        spaceBefore=3,
        spaceAfter=6
    )

    def callout_box(text, box_type="info"):
        b_color = colors.HexColor("#0284c7") if box_type == "info" else colors.HexColor("#10b981") if box_type == "tip" else colors.HexColor("#f59e0b")
        bg_col = colors.HexColor("#f0f9ff") if box_type == "info" else colors.HexColor("#f0fdf4") if box_type == "tip" else colors.HexColor("#fffbeb")
        prefix = "<b>NOTE:</b> " if box_type == "info" else "<b>VERIFICATION TIP:</b> " if box_type == "tip" else "<b>CRITICAL REQUIREMENT:</b> "
        p = Paragraph(f"{prefix}{text}", body_style)
        t = Table([[p]], colWidths=[528])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_col),
            ('BOX', (0,0), (-1,-1), 0.75, b_color),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        return t

    def code_box(code_text):
        escaped = code_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')
        p = Paragraph(escaped, code_style)
        t = Table([[p]], colWidths=[528])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('LEFTPADDING', (0,0), (-1,-1), 9),
            ('RIGHTPADDING', (0,0), (-1,-1), 9),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        return t

    def screenshot_card(img_path, caption_text, width=515, height=None):
        if not Path(img_path).exists():
            return Paragraph(f"[Image Missing: {img_path}]", caption_style)
        img = Image(img_path, width=width, height=height)
        caption = Paragraph(caption_text, caption_style)
        card_table = Table([[img], [caption]], colWidths=[width])
        card_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        return card_table

    story = []

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 40))

    # Top Badge
    badge_p = Paragraph(
        "<font color='#0284c7'><b>OFFICIAL TECHNICAL JOURNAL & OPERATIONAL FIELD MANUAL</b></font>",
        ParagraphStyle('Badge', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_CENTER)
    )
    badge_t = Table([[badge_p]], colWidths=[528])
    badge_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0f9ff")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0ea5e9")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(badge_t)
    story.append(Spacer(1, 35))

    story.append(Paragraph("VERISIGHT™", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Autonomous Silicon Verification & Failure Debugging Copilot", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Multi-Agent Architecture: Root-Cause Analysis, Automated Fix Generation, Verification Plan Synthesis & Live Coverage Cockpit", ParagraphStyle('Sub2', parent=subtitle_style, fontSize=10, textColor=c_muted)))
    story.append(Spacer(1, 15))

    story.append(HRFlowable(width="80%", thickness=2.5, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=20))

    # Author Box
    author_table_data = [
        [
            Paragraph("<b>Document Title:</b>", body_style),
            Paragraph("VeriSight Comprehensive Technical Journal & User Operation Manual", body_style)
        ],
        [
            Paragraph("<b>Project Name:</b>", body_style),
            Paragraph("<b>VeriSight</b> (AI-Powered RTL/UVM Debugging & Verification Architecture)", body_style)
        ],
        [
            Paragraph("<b>Lead Architect & Author:</b>", body_style),
            Paragraph("<b>Kittu Patel</b> (GitHub: <i>@KITTUV03</i>)", body_style)
        ],
        [
            Paragraph("<b>Release Version:</b>", body_style),
            Paragraph("Production Release v2.4 (Enterprise Multi-Agent Edition)", body_style)
        ],
        [
            Paragraph("<b>Publication Date:</b>", body_style),
            Paragraph("October 20, 2026", body_style)
        ],
        [
            Paragraph("<b>Autonomous Capabilities:</b>", body_style),
            Paragraph("• Multi-Modal Knowledge Extraction Engine (Spec, RTL, TB, Log, Coverage, VCD)<br/>• 9 Formal Decision Rules for Root Cause Classification (TB vs RTL vs Spec vs Unknown)<br/>• 7-Module Exhaustive RTL Analyzer (X-Tracer, CDC, Lint, Protocol, Structural, Misc)<br/>• Automated Fix Generator & Sandbox Syntax/Regression Validator (Unified Git Patches)<br/>• Verification Plan, Functional Coverage (Covergroups) & SVA Suite Synthesis<br/>• ISO 26262 / DO-254 Bi-Directional Traceability Matrix & Dynamic UCDB Cockpit<br/>• One-Click Closed-Loop Simulation Runner (iverilog, verilator, questa, vcs)<br/>• Live Interactive Web Cockpit (FastAPI + Modern Web Dashboard)", body_style)
        ],
        [
            Paragraph("<b>Supported Standards:</b>", body_style),
            Paragraph("IEEE 1800 SystemVerilog, UVM 1.2, SVA (Assertions), VCD/FSDB, PDF/Markdown Specs", body_style)
        ]
    ]
    author_t = Table(author_table_data, colWidths=[140, 388])
    author_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(author_t)

    story.append(Spacer(1, 35))

    confidential_p = Paragraph(
        "<b>TECHNICAL JOURNAL:</b> This document provides an exhaustive, mathematically grounded overview of the VeriSight platform, the fundamental challenges in modern ASIC verification, multi-agent AI architecture, and a complete step-by-step local installation and usage guide. All content is strictly grounded in the verified production codebase.",
        ParagraphStyle('Conf', parent=body_style, fontSize=7.5, leading=10.5, textColor=c_muted, alignment=TA_CENTER)
    )
    story.append(confidential_p)
    story.append(PageBreak())

    # =========================================================================
    # EXECUTIVE SUMMARY & TABLE OF CONTENTS
    # =========================================================================
    story.append(Paragraph("Table of Contents & Technical Overview", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    toc_data = [
        [Paragraph("<b>Chapter</b>", body_style), Paragraph("<b>Core Subject Matter & Operational Scope</b>", body_style), Paragraph("<b>Visual Figures & Screenshots</b>", body_style)],
        [Paragraph("<b>Chapter 1</b>", body_style), Paragraph("Introduction to VeriSight & Industry Verification Bottlenecks", body_style), Paragraph("Industry Pain Points & AI Solution", body_style)],
        [Paragraph("<b>Chapter 2</b>", body_style), Paragraph("The VeriSight Multi-Agent Architecture & Engine Breakdown", body_style), Paragraph("Agent 1 to Agent 5 + Plan + SimRunner", body_style)],
        [Paragraph("<b>Chapter 3</b>", body_style), Paragraph("Interactive Setup Wizard & LLM Credential Configuration", body_style), Paragraph("Screenshots 01 & 02 (Welcome & LLM Setup)", body_style)],
        [Paragraph("<b>Chapter 4</b>", body_style), Paragraph("VeriSight Debug: Root-Cause Analysis & Fix Pipeline", body_style), Paragraph("Screenshots 03 & 04 (Debug Inputs & Results)", body_style)],
        [Paragraph("<b>Chapter 5</b>", body_style), Paragraph("VeriSight Plan: Verification Plan, SVA & Coverage Synthesis", body_style), Paragraph("Screenshots 05 & 06 (Plan Inputs & Results)", body_style)],
        [Paragraph("<b>Chapter 6</b>", body_style), Paragraph("Quick Demos Suite & Headless CLI CI/CD Automation", body_style), Paragraph("Screenshots 07 & 08 (Demos & CLI Exit)", body_style)],
        [Paragraph("<b>Chapter 7</b>", body_style), Paragraph("Dynamic Coverage Closure Cockpit & Live Verification Plan", body_style), Paragraph("Screenshot 09 (Live Cockpit & UCDB)", body_style)],
        [Paragraph("<b>Chapter 8</b>", body_style), Paragraph("Root-Cause Diagnostic Report & Interactive Waveform Studio", body_style), Paragraph("Screenshot 10 (RCA Studio & Waveforms)", body_style)],
        [Paragraph("<b>Chapter 9</b>", body_style), Paragraph("One-Click Closed-Loop Simulator & Automated Code Fixer", body_style), Paragraph("Screenshots 11 & 12 (Sim Runner & Patches)", body_style)],
        [Paragraph("<b>Chapter 10</b>", body_style), Paragraph("FastAPI Live Web Cockpit & Nightly CI/CD Regression Flow", body_style), Paragraph("Screenshots 13 & 14 (Web Cockpit & CI/CD)", body_style)],
        [Paragraph("<b>Chapter 11</b>", body_style), Paragraph("Complete Step-by-Step Local Deployment & Operation Guide", body_style), Paragraph("Terminal Runbook for Engineers", body_style)],
        [Paragraph("<b>Appendix</b>", body_style), Paragraph("Schema Reference, Command Dictionary & Acronym Glossary", body_style), Paragraph("Quick-Reference Cheatsheet", body_style)],
    ]
    toc_table = Table(toc_data, colWidths=[65, 295, 168])
    toc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(toc_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Executive Summary by Author: Kittu Patel", h2_style))
    story.append(Paragraph(
        "Modern Very Large Scale Integration (VLSI) and System-on-Chip (SoC) engineering is constrained by the <b>Functional Verification Crisis</b>. As transistor densities surpass tens of billions of gates, functional verification consumes upwards of <b>70% of entire ASIC project schedules and human engineering bandwidth</b>. Verification engineers are overwhelmed by multi-gigabyte simulation log files, subtle non-deterministic Clock Domain Crossing (CDC) bugs, unpredictable Unknown State ('X') propagations, and weeks spent manually translating ambiguous architectural specifications into SystemVerilog testbenches, covergroups, and temporal assertions.",
        body_style
    ))
    story.append(Paragraph(
        "<b>VeriSight</b> was engineered by <b>Kittu Patel</b> to eliminate these bottlenecks by introducing an autonomous, multi-agent AI copilot designed specifically for silicon verification. Rather than serving as an untrusted, hallucinating generic chat model, VeriSight fuses deterministic Abstract Syntax Tree (AST) parsers, formal gate-level netlist tracing (yosys and x-tracer), static CDC/Lint engines, and multi-model Large Language Models (LLMs) including Google Gemini 2.0 Flash and Anthropic Claude 3.5 Sonnet, anchored by an 11-collection localized ChromaDB vector memory. This journal serves as the definitive reference manual for engineers deploying and operating VeriSight in production ASIC flows.",
        body_style
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 1: INDUSTRY FLAWS & THE VERISIGHT SOLUTION
    # =========================================================================
    story.append(Paragraph("Chapter 1: Industry Verification Flaws & The VeriSight Solution", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "To understand the value of VeriSight, one must examine the critical flaws and manual inefficiencies plaguing contemporary digital hardware verification teams across the semiconductor industry.",
        body_style
    ))

    story.append(Paragraph("The 6 Critical Flaws Faced by Industry Verification Engineers:", h2_style))

    flaws_data = [
        [Paragraph("<b>Industry Verification Flaw / Bottleneck</b>", body_style), Paragraph("<b>Root Cause & Impact on Chip Tapeout</b>", body_style), Paragraph("<b>How VeriSight Solves It</b>", body_style)],
        [
            Paragraph("<b>1. Massive Simulation Log Debugging</b><br/><i>(Needle in a Haystack)</i>", body_style),
            Paragraph("Nightly regressions generate gigabyte-scale logs with thousands of cascading UVM errors. Engineers spend hours manually scrolling to locate the root-cause symptom.", body_style),
            Paragraph("<b>Agent 1 (Knowledge Extraction):</b> Parses multi-GB logs in seconds, filters out downstream cascading noise, isolates primary error timestamps, and correlates log errors to RTL/TB AST nodes.", body_style)
        ],
        [
            Paragraph("<b>2. Ambiguous Specifications & Intent Loss</b><br/><i>(Specification Gap)</i>", body_style),
            Paragraph("Architectural specs (PDF/Word) are written in natural English. Manual translation into test plans loses 20-30% of corner cases, resulting in post-silicon silicon bugs.", body_style),
            Paragraph("<b>VeriSight Plan:</b> Autonomously ingests PDF/MD specs, decomposes functional feature trees, and generates 100% traceable test scenarios and production SystemVerilog covergroups.", body_style)
        ],
        [
            Paragraph("<b>3. Difficult Root-Cause Attribution</b><br/><i>(DUT vs. TB Blame Game)</i>", body_style),
            Paragraph("When a simulation scoreboard flags a mismatch, triage engineers spend days debating whether the fault lies in the RTL DUT, the UVM testbench, or the spec itself.", body_style),
            Paragraph("<b>Agent 2 (Root Cause Classifier):</b> Evaluates 9 deterministic decision rules to classify failure as RTL Bug, TB Bug, Spec Bug, or Unknown with mathematical confidence scores.", body_style)
        ],
        [
            Paragraph("<b>4. The X-Propagation & Uninitialized State Trap</b>", body_style),
            Paragraph("Uninitialized registers output 'X' in simulation. Simulators often mask these bugs via 'X-optimism' or cause unpredictable false mismatches that take weeks to trace.", body_style),
            Paragraph("<b>Agent 3 (X-Tracer Sub-Module):</b> Scans RTL for missing resets and uses yosys netlist synthesis + VCD waveform backward-tracing to identify the exact flip-flop origin.", body_style)
        ],
        [
            Paragraph("<b>5. CDC, Lint, and Structural Deadlock Fatigue</b>", body_style),
            Paragraph("Traditional static EDA tools produce 10,000+ warnings, causing warning fatigue. Subtle FSM deadlocks, unhandled opcodes, and missing synchronizers slip through.", body_style),
            Paragraph("<b>Agent 3 (7 Sub-Modules):</b> Concurrently runs AST Lint, CDC synchronization analysis, FSM reachability graph checks, and bus protocol compliance checkers without noise.", body_style)
        ],
        [
            Paragraph("<b>6. Painful Coverage Closure & Manual Test Authoring</b>", body_style),
            Paragraph("Regressions stall at 85-92% functional coverage. Engineers spend weeks hand-writing directed sequences to hit stubborn corner-case bins before tapeout signoff.", body_style),
            Paragraph("<b>Live Coverage Cockpit:</b> Ingests UCDB databases, highlights unhit coverage bins, and synthesizes directed sequences and SVA properties to close the remaining coverage gap.", body_style)
        ],
    ]
    flaws_table = Table(flaws_data, colWidths=[120, 190, 218])
    flaws_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(flaws_table)
    story.append(Spacer(1, 10))

    story.append(callout_box(
        "By automating both pre-silicon test planning (VeriSight Plan) and post-mortem failure triage (VeriSight Debug), VeriSight shortens verification turnaround time from weeks to minutes, directly protecting multi-million-dollar tapeout schedules.",
        "tip"
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 2: MULTI-AGENT ARCHITECTURE & SUBSYSTEM DEEP DIVE
    # =========================================================================
    story.append(Paragraph("Chapter 2: The VeriSight Multi-Agent Architecture", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "VeriSight is architected as an autonomous multi-agent pipeline where each specialized agent handles a dedicated phase of the verification lifecycle. All agents exchange typed, schema-validated Pydantic data structures, ensuring zero data loss and strict evidence traceability.",
        body_style
    ))

    story.append(Paragraph("Detailed Breakdown of VeriSight Agents & Subsystems:", h2_style))

    # Agent 1
    story.append(Paragraph("1. Agent 1: Knowledge Extraction Engine (<code>agent1_knowledge.py</code>)", h3_style))
    story.append(Paragraph(
        "Agent 1 is the multi-modal sensory organ of VeriSight. It parses and ingests six heterogeneous verification inputs: (1) Architectural Specifications (Markdown, Text, or PDF via <code>pypdf</code>), (2) RTL Source Code (SystemVerilog/Verilog AST, port definitions, parameters), (3) UVM Testbenches (classes, sequences, scoreboards), (4) Simulation Logs (UVM phases, timestamps, assertion errors), (5) Functional Coverage Reports (hit counts, bins), and (6) VCD Waveforms (parsed into compact transitions via <code>vcdvcd</code> or <code>pywellen</code>). Agent 1 synthesizes a unified <code>knowledge.json</code> containing the complete verified context.",
        body_style
    ))

    # Agent 2
    story.append(Paragraph("2. Agent 2: Root Cause Classifier (<code>agent2_classifier.py</code>)", h3_style))
    story.append(Paragraph(
        "Agent 2 determines the true origin of a simulation failure. It applies <b>9 Formal Decision Rules</b> in strict hierarchical order: Case 1: Driver incorrect stimulus &rarr; TB Bug; Case 2: Monitor sampling error &rarr; TB Bug; Case 3: Scoreboard prediction error &rarr; TB Bug; Case 4: Coverage model bug &rarr; TB Bug; Case 5: Assertions contradict spec &rarr; TB Bug; Case 6: RTL violates spec &rarr; RTL Bug; Case 7: RTL outputs X &rarr; RTL Bug; Case 8: Protocol violated in RTL &rarr; RTL Bug; Case 9: Spec contradicts itself &rarr; Spec Bug. It produces a <code>Classification</code> with confidence (0-100%) and multi-hop evidence chains linking symptoms directly to root causes.",
        body_style
    ))

    # Agent 3
    story.append(Paragraph("3. Agent 3: RTL Root Cause Analyzer (<code>agent3_rtl_analyzer.py</code>)", h3_style))
    story.append(Paragraph(
        "When a failure is classified as an RTL Bug, Agent 3 executes an exhaustive diagnostic sweep across <b>7 deep sub-modules</b>: (1) <i>X-Tracer</i> (static reset checking and backward gate-level VCD tracing via yosys and x-tracer), (2) <i>Functional Analyzer</i> (spec vs RTL math discrepancies), (3) <i>CDC Analyzer</i> (asynchronous clocks, missing 2-FF synchronizers, metastability risks), (4) <i>Lint Analyzer</i> (combinational loops, latches, unassigned nets), (5) <i>Structural Analyzer</i> (FSM dead-state detection, unreachable transitions), (6) <i>Protocol Compliance</i> (APB, AHB, AXI, Wishbone, SPI, I2C bus handshaking), and (7) <i>Misc Analyzer</i> (timing race conditions and reset sequencing).",
        body_style
    ))

    # Agent 4
    story.append(Paragraph("4. Agent 4: Multi-Format Report Generator (<code>agent4_reporter.py</code>)", h3_style))
    story.append(Paragraph(
        "Agent 4 compiles the findings into four production-grade deliverables: <code>report.html</code> (interactive visual dashboard with collapsible traces and Waveform Studio), <code>report.md</code> (detailed engineering markdown for Git wikis), <code>error.json</code> (strict schema-validated record for CI/CD bug trackers), and <code>summary.txt</code> (executive briefing for standup meetings). It also indexes the entire session into ChromaDB for future RAG retrieval.",
        body_style
    ))

    # Agent 5
    story.append(Paragraph("5. Agent 5: Automated Fix Generator & Validator (<code>agent5_fix_generator.py</code>)", h3_style))
    story.append(Paragraph(
        "Agent 5 synthesizes a concrete, minimal source-code fix. Governed by strict non-hallucination rules, it modifies the smallest possible code region, never invents signal names, and outputs a standard unified Git diff patch (<code>proposed.patch</code>). It validates the patch in an isolated sandbox with iverilog/slang syntax checkers and regression re-runs before recommending it.",
        body_style
    ))

    # Plan Engine
    story.append(Paragraph("6. VeriSight Plan: Autonomous Verification Plan Architect (<code>verisight/plan/</code>)", h3_style))
    story.append(Paragraph(
        "Decomposes natural language specifications into hierarchical feature trees, formulates directed and constrained-random test cases, generates production SystemVerilog covergroups (<code>coverage_model.sv</code>), synthesizes temporal SVA assertions (<code>dut_assertions.sv</code>), builds an ISO 26262/DO-254 bi-directional traceability matrix, and provides a dynamic UCDB coverage cockpit.",
        body_style
    ))

    # Sim Runner & Web Server
    story.append(Paragraph("7. Sim Runner & Web Cockpit (<code>sim_runner.py</code> & <code>server/app.py</code>)", h3_style))
    story.append(Paragraph(
        "The One-Click Simulation Runner compiles and runs testbenches under open-source (iverilog, verilator) or commercial (questa, vcs) simulators with automatic VCD waveform dumping. The FastAPI Web Cockpit provides a responsive web server on localhost:8000 for live regression monitoring and triage.",
        body_style
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 3: WIZARD & LLM CONFIGURATION (SCREENSHOTS 1 & 2)
    # =========================================================================
    story.append(Paragraph("Chapter 3: Interactive Setup Wizard & LLM Configuration", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "To provide effortless usability without requiring engineers to memorize complex CLI arguments, author <b>Kittu Patel</b> created the VeriSight Interactive Guided Wizard. The wizard can be launched using <code>./start.sh</code>, <code>python start.py</code>, or <code>python main.py start</code>.",
        body_style
    ))

    # SCREENSHOT 1
    story.append(screenshot_card(
        "docs/screenshots/screenshot_01_welcome_menu.png",
        "Figure 3.1: VeriSight Interactive Guided Wizard — Main Welcome Banner & Step 1 Workflow Selection Menu",
        width=515,
        height=195
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Workflow Selection Pathways in Step 1:", h2_style))
    story.append(Paragraph("• <b>[1] VeriSight Debug:</b> Autonomous Root-Cause Analysis pipeline for simulation failures, UVM errors, and RTL bugs.", bullet_style))
    story.append(Paragraph("• <b>[2] VeriSight Plan:</b> Verification & Architecture Plan generator to ingest specifications and synthesize covergroups and SVA.", bullet_style))
    story.append(Paragraph("• <b>[3] Quick Demos:</b> 1-click instant demonstration runs on pre-packaged ALU and FIFO designs.", bullet_style))
    story.append(Paragraph("• <b>[4] Exit:</b> Terminates the interactive session cleanly and displays advanced headless CLI commands.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 2
    story.append(screenshot_card(
        "docs/screenshots/screenshot_02_llm_config.png",
        "Figure 3.2: VeriSight LLM Configuration Screen — Auto-Detection of Environment Credentials & Mode Selection",
        width=515,
        height=228
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Supported LLM Execution Modes:", h2_style))
    story.append(Paragraph("• <b>Google Gemini (Default):</b> Uses <code>gemini-2.0-flash</code> with ultra-fast latency and 1-million token context.", bullet_style))
    story.append(Paragraph("• <b>Anthropic Claude:</b> Uses <code>claude-sonnet-5</code> or <code>claude-3-5-sonnet</code> for deep HDL logic reasoning.", bullet_style))
    story.append(Paragraph("• <b>Offline Deterministic Mode (Option 5):</b> Zero cloud API calls. Disables LLM queries and executes 100% locally using deterministic AST parsers, CDC checkers, and gate-level X-tracing. Strictly enforced for air-gapped defense and confidential foundry environments.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 4: VERISIGHT DEBUG PIPELINE (SCREENSHOTS 3 & 4)
    # =========================================================================
    story.append(Paragraph("Chapter 4: VeriSight Debug — Root-Cause Analysis & Fix Pipeline", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "Selecting option <code>[1] VeriSight Debug</code> launches the autonomous diagnostic engine. The wizard guides the engineer through input gathering with intelligent path normalization and fuzzy auto-detection:",
        body_style
    ))

    # SCREENSHOT 3
    story.append(screenshot_card(
        "docs/screenshots/screenshot_03_agent1_debug_inputs.png",
        "Figure 4.1: Agent 1 Input Prompting — Ingestion of Simulation Log, RTL Sources, UVM Testbench, and Specification",
        width=515,
        height=185
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("The 5-Phase Autonomous Diagnostic Sweep:", h2_style))
    story.append(Paragraph("1. <b>Tokenized Ingestion:</b> Reads simulation logs, isolates first-error timestamps, and links failures to AST declarations.", bullet_style))
    story.append(Paragraph("2. <b>Static Analyzer Suite:</b> Concurrently runs CDC analysis, AST linting, protocol handshaking, and gate-level X-tracing.", bullet_style))
    story.append(Paragraph("3. <b>RAG Context Retrieval:</b> Queries ChromaDB vector database for known failure signatures and historical signoff errata.", bullet_style))
    story.append(Paragraph("4. <b>Multi-Agent LLM Synthesis:</b> Applies the 9 decision rules to classify the root cause with confidence scoring.", bullet_style))
    story.append(Paragraph("5. <b>Fix Generation:</b> Synthesizes a unified Git diff patch (<code>proposed.patch</code>) and validates it in an isolated sandbox.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 4
    story.append(screenshot_card(
        "docs/screenshots/screenshot_04_agent1_debug_results.png",
        "Figure 4.2: Agent 1 Diagnostic Results — Root Cause Classification, Confidence Percentage, and Generated Deliverables",
        width=515,
        height=310
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Diagnostic Output Artifacts (output/custom_debug/):", h2_style))
    story.append(Paragraph("• <b>report.html:</b> Interactive HTML diagnostic dashboard featuring collapsible evidence chains and Waveform Studio.", bullet_style))
    story.append(Paragraph("• <b>report.md:</b> Detailed markdown technical report for design review documentation and Git commits.", bullet_style))
    story.append(Paragraph("• <b>error.json:</b> Schema-validated JSON root-cause record for automated Jira / Bugzilla issue logging.", bullet_style))
    story.append(Paragraph("• <b>fix/proposed.patch:</b> Production-ready unified git diff patch directly applicable via <code>git apply</code>.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 5: VERISIGHT PLAN (SCREENSHOTS 5 & 6)
    # =========================================================================
    story.append(Paragraph("Chapter 5: VeriSight Plan — Verification Plan & Suite Architect", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "Selecting option <code>[2] VeriSight Plan</code> activates the verification architecture synthesizer. In traditional ASIC development, converting a 100-page PRD into verification covergroups and SVA assertions takes weeks of manual work. VeriSight Plan automates this in minutes.",
        body_style
    ))

    # SCREENSHOT 5
    story.append(screenshot_card(
        "docs/screenshots/screenshot_05_agent2_plan_inputs.png",
        "Figure 5.1: VeriSight Plan Input Gathering — Specification Document (PDF/MD) and RTL Ingestion",
        width=515,
        height=150
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Key Capabilities of VeriSight Plan:", h2_style))
    story.append(Paragraph("• <b>Multi-Format Spec Ingestion:</b> Natively extracts text, tables, register maps, and operational modes from PDF, Markdown, and Text specifications.", bullet_style))
    story.append(Paragraph("• <b>RTL Port Grounding:</b> Parses RTL top-level port interfaces (e.g. <code>alu.sv</code>) to ensure all generated covergroups and assertions match real hardware signal names exactly.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 6
    story.append(screenshot_card(
        "docs/screenshots/screenshot_06_agent2_plan_results.png",
        "Figure 5.2: VeriSight Plan Synthesis Results — Decomposed Features, Test Scenarios, Coverage Models & SVA Suite",
        width=515,
        height=330
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Deliverables Generated in output/verification_plan/:", h2_style))
    story.append(Paragraph("• <b>verification_plan.html:</b> Interactive HTML dashboard with live search filtering, requirement heatmaps, and coverage progress bars.", bullet_style))
    story.append(Paragraph("• <b>coverage_model.sv:</b> Complete SystemVerilog functional coverage package containing parameterized <code>covergroup</code> models and multi-variable cross bins.", bullet_style))
    story.append(Paragraph("• <b>dut_assertions.sv:</b> Formal SystemVerilog Assertions (SVA) suite ready for direct <code>bind</code> instantiation onto the DUT top level.", bullet_style))
    story.append(Paragraph("• <b>traceability_matrix.csv:</b> ISO 26262 (ASIL-D) and DO-254 compliant bi-directional traceability spreadsheet.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 6: QUICK DEMOS & HEADLESS CLI (SCREENSHOTS 7 & 8)
    # =========================================================================
    story.append(Paragraph("Chapter 6: Quick Demos Suite & Headless CI/CD Automation", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "To allow engineers and verification leads to evaluate VeriSight instantly without typing file paths, author <b>Kittu Patel</b> embedded the <b>Quick Demos Suite</b> into Option 3 of the setup wizard.",
        body_style
    ))

    # SCREENSHOT 7
    story.append(screenshot_card(
        "docs/screenshots/screenshot_07_option3_demos.png",
        "Figure 6.1: Option 3 Quick Demos Menu — Instant 1-Click Verification & Debug Demos for ALU and FIFO Designs",
        width=515,
        height=195
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("The 4 Pre-Packaged Demonstrations:", h2_style))
    story.append(Paragraph("• <b>[1] ALU Debug Demo:</b> Detects a missing reset bug in an arithmetic unit causing uninitialized 'X' outputs.", bullet_style))
    story.append(Paragraph("• <b>[2] FIFO Debug Demo:</b> Isolates a read pointer underflow boundary condition in a synchronous FIFO memory.", bullet_style))
    story.append(Paragraph("• <b>[3] ALU Plan Demo:</b> Synthesizes 22 features, 45 test cases, 12 covergroups, and 23 SVA properties for the ALU.", bullet_style))
    story.append(Paragraph("• <b>[4] FIFO Plan Demo:</b> Generates a full test plan covering full/empty states, burst transfers, and watermark assertions.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 8
    story.append(screenshot_card(
        "docs/screenshots/screenshot_08_cli_and_exit.png",
        "Figure 6.2: Option 4 Exit Screen — Clean Termination & Direct CLI Power Commands for Nightly Regressions",
        width=515,
        height=285
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Headless CLI Commands for Automation:", h2_style))
    story.append(code_box(
        "# Run Debug Pipeline Headlessly\n"
        "python main.py --spec examples/specs/alu_spec.md --rtl examples/rtl/ --log examples/logs/sim.log --output output/run1\n\n"
        "# Run Plan Synthesizer Headlessly\n"
        "python main.py plan --spec examples/specs/alu_spec.md --rtl examples/rtl/ --output output/vplan1"
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 7: LIVE COVERAGE COCKPIT (SCREENSHOT 9)
    # =========================================================================
    story.append(Paragraph("Chapter 7: Dynamic Coverage Closure Cockpit & Verification Plan", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "The generated <code>verification_plan.html</code> serves as an interactive <b>Live Coverage Cockpit</b>. It bridges the gap between planned verification goals and actual simulator coverage databases (UCDB / Synopsys vDB):",
        body_style
    ))

    # SCREENSHOT 9
    story.append(screenshot_card(
        "docs/screenshots/screenshot_09_vplan_cockpit.png",
        "Figure 7.1: VeriSight Live Coverage Cockpit GUI — Dynamic Planned vs. Actual UCDB Simulation Coverage Progress Bars",
        width=515,
        height=355
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Key Cockpit Innovations:", h2_style))
    story.append(Paragraph("• <b>Live UCDB Ingestion:</b> Ingests simulator coverage databases and maps actual hit counts against planned features.", bullet_style))
    story.append(Paragraph("• <b>Planned vs. Actual Delta Tracking:</b> Highlights unhit coverage bins in amber/red with percentage completion.", bullet_style))
    story.append(Paragraph("• <b>AI Directed Stimulus Generator:</b> Features an interactive <i>'Generate Directed Stimulus'</i> button to autonomously synthesize UVM sequences that specifically target remaining unhit bins.", bullet_style))
    story.append(Paragraph("• <b>Bi-Directional Traceability:</b> Mappings satisfy ISO 26262 ASIL-D and DO-254 safety signoff requirements.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 8: RCA DIAGNOSTIC REPORT & WAVEFORM STUDIO (SCREENSHOT 10)
    # =========================================================================
    story.append(Paragraph("Chapter 8: Root-Cause Diagnostic Report & Waveform Studio", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "The generated <code>report.html</code> is an interactive single-page diagnostic dashboard featuring the built-in <b>Waveform Studio</b>, allowing engineers to inspect timing transitions directly in their browser without launching heavyweight GUI waveform viewers:",
        body_style
    ))

    # SCREENSHOT 10
    story.append(screenshot_card(
        "docs/screenshots/screenshot_10_rca_dashboard.png",
        "Figure 8.1: VeriSight RCA Diagnostic Dashboard & Waveform Studio GUI — Time-Correlated Evidence and Bus Failure Cursor",
        width=515,
        height=355
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Key Diagnostic Features in report.html:", h2_style))
    story.append(Paragraph("• <b>Root Cause Classification & Confidence Gauge:</b> Instantly displays bug type (RTL Bug, TB Bug, Spec Bug) and confidence.", bullet_style))
    story.append(Paragraph("• <b>Time-Correlated Waveform Studio:</b> Automatically extracts VCD waveform signals near failure timestamps and displays them with color-coded signal transitions and failure cursors.", bullet_style))
    story.append(Paragraph("• <b>7-Submodule Deep Findings Tab:</b> Collapsible inspection tabs for X-Tracer, CDC, Lint, Protocol, Structural, and Misc findings.", bullet_style))
    story.append(Paragraph("• <b>Interactive Patch Viewer:</b> Displays the proposed unified git patch with single-click clipboard copying.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 9: SIM RUNNER & AUTOMATED FIX (SCREENSHOTS 11 & 12)
    # =========================================================================
    story.append(Paragraph("Chapter 9: One-Click Sim Runner & Automated Fix Generator", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "VeriSight provides closed-loop simulation and automated repair capabilities, turning post-mortem analysis into an active, self-correcting verification environment:",
        body_style
    ))

    # SCREENSHOT 11
    story.append(screenshot_card(
        "docs/screenshots/screenshot_11_sim_runner.png",
        "Figure 9.1: One-Click Closed-Loop Simulation Runner — Compilation, Test Execution, and Automated VCD Waveform Dumping",
        width=515,
        height=275
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("One-Click Simulation Runner (<code>sim_runner.py</code>):", h2_style))
    story.append(Paragraph("• Executes simulations via <code>python main.py simulate --rtl &lt;dir&gt; --tb &lt;dir&gt;</code> without requiring manual Makefiles.", bullet_style))
    story.append(Paragraph("• Supports Icarus Verilog (<code>iverilog</code>), Verilator, Siemens Questa, and Synopsys VCS.", bullet_style))
    story.append(Paragraph("• Automatically injects <code>$dumpfile</code> and <code>$dumpvars</code> wrapper modules to guarantee VCD waveform capture.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 12
    story.append(screenshot_card(
        "docs/screenshots/screenshot_12_automated_fix.png",
        "Figure 9.2: Agent 5 Automated Fix Generator & Sandbox Validation — Synthesized Patch, Syntax Check & Regression Verification",
        width=515,
        height=275
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Automated Fix Generator & Sandbox Validation (Agent 5):", h2_style))
    story.append(Paragraph("• Synthesizes unified git diff patches (<code>output/fix/proposed.patch</code>) grounded strictly in verified evidence.", bullet_style))
    story.append(Paragraph("• Compiles the patched RTL in an isolated sandbox to verify syntax correctness before presenting it to the engineer.", bullet_style))
    story.append(Paragraph("• Re-runs the closed-loop testbench to prove that the scoreboard mismatch is 100% resolved without introducing regressions.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 10: WEB COCKPIT & CI/CD (SCREENSHOTS 13 & 14)
    # =========================================================================
    story.append(Paragraph("Chapter 10: Live Web Cockpit & Nightly CI/CD Regression", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "For interactive team collaboration and automated enterprise regression farms, VeriSight provides both a real-time web server and non-blocking headless execution modes:",
        body_style
    ))

    # SCREENSHOT 13
    story.append(screenshot_card(
        "docs/screenshots/screenshot_13_web_cockpit_server.png",
        "Figure 10.1: Live Web Cockpit Server (FastAPI + Uvicorn) — Localhost Dashboard Server with Real-Time REST APIs",
        width=515,
        height=230
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("FastAPI Live Web Cockpit Server (<code>server/app.py</code>):", h2_style))
    story.append(Paragraph("• Launched with a single command: <code>python main.py serve --host 127.0.0.1 --port 8000</code>.", bullet_style))
    story.append(Paragraph("• Serves a modern single-page web app (SPA) for triggering simulations, viewing reports, and monitoring engine status.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 14
    story.append(screenshot_card(
        "docs/screenshots/screenshot_14_ci_cd_pipeline.png",
        "Figure 10.2: Headless CI/CD Nightly Regression Pipeline — Automated Log Triage, Classification, and Zero-Error Exit Codes",
        width=515,
        height=165
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Headless CI/CD Nightly Regression Integration:", h2_style))
    story.append(Paragraph("• Integrates seamlessly into GitHub Actions, GitLab CI, and LSF/Slurm compute clusters.", bullet_style))
    story.append(Paragraph("• Parses gigabyte regression logs non-interactively and outputs structured JUnit XML and JSON summaries.", bullet_style))
    story.append(Paragraph("• Completes automated triage in seconds, delivering actionable root-cause summaries before engineers start their workday.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 11: STEP-BY-STEP LOCAL USER GUIDE
    # =========================================================================
    story.append(Paragraph("Chapter 11: Step-by-Step Local Deployment & User Guide", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        "This chapter provides an exhaustive, step-by-step runbook for verification engineers installing and running VeriSight on their local Linux workstation, WSL2 instance, or macOS development machine.",
        body_style
    ))

    story.append(Paragraph("Step 1: System Prerequisites", h2_style))
    story.append(Paragraph("Ensure your local machine has Python 3.10+ and Git installed. For local simulation and waveform dumping, install Icarus Verilog:", body_style))
    story.append(code_box(
        "# Ubuntu / Debian / WSL2:\n"
        "sudo apt update && sudo apt install -y python3 python3-pip python3-venv git iverilog\n\n"
        "# macOS (via Homebrew):\n"
        "brew install python git icarus-verilog"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Step 2: Clone Repository & Virtual Environment Setup", h2_style))
    story.append(Paragraph("Clone the official repository and set up an isolated Python virtual environment:", body_style))
    story.append(code_box(
        "git clone https://github.com/KITTUV03/VeriSight.git\n"
        "cd VeriSight\n\n"
        "# Create and activate virtual environment\n"
        "python3 -m venv .venv\n"
        "source .venv/bin/activate\n\n"
        "# Install VeriSight in editable mode with development dependencies\n"
        "pip install -e '.[dev]'\n"
        "pip install pypdf reportlab"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Step 3: Configure LLM API Keys", h2_style))
    story.append(Paragraph("Set your preferred LLM provider API key in your shell or copy <code>.env.example</code> to <code>.env</code>:", body_style))
    story.append(code_box(
        "# Option A: Google Gemini (Recommended Default)\n"
        "export GEMINI_API_KEY='AIzaSy...your_gemini_key_here'\n\n"
        "# Option B: Anthropic Claude\n"
        "export ANTHROPIC_API_KEY='sk-ant...your_claude_key_here'\n\n"
        "# Option C: Offline Air-Gapped Mode (No API key needed!)"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Step 4: Launch Interactive Guided Wizard", h2_style))
    story.append(Paragraph("Launch the guided wizard using the native executable shell script or Python entry point:", body_style))
    story.append(code_box(
        "./start.sh          # Native executable bash launcher\n"
        "# or:\n"
        "python main.py start"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Step 5: Run Instant Pre-Packaged Demos", h2_style))
    story.append(Paragraph("To verify installation instantly, select option <code>[3] Quick Demos</code> in the wizard, or run directly via CLI:", body_style))
    story.append(code_box(
        "# Run ALU Root-Cause Debug Demo:\n"
        "python main.py --spec examples/specs/alu_spec.md --rtl examples/rtl/ --log examples/logs/sim.log --output output/custom_debug\n\n"
        "# Run ALU Verification Plan & Coverage Synthesis Demo:\n"
        "python main.py plan --spec examples/specs/alu_spec.md --rtl examples/rtl/ --output output/verification_plan"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Step 6: Run One-Click Closed-Loop Simulation", h2_style))
    story.append(Paragraph("Compile, simulate, dump waveforms, and debug your RTL in a single automated command:", body_style))
    story.append(code_box(
        "python main.py simulate --rtl examples/rtl/alu.sv --tb examples/tb/alu_tb.sv --output output/closed_loop"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Step 7: Launch Live Interactive Web Cockpit", h2_style))
    story.append(Paragraph("Start the FastAPI web dashboard to view interactive reports, coverage progress, and waveforms in your browser:", body_style))
    story.append(code_box(
        "python main.py serve --port 8000\n"
        "# Open http://localhost:8000 in Chrome or Firefox"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Step 8: Review & Apply Generated Patches", h2_style))
    story.append(Paragraph("Inspect the machine-generated fix and apply it cleanly to your git repository:", body_style))
    story.append(code_box(
        "cat output/custom_debug/fix/proposed.patch\n"
        "git apply output/custom_debug/fix/proposed.patch"
    ))
    story.append(PageBreak())

    # =========================================================================
    # APPENDIX: SCHEMA REFERENCE & GLOSSARY
    # =========================================================================
    story.append(Paragraph("Appendix: Reference Schemas, Commands & Glossary", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph("Comprehensive Command-Line Dictionary", h2_style))

    cheatsheet_data = [
        [Paragraph("<b>Operational Goal</b>", body_style), Paragraph("<b>Command-Line Syntax</b>", body_style)],
        [Paragraph("Launch Interactive Setup Wizard", body_style), Paragraph("<code>./start.sh</code> &nbsp;or&nbsp; <code>python main.py start</code>", body_style)],
        [Paragraph("Run Simulation Failure RCA", body_style), Paragraph("<code>python main.py --spec &lt;spec&gt; --rtl &lt;rtl&gt; --log &lt;log&gt; --output &lt;dir&gt;</code>", body_style)],
        [Paragraph("Synthesize Verification Plan & SVA", body_style), Paragraph("<code>python main.py plan --spec &lt;spec&gt; --rtl &lt;rtl&gt; --output &lt;dir&gt;</code>", body_style)],
        [Paragraph("Execute One-Click Simulation", body_style), Paragraph("<code>python main.py simulate --rtl &lt;rtl&gt; --tb &lt;tb&gt; --simulator iverilog</code>", body_style)],
        [Paragraph("Start Live Web Cockpit Server", body_style), Paragraph("<code>python main.py serve --host 127.0.0.1 --port 8000</code>", body_style)],
        [Paragraph("Run in 100% Offline Air-Gapped Mode", body_style), Paragraph("Select option 5 in wizard, or pass <code>--no-rag</code> without API keys", body_style)],
        [Paragraph("Apply Generated RTL Code Fix", body_style), Paragraph("<code>git apply &lt;output_dir&gt;/fix/proposed.patch</code>", body_style)],
        [Paragraph("Execute Pytest Unit Test Suite", body_style), Paragraph("<code>python -m pytest tests/ -v</code>", body_style)],
    ]
    cheat_t = Table(cheatsheet_data, colWidths=[180, 348])
    cheat_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(cheat_t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Semiconductor Verification Acronym Glossary", h2_style))

    acronym_data = [
        [Paragraph("<b>Acronym</b>", body_style), Paragraph("<b>Full Definition & Verification Context</b>", body_style)],
        [Paragraph("<b>ASIC</b>", body_style), Paragraph("Application-Specific Integrated Circuit — Custom-designed silicon microchip.", body_style)],
        [Paragraph("<b>AST</b>", body_style), Paragraph("Abstract Syntax Tree — Hierarchical syntactic tree representation of HDL code.", body_style)],
        [Paragraph("<b>CDC</b>", body_style), Paragraph("Clock Domain Crossing — Signals transmitted between asynchronous clock regimes.", body_style)],
        [Paragraph("<b>DUT</b>", body_style), Paragraph("Design Under Test — The target hardware module being simulated or verified.", body_style)],
        [Paragraph("<b>RCA</b>", body_style), Paragraph("Root Cause Analysis — Algorithmic isolation of the primary source of a silicon defect.", body_style)],
        [Paragraph("<b>RAG</b>", body_style), Paragraph("Retrieval-Augmented Generation — Semantic context injection from vector databases.", body_style)],
        [Paragraph("<b>SVA</b>", body_style), Paragraph("SystemVerilog Assertions — Formal temporal logic properties verifying protocol rules.", body_style)],
        [Paragraph("<b>UCDB</b>", body_style), Paragraph("Unified Coverage Database — Industry standard format for simulator coverage results.", body_style)],
        [Paragraph("<b>UVM</b>", body_style), Paragraph("Universal Verification Methodology — IEEE 1800.2 standard class library for testbenches.", body_style)],
        [Paragraph("<b>VCD</b>", body_style), Paragraph("Value Change Dump — ASCII standard waveform transition format for digital logic.", body_style)],
        [Paragraph("<b>X-State</b>", body_style), Paragraph("Unknown Logic State — Uninitialized logic value in 4-state simulation ('X').", body_style)],
    ]
    acronym_t = Table(acronym_data, colWidths=[90, 438])
    acronym_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(acronym_t)
    story.append(Spacer(1, 15))

    # Concluding signature
    concl_p = Paragraph(
        "<b>VeriSight™ Autonomous Silicon Verification & Failure Debugging Copilot</b><br/>"
        "Engineered by <b>Kittu Patel</b> (@KITTUV03) • All Rights Reserved • 2026",
        ParagraphStyle('Concl', parent=body_style, fontSize=8, leading=11, alignment=TA_CENTER, textColor=c_muted)
    )
    story.append(concl_p)

    print("Building multi-page PDF document...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"SUCCESS: {PDF_FILENAME} successfully built!")

if __name__ == '__main__':
    build_pdf()
