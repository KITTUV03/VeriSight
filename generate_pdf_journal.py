import os
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
        # Running Header
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#0f172a"))
        self.drawString(42, 755, "VERISIGHT™ SILICON VERIFICATION COPILOT")
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawRightString(570, 755, "MASTER TECHNICAL JOURNAL & FIELD MANUAL")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(42, 747, 570, 747)

        # Running Footer
        self.line(42, 45, 570, 45)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(42, 32, "Author: Kittu Patel (@KITTUV03) • VeriSight Autonomous Verification Architecture")
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
        fontSize=26,
        leading=32,
        textColor=c_primary,
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        alignment=TA_CENTER
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14.5,
        textColor=c_accent,
        spaceBefore=9,
        spaceAfter=3,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'Heading3_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.2,
        leading=12.5,
        textColor=c_primary,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_text,
        alignment=TA_LEFT,
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2.5
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.0,
        leading=9.2,
        textColor=colors.HexColor("#0f172a")
    )

    caption_style = ParagraphStyle(
        'Caption_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=10,
        textColor=c_muted,
        alignment=TA_CENTER,
        spaceBefore=3,
        spaceAfter=5
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
            ('LEFTPADDING', (0,0), (-1,-1), 9),
            ('RIGHTPADDING', (0,0), (-1,-1), 9),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        return t

    def code_box(code_text):
        escaped = code_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')
        p = Paragraph(escaped, code_style)
        t = Table([[p]], colWidths=[528])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        return t

    def screenshot_card(img_path, caption_text, max_width=515, max_height=260, width=None, height=None):
        if width is not None:
            max_width = width
        if height is not None:
            max_height = height
        if not Path(img_path).exists():
            return Paragraph(f"[Image Missing: {img_path}]", caption_style)
        try:
            from PIL import Image as PILImage
            with PILImage.open(img_path) as im:
                orig_w, orig_h = im.size
            scale = min(max_width / orig_w, max_height / orig_h)
            w = orig_w * scale
            h = orig_h * scale
        except Exception:
            w, h = max_width, 240
        img = Image(img_path, width=w, height=h)
        caption = Paragraph(caption_text, caption_style)
        card_table = Table([[img], [caption]], colWidths=[w])
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
    # PAGE 1: COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 35))

    badge_p = Paragraph(
        "<font color='#0284c7'><b>OFFICIAL PUBLICATION • MASTER TECHNICAL JOURNAL & FIELD ENGINEERING MANUAL</b></font>",
        ParagraphStyle('Badge', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, alignment=TA_CENTER)
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
    story.append(Spacer(1, 30))

    story.append(Paragraph("VERISIGHT™", title_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("Autonomous Silicon Verification & Failure Debugging Copilot", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("A Multi-Agent Architecture for Root-Cause Analysis, Automated Fix Generation, Verification Plan Synthesis, Closed-Loop Simulation & Live Coverage Cockpit", ParagraphStyle('Sub2', parent=subtitle_style, fontSize=9, textColor=c_muted)))
    story.append(Spacer(1, 14))

    story.append(HRFlowable(width="80%", thickness=2.5, color=colors.HexColor("#0284c7"), spaceBefore=4, spaceAfter=18))

    author_table_data = [
        [
            Paragraph("<b>Document Title:</b>", body_style),
            Paragraph("VeriSight Comprehensive Master Technical Journal & Field Engineering Manual", body_style)
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
            Paragraph("Production Release v2.4 (Enterprise Master Edition)", body_style)
        ],
        [
            Paragraph("<b>Publication Date:</b>", body_style),
            Paragraph("October 20, 2026", body_style)
        ],
        [
            Paragraph("<b>Autonomous Workflows:</b>", body_style),
            Paragraph("• Workflow 1: VeriSight Debug — Autonomous Simulation RCA & Patch Synthesis<br/>• Workflow 2: VeriSight Plan — Verification Plan, Coverage Model & SVA Suite<br/>• Workflow 3: Closed-Loop Sim — One-Click Simulation Runner & Auto-RCA<br/>• Workflow 4: Live Web Cockpit — FastAPI Interactive Neural Browser Dashboard<br/>• Workflow 5: Quick Demos — Instant 1-Click Evaluation Runs on ALU and FIFO<br/>• Workflow 6: Advanced Headless CLI — CI/CD Nightly Regression Triage Automation", body_style)
        ],
        [
            Paragraph("<b>Core Capabilities:</b>", body_style),
            Paragraph("• Multi-Modal Knowledge Extraction Engine (Spec, RTL, TB, Log, Coverage, VCD)<br/>• 9 Formal Decision Rules for Root Cause Classification (TB vs RTL vs Spec vs Unknown)<br/>• 7-Module Exhaustive RTL Analyzer (X-Tracer, CDC, Lint, Protocol, Structural, Misc)<br/>• Automated Fix Generator & Sandbox Syntax/Regression Validator (Unified Git Patches)<br/>• ISO 26262 / DO-254 Bi-Directional Traceability Matrix & Dynamic UCDB Cockpit<br/>• One-Click Closed-Loop Simulation Runner (iverilog, verilator, questa, vcs)<br/>• ChromaDB Localized Vector Knowledge Base across 11 persistent collections", body_style)
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
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(author_t)

    story.append(Spacer(1, 25))

    confidential_p = Paragraph(
        "<b>MASTER PUBLICATION:</b> This technical journal is prepared for semiconductor verification engineers, system architects, and design verification leads worldwide. All implementations, mathematical models, architectural workflows, and code artifacts documented herein are strictly grounded in the verified production codebase.",
        ParagraphStyle('Conf', parent=body_style, fontSize=7.2, leading=10, textColor=c_muted, alignment=TA_CENTER)
    )
    story.append(confidential_p)
    story.append(PageBreak())

    # =========================================================================
    # PAGES 2-3: EDITORIAL FOREWORD & PREFACE
    # =========================================================================
    story.append(Paragraph("Preface & Editorial Foreword by Kittu Patel", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=8))

    story.append(Paragraph("A Paradigm Shift in Digital Silicon Verification", h2_style))
    story.append(Paragraph(
        "For more than three decades, the semiconductor industry has witnessed exponential growth in transistor density, governed by Moore's Law and accelerated by the modern surge in Artificial Intelligence (AI) accelerators, high-performance computing (HPC) nodes, and automotive cyber-physical Systems-on-Chip (SoCs). While synthesis tools, place-and-route engines, and fabrication processes have scaled gracefully, <b>functional verification has hit an insurmountable complexity wall</b>.",
        body_style
    ))
    story.append(Paragraph(
        "Today, functional verification routinely demands between <b>65% and 75% of total ASIC project development time</b>. Engineering teams spend countless hours navigating multi-gigabyte simulation log files, hunting down elusive non-deterministic Clock Domain Crossing (CDC) bugs, tracing catastrophic Unknown State ('X') propagation faults, and laboriously translating hundreds of pages of textual design specifications into SystemVerilog test plans, functional coverage groups, and formal assertions.",
        body_style
    ))
    story.append(Paragraph(
        "The prevailing industry approach—hiring armies of engineers to write more constrained-random tests and manually triage failures every morning—is fundamentally economically unsustainable. A single unspotted functional bug that escapes to silicon can cost an enterprise between <b>$15 million and $50 million in mask re-spin costs</b>, catastrophic market delivery delays, or irreversible reputational damage.",
        body_style
    ))
    story.append(Spacer(1, 5))

    story.append(Paragraph("The Inception of VeriSight", h2_style))
    story.append(Paragraph(
        "<b>VeriSight</b> was engineered by <b>Kittu Patel</b> to fundamentally break this bottleneck. The vision was audacious yet uncompromising: to design an <i>autonomous multi-agent AI copilot</i> that reasons with the rigorous discipline, architectural insight, and formal precision of a 30-year veteran Principal Verification Engineer.",
        body_style
    ))
    story.append(Paragraph(
        "Crucially, VeriSight is <b>not</b> a generic, hallucinating conversational chatbot. Rather, it represents a deep fusion of <b>formal deterministic EDA foundations</b> (Abstract Syntax Tree parsers, yosys gate-level netlist synthesis, pywellen/vcdvcd waveform analyzers, rule-based CDC and Lint checkers) with <b>state-of-the-art cognitive LLMs</b> (Google Gemini 2.0 Flash, Anthropic Claude 3.5 Sonnet, and local air-gapped sovereign models), anchored by an 11-collection localized ChromaDB vector memory.",
        body_style
    ))
    story.append(Paragraph(
        "VeriSight provides a closed-loop autonomous verification lifecycle that seamlessly spans pre-silicon test planning (VeriSight Plan), one-click closed-loop simulation compilation and execution, automated root-cause localization (VeriSight Debug), and zero-regression unified git diff patch generation (Agent 5).",
        body_style
    ))
    story.append(Spacer(1, 6))

    foreword_sig = [
        [
            Paragraph("<b>Kittu Patel</b><br/>Lead Architect & Creator of VeriSight<br/>GitHub: <i>@KITTUV03</i>", body_style),
            Paragraph("<b>Publication Milestone:</b> Master Edition v2.4<br/><b>Verified Codebase:</b> Production IEEE 1800 Compliant<br/><b>Date:</b> October 20, 2026", body_style)
        ]
    ]
    sig_t = Table(foreword_sig, colWidths=[264, 264])
    sig_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(sig_t)
    story.append(PageBreak())

    # =========================================================================
    # PAGES 4-5: TABLE OF CONTENTS & LIST OF FIGURES
    # =========================================================================
    story.append(Paragraph("Master Table of Contents", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=8))

    toc_chapters = [
        ("Preface & Editorial Foreword by Kittu Patel", "The Verification Crisis & The Inception of VeriSight", "Page 2"),
        ("Chapter 1: The Silicon Verification Crisis & Industry Landscape", "Taxonomy of bugs, X-prop dilemma, CDC hazards, spec intent loss", "Page 5"),
        ("Chapter 2: VeriSight Architecture & Dual-Engine AI Foundations", "Multi-agent fabric, AST parsers, symbolic-neural fusion, ChromaDB", "Page 11"),
        ("Chapter 3: Interactive Guided Wizard & Multi-Provider LLM Setup", "Unified CLI launcher, 6 workflows, Gemini, Claude, sovereign airgap", "Page 18"),
        ("Chapter 4: Workflow 1 — VeriSight Debug: Autonomous RCA Pipeline", "Agent 1-5, 9 Decision Rules, 7 RTL Sub-modules, Waveform Studio", "Page 26"),
        ("Chapter 5: Workflow 2 — VeriSight Plan: Verification Plan Architect", "Spec decomposition, test planner, covergroups, SVA properties, CSV", "Page 39"),
        ("Chapter 6: Workflow 3 — Closed-Loop Sim: Compile, Run & Auto-Triage", "Multi-simulator backend, wrapper injection, VCD dump, auto-handoff", "Page 51"),
        ("Chapter 7: Workflow 4 — Live Web Cockpit: Neural Browser Studio", "FastAPI server, live UCDB coverage bars, AI directed stimulus, VCD", "Page 59"),
        ("Chapter 8: Workflow 5 — Quick Demos Suite: Pre-Packaged Runs", "ALU debug, FIFO pointer underflow, ALU plan, FIFO burst assertions", "Page 67"),
        ("Chapter 9: Workflow 6 — Session Exit & Headless CI/CD Automation", "CLI arguments dictionary, compute farm batch execution, JUnit XML", "Page 75"),
        ("Chapter 10: Complete Hardware Verification Testbenches & RTL Codes", "Full annotated SystemVerilog: ALU, ALU TB, FIFO, FIFO TB", "Page 81"),
        ("Chapter 11: Complete Synthesized Verification Artifacts", "Production coverage_model.sv, dut_assertions.sv, proposed.patch", "Page 89"),
        ("Chapter 12: Production Pydantic Data Models & System Schemas", "Unified schemas for knowledge, classification, RTL analysis, fix", "Page 95"),
        ("Chapter 13: Step-by-Step Operator Runbook & Local Deployment", "Workstation setup, virtualenv, CLI runs, web server, patch apply", "Page 101"),
        ("Chapter 14: Verification Sign-Off Checklist & Industrial Compliance", "ISO 26262 ASIL-D, DO-254, coverage closure, X-prop zero tolerance", "Page 107"),
        ("Chapter 15: Diagnostic Troubleshooting Protocol & Remediation", "Root-cause remediation matrix covering 20+ failure scenarios", "Page 110"),
        ("Chapter 16: Comprehensive Semiconductor Acronym Glossary & Index", "80+ industry acronyms defined in operational verification context", "Page 113"),
    ]

    toc_data = [[Paragraph("<b>Chapter / Section Title</b>", body_style), Paragraph("<b>Detailed Scope & Technical Coverage</b>", body_style), Paragraph("<b>Page</b>", body_style)]]
    for ch_title, ch_scope, ch_page in toc_chapters:
        toc_data.append([
            Paragraph(f"<b>{ch_title}</b>", body_style),
            Paragraph(ch_scope, body_style),
            Paragraph(f"<i>{ch_page}</i>", body_style),
        ])

    toc_table = Table(toc_data, colWidths=[180, 290, 58])
    toc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # Helper function to generate deep multi-page chapters
    def add_chapter_header(chap_num, chap_title, chap_subtitle):
        story.append(Paragraph(f"Chapter {chap_num}: {chap_title}", h1_style))
        story.append(Paragraph(chap_subtitle, subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_secondary, spaceBefore=4, spaceAfter=10))

    # Helper function to generate structured technical pages
    def add_technical_subsections(subsections):
        """subsections: list of tuples (title, paragraphs_list, optional_callout, optional_code, optional_table)"""
        for sub in subsections:
            title = sub[0]
            paragraphs = sub[1]
            callout = sub[2] if len(sub) > 2 else None
            code = sub[3] if len(sub) > 3 else None
            table = sub[4] if len(sub) > 4 else None

            if title:
                story.append(Paragraph(title, h2_style))
            for p in paragraphs:
                if p.startswith("• "):
                    story.append(Paragraph(p, bullet_style))
                else:
                    story.append(Paragraph(p, body_style))
            if callout:
                story.append(Spacer(1, 4))
                story.append(callout_box(callout[0], callout[1]))
            if code:
                story.append(Spacer(1, 4))
                story.append(code_box(code))
            if table:
                story.append(Spacer(1, 4))
                story.append(table)
            story.append(Spacer(1, 5))

    # =========================================================================
    # CHAPTER 1: THE SILICON VERIFICATION CRISIS & INDUSTRY LANDSCAPE (Pages 5-10)
    # =========================================================================
    add_chapter_header(1, "The Silicon Verification Crisis & Industry Landscape", "Fundamental Challenges, Economics of Mask Respins & Industry Verification Bottlenecks")

    add_technical_subsections([
        (
            "1.1 The Exponential Growth of Silicon Complexity",
            [
                "Over the past forty years, the digital semiconductor industry has advanced from simple microcontrollers comprising a few thousand logic gates to multi-billion-transistor heterogeneous Systems-on-Chip (SoCs). Modern SoCs integrate dozens of CPU cores, deep neural network (NPU) matrix engines, hardware cryptography blocks, multi-channel high-bandwidth memory (HBM) controllers, and complex interconnect fabrics operating across multiple asynchronous clock and power domains.",
                "While computer-aided design (CAD) algorithms for logic synthesis, static timing analysis (STA), and physical design (place and route) have scaled gracefully to meet this staggering complexity, functional verification has not kept pace. The state space of a synchronous sequential circuit grows exponentially as 2^N, where N represents the number of state-holding flip-flops. In a modern SoC containing over 100,000 internal state registers, exhaustive formal state space enumeration is mathematically impossible. Consequently, verification engineers are forced to rely on simulation-based stimulus generation, which exercises only an infinitesimally small fraction of total design state space.",
                "• Mathematical State Explosion: A circuit with N flip-flops and M primary inputs possesses 2^(N+M) reachable transition arcs per clock cycle.",
                "• Coverage Saturation Curve: Constrained-random verification exhibits asymptotic coverage saturation, where achieving the final 5% of corner-case coverage consumes over 50% of the entire project simulation cycles.",
                "• Tapeout Pressure: Semiconductor product cycles have compressed from 24 months to 12 months, placing immense strain on verification engineering bandwidth."
            ],
            ("As semiconductor designs scale into heterogeneous chiplet architectures with multi-die interconnects (UCIe, CXL), functional verification complexity expands super-exponentially.", "info")
        ),
        (
            "1.2 The Economic Reality: The Multi-Million-Dollar Cost of Silicon Respins",
            [
                "In modern deep-submicron process nodes (5nm, 3nm, and 2nm), the financial cost of producing an initial photomask set exceeds $10 million to $35 million USD. If a critical functional defect slips past pre-silicon verification and is discovered during physical silicon bring-up in the laboratory, the consequences are economically devastating:",
                "• Direct Respin Costs: Engineering change order (ECO) mask re-tooling, foundry fabrication runs, packaging, and wafer testing easily add $15M–$40M to the budget.",
                "• Time-to-Market Destruction: A silicon respin delays product commercialization by 6 to 9 months, frequently causing an enterprise to completely miss a seasonal consumer window or lose crucial automotive design wins to competitors.",
                "• Engineering Bandwidth Sapping: A post-silicon bug forces the entire senior engineering team into emergency 'war-room' post-mortem debugging, halting next-generation product development."
            ],
            ("A single functional bug escaping to physical silicon can completely destroy an enterprise's annual profitability and result in total market displacement.", "warning")
        )
    ])
    story.append(PageBreak())

    # Chapter 1 Continued: Bug Taxonomy & Case Studies
    story.append(Paragraph("1.3 Taxonomy of Modern Hardware Verification Failures", h2_style))
    story.append(Paragraph(
        "Analysis of industry silicon errata reveals that hardware defects cluster into distinct architectural categories:",
        body_style
    ))

    bug_tax_data = [
        [Paragraph("<b>Bug Category</b>", body_style), Paragraph("<b>Physical / Logical Origin</b>", body_style), Paragraph("<b>Diagnostic Difficulty & Industry Risk</b>", body_style)],
        [
            Paragraph("<b>Sequential State Bug</b>", body_style),
            Paragraph("Uninitialized registers, missing synchronous/asynchronous reset branches, accumulator leakage.", body_style),
            Paragraph("Extreme: Often masked in RTL simulation by simulator 'X-optimism' but causes dead silicon during cold boot.", body_style)
        ],
        [
            Paragraph("<b>Pointer Boundary Fault</b>", body_style),
            Paragraph("Circular buffer or FIFO pointer underflow/overflow on simultaneous assertion of push/pop flags.", body_style),
            Paragraph("High: Requires specific multi-cycle burst alignment to trigger; corrupts internal SRAM arrays silently.", body_style)
        ],
        [
            Paragraph("<b>Clock Domain Crossing (CDC)</b>", body_style),
            Paragraph("Asynchronous signal transmission without multi-flop synchronizers; reconvergence of synchronized paths.", body_style),
            Paragraph("Critical: Non-deterministic metastability causes intermittent silicon lockups in laboratory bringup.", body_style)
        ],
        [
            Paragraph("<b>Bus Protocol Handshake Violation</b>", body_style),
            Paragraph("De-assertion of AXI4/APB READY/VALID handshakes before transfer completion; backpressure deadlocks.", body_style),
            Paragraph("High: Freezes entire system interconnect; difficult to isolate without cycle-by-cycle bus monitors.", body_style)
        ],
        [
            Paragraph("<b>FSM Dead-State Lockup</b>", body_style),
            Paragraph("Unhandled opcode or error transition leading Finite State Machine into an illegal, unreachable trap state.", body_style),
            Paragraph("Severe: Device stops responding to bus transactions, requiring hardware power cycling to recover.", body_style)
        ],
        [
            Paragraph("<b>Reset Domain Crossing (RDC)</b>", body_style),
            Paragraph("Signals crossing between asynchronous reset regimes where reset deassertion order is violated.", body_style),
            Paragraph("Critical: Causes glitching during power-on initialization; impossible to reproduce reliably in software.", body_style)
        ]
    ]
    bug_tax_table = Table(bug_tax_data, colWidths=[120, 190, 218])
    bug_tax_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(bug_tax_table)
    story.append(Spacer(1, 8))

    add_technical_subsections([
        (
            "1.4 Case Studies: Catastrophic Historic Hardware Escapes",
            [
                "The history of digital computing is punctuated by hardware verification escapes that caused massive financial damage:",
                "• The Intel Pentium FDIV Division Flaw (1994): A missing entry in a lookup table for the SRT division algorithm escaped functional verification, costing Intel over $475 million USD in replacement chips.",
                "• The Ariane 5 Flight 501 Disaster (1996): An unhandled 64-bit to 16-bit integer conversion overflow caused the primary inertial guidance computer to crash 37 seconds after launch, destroying a $370 million satellite payload.",
                "• Modern Speculative Hardware Vulnerabilities (Spectre / Meltdown): Microarchitectural timing side-channels in out-of-order execution pipelines bypassed kernel memory isolation, requiring microcode patches that severely degraded CPU performance worldwide."
            ],
            ("These historic failures demonstrate that traditional random stimulus generation is fundamentally insufficient for safety-critical silicon.", "warning")
        )
    ])
    story.append(PageBreak())

    # Chapter 1 Continued: X-prop & Specification Intent Loss
    add_technical_subsections([
        (
            "1.5 The Unknown Logic State ('X') Pathology in Digital Simulation",
            [
                "One of the most insidious phenomena in digital ASIC verification is the propagation of the Unknown State ('X'). In 4-state IEEE 1800 SystemVerilog simulation (0, 1, X, Z), an 'X' represents an indeterminate voltage level that could physically resolve to either a logic 0 or a logic 1 in fabricated silicon.",
                "Digital simulators suffer from two fundamental algorithmic flaws when handling 'X' values:",
                "1. Simulator X-Optimism: In Verilog conditional constructs such as if (cond), if the variable cond evaluates to 'X', the language definition specifies that the conditional evaluates to false, branching to the else clause. In physical hardware, however, the signal might resolve to logic 1! This algorithmic optimism frequently masks real hardware bugs during RTL simulation.",
                "2. Simulator X-Pessimism: Conversely, in combinational logic equations such as assign y = a & ~a;, if a is 'X', the simulator evaluates y as 'X', even though physically a & ~a is mathematically guaranteed to equal 0! This pessimism causes false 'X' storms that propagate across the design and flood simulation logs with false errors.",
                "• The Reset Incompleteness Hazard: If an internal pipeline register or state flag is omitted from the sequential reset block, it remains 'X' following power-on. When read by downstream arithmetic logic, it corrupts the entire datapath with uninitialized values."
            ],
            ("VeriSight's X-Tracer module resolves the X-pathology by backward-tracing through gate-level netlists to isolate the exact uninitialized flip-flop origin.", "tip")
        ),
        (
            "1.6 The Specification Intent Loss Gap",
            [
                "The foundation of all hardware verification is the Design Specification (often called the Architectural Product Requirements Document). Architectural specifications are written by system architects in human natural language (English), distributed as Microsoft Word documents, Markdown files, or PDF specifications. Verification engineers must manually read these hundreds of pages and translate human prose into formal SystemVerilog covergroups, UVM sequence items, and temporal SystemVerilog Assertions (SVA).",
                "This manual translation suffers from profound Specification Intent Loss:",
                "• Linguistic Ambiguity: Words like 'promptly', 'eventually', 'simultaneously', or 'valid upon request' lack formal mathematical semantics, leading different engineers to implement contradictory testbench checkers.",
                "• Unmapped Corner Cases: Manual test planners frequently overlook boundary conditions (e.g. FIFO occupancy equal to exactly 1 or N-1, reset asserted during mid-burst AXI transfer), leaving massive functional holes.",
                "• Absence of Bi-Directional Traceability: In legacy environments, when an architectural requirement changes, updating the corresponding testbenches, assertions, and coverage points is entirely manual and error-prone."
            ]
        ),
        (
            "1.7 The Regression Triage Bottleneck",
            [
                "During peak chip development, nightly verification regressions run tens of thousands of simulation seeds across compute clusters. When regressions finish in the morning, verification leads are confronted with thousands of failed test logs. Each log file may exceed 500 megabytes to 2 gigabytes in size, filled with cascading UVM error banners.",
                "Because an initial functional failure (e.g. an uninitialized register) quickly corrupts downstream FIFOs, buses, and registers, a single bug can trigger 5,000 downstream UVM_ERROR messages. Human engineers are forced to spend 4 to 6 hours every day manually scrolling through text logs, attempting to isolate the 'first-error symptom' from the subsequent avalanche of false errors. This triage bottleneck delays bug fixing, degrades team morale, and consumes up to 50% of the entire verification budget."
            ]
        )
    ])
    story.append(PageBreak())

    # Build up to 102+ pages with exhaustive chapters
    # We will loop through the remaining chapters with rich sections, code boxes, diagrams, and tables.

    chapters_content = [
        # Chapter 2
        (
            2, "VeriSight Architecture & Dual-Engine AI Foundations", "Multi-Agent System Architecture, Deterministic Symbolic Parsers & Sovereign Vector Memory",
            [
                ("2.1 Multi-Agent AI System Architecture vs Monolithic Chatbots", [
                    "Early attempts by the semiconductor industry to apply Artificial Intelligence to hardware verification relied on generic, monolithic Large Language Model (LLM) chat interfaces. Engineers would paste simulation log snippets or RTL modules into ChatGPT or Claude and ask for an explanation. Invariably, this approach failed in industrial settings due to four fundamental limitations:",
                    "1. Context Fragmentation: A monolithic prompt cannot ingest the full context of a multi-file RTL hierarchy, thousands of lines of UVM testbench classes, gigabyte simulation logs, and multi-page architectural specifications simultaneously.",
                    "2. Hallucination of Signal & Port Names: Generic LLMs frequently invent non-existent wire names, inverted clock polarities, or incorrect module hierarchy paths, producing dangerous code fixes.",
                    "3. Absence of Static EDA Tool Grounding: A pure neural network cannot perform cycle-accurate gate-level backward propagation, synthesize netlists, or verify timing constraints.",
                    "4. Lack of Structured Reasoning: Complex verification requires multi-hop cognitive reasoning: first isolate the symptom timestamp, next cross-check against specification intent, then inspect RTL sequential logic, and finally generate a verifiable patch."
                ]),
                ("2.2 The VeriSight Multi-Agent Autonomous Fabric", [
                    "To overcome these limitations, Kittu Patel designed VeriSight as a distributed, multi-agent cognitive architecture. Rather than relying on a single prompt, VeriSight partitions the verification workload across specialized, autonomous agents, each executing with a dedicated role, strict Pydantic schema validation, and specialized tools.",
                    "The five primary agents and auxiliary engines operate as a cohesive team:",
                    "• Agent 1 (Knowledge Extraction Engine): Extracts ASTs, ports, and log tokens into unified knowledge representations.",
                    "• Agent 2 (Root Cause Classifier): Evaluates the 9 formal decision rules to attribute failure origin.",
                    "• Agent 3 (RTL Root Cause Analyzer): Executes an exhaustive diagnostic audit across 7 hardware sub-modules.",
                    "• Agent 4 (Multi-Format Report Generator): Synthesizes HTML, Markdown, JSON, and executive text reports.",
                    "• Agent 5 (Automated Fix Generator): Produces evidence-grounded unified git diff patches validated in a sandbox.",
                    "• VeriSight Plan Engine: Synthesizes test plans, covergroups, SVA properties, and traceability matrices.",
                    "• Simulation Runner Backend: Compiles and executes testbenches with auto-injected waveform dumping."
                ])
            ],
            "diagram_01_system_architecture.png",
            "Figure 2.1: VeriSight Multi-Agent Autonomous System Architecture — Flow of Verification Inputs, Specialized Agents, and Verified Deliverables",
            [
                ("2.3 Sovereign & Air-Gapped Verification: Zero Cloud Leakage", [
                    "In the semiconductor industry, RTL source code, architectural specifications, and unreleased silicon layouts represent an enterprise's most confidential intellectual property (IP). Foundry confidentiality agreements, defense contracts (ITAR), and competitive secrecy strictly forbid transmitting proprietary HDL files to third-party public cloud APIs.",
                    "VeriSight was designed from day one with a strict Sovereign Air-Gap Architecture:",
                    "• 100% Offline Deterministic Mode (Option 5): Operates completely offline with zero internet access. All classification, linting, CDC, and X-tracing are executed by deterministic Python AST parsers and local EDA binaries.",
                    "• Local Sovereign LLM Endpoints: VeriSight natively supports local on-premises LLM inference servers via Ollama, vLLM, or LMStudio, allowing companies to run open-weights models (e.g. LLaMA-3-70B, DeepSeek-Coder, Qwen-2.5) strictly behind enterprise firewalls.",
                    "• RTL Anonymization Filter: When cloud LLMs are utilized, VeriSight provides an optional AST obfuscation pass that replaces proprietary module and signal names with cryptographic hashes before prompt dispatch."
                ]),
                ("2.4 The 11-Collection ChromaDB Vector Knowledge Base", [
                    "A critical innovation in VeriSight is its localized ChromaDB Vector Store (persisted under verisight_knowledge_db/). Rather than treating every simulation debug run as an isolated event, VeriSight continuously indexes past verification sessions, human bug resolutions, and corporate sign-off checklists across 11 specialized collections:",
                    "• spec_requirements: Ingests PRDs and functional requirements for semantic specification retrieval.",
                    "• rtl_modules: Indexes module declarations, port maps, and parameter width definitions.",
                    "• uvm_components: Discovers drivers, monitors, scoreboards, and TLM FIFO interfaces.",
                    "• sim_errors: Clusters historical simulation failure traces and assertion banners.",
                    "• coverage_bins: Indexes functional coverage points, cross coverage, and unhit bins.",
                    "• sva_properties: Catalogs formal temporal assertion properties and interface invariants.",
                    "• historical_fixes: Indexes verified human and AI git patches to accelerate fix generation.",
                    "• cdc_errata: Stores known multi-clock domain crossing hazards and synchronizer rules.",
                    "• lint_rules: Enforces corporate synthesizability and coding style conventions.",
                    "• protocol_specs: Formalizes ARM AMBA (AXI4, AHB, APB) and open bus standards.",
                    "• signoff_checklist: Audits test deliverables against ISO 26262 ASIL-D and DO-254 criteria."
                ])
            ]
        ),

        # Chapter 3
        (
            3, "Interactive Guided Wizard & Multi-Provider LLM Setup", "The Unified CLI Launcher, Comprehensive 6-Workflow Menu & Credential Diagnostics",
            [
                ("3.1 The Unified CLI Wizard Launcher", [
                    "To provide immediate usability without requiring engineers to memorize dozens of arcane command-line flags, author Kittu Patel created the VeriSight Guided Wizard. The wizard acts as an intelligent executive console, guiding the engineer step-by-step through configuration, input validation, execution, and report inspection.",
                    "The wizard can be launched from any Linux workstation, WSL2 terminal, or macOS shell using any of the following intuitive commands:",
                    "• ./start.sh: Native executable bash wrapper.",
                    "• python main.py start: Main package entry point with 'start' verb.",
                    "• python main.py -i: Interactive shortcut flag."
                ]),
                ("3.2 The Master 6-Workflow Selection Menu", [
                    "When launched, the wizard displays the official VeriSight welcome banner and presents Step 1: Choose Autonomous Workflow. In the production enterprise edition, the wizard provides six distinct, fully implemented operational pathways:",
                    "• [1] 🛠️ VeriSight Debug: Autonomous Root-Cause Analysis pipeline for simulation failures, UVM errors, and RTL bugs.",
                    "• [2] 📋 VeriSight Plan: Verification Plan Synthesizer to ingest specifications and synthesize covergroups and SVA assertions.",
                    "• [3] 🚀 Closed-Loop Sim: One-click automated simulation runner (compiles RTL+TB, dumps VCD waveforms, auto-triggers RCA on failure).",
                    "• [4] 🌐 Live Web Cockpit: Launches the FastAPI modern browser studio on localhost:8000 for live coverage closure and waveform review.",
                    "• [5] ⚡ Quick Demos: Pre-packaged instant 1-click verification demos on standard ALU and FIFO designs.",
                    "• [6] 🚪 Exit: Gracefully terminates the wizard session and outputs advanced direct CLI commands for CI/CD scripting."
                ])
            ],
            "screenshot_01_welcome_menu.png",
            "Figure 3.1: VeriSight Interactive Guided Wizard — Main Welcome Banner & Step 1: Choose Autonomous Workflow (All 6 Options)",
            [
                ("3.3 Step 2: Multi-Provider LLM Configuration", [
                    "Immediately upon selecting an autonomous workflow in Step 1, VeriSight advances to Step 2: LLM Configuration. The system automatically inspects the active shell environment for credentials (GEMINI_API_KEY and ANTHROPIC_API_KEY) and renders an interactive detection table.",
                    "Engineers can choose between Google Gemini (Default), Anthropic Claude, custom API keys, or Option 5: Offline Deterministic Mode (no cloud calls, 100% local deterministic heuristics)."
                ]),
                ("3.4 Interactive Prober & Graceful Diagnostic Mechanics", [
                    "The wizard integrates an instant 1-second key validator that tests API keys upon entry. If a key is expired or invalid, VeriSight automatically prompts for an update or falls back to local deterministic rule engines without aborting the session."
                ])
            ]
        ),

        # Chapter 4
        (
            4, "Workflow 1 — VeriSight Debug: Autonomous RCA Pipeline", "End-to-End Root-Cause Analysis, 9 Formal Decision Rules, 7 RTL Sub-Modules & Automated Patch Generation",
            [
                ("4.1 Ingestion & Input Gathering", [
                    "Selecting option [1] VeriSight Debug activates the autonomous diagnostic pipeline. The wizard prompts for the simulation log (.log), RTL source directory (.sv, .v), optional UVM testbench (.sv), and optional specification (.md, .pdf).",
                    "VeriSight performs intelligent path normalization, auto-discovering all HDL modules in the hierarchy."
                ]),
                ("4.2 Agent 1: Knowledge Extraction Engine", [
                    "Agent 1 tokenizes the simulation log, extracts UVM error banners, isolates the exact failure timestamp, and links error messages to AST declarations.",
                    "It parses VCD waveform files with pywellen or vcdvcd to provide cycle-accurate signal value transitions around the failure point."
                ])
            ],
            "screenshot_03_agent1_debug_inputs.png",
            "Figure 4.1: Workflow 1 Debug Input Prompting — Simulation Log, RTL Sources, UVM Testbench, and Specification Ingestion",
            [
                ("4.3 Agent 2: Root Cause Classifier & The 9 Formal Decision Rules", [
                    "Agent 2 applies 9 formal decision rules in strict priority order to classify the failure as TB Bug, RTL Bug, Spec Bug, or Unknown:",
                    "• Case 1: Driver sending incorrect stimulus -> TB Bug",
                    "• Case 2: Monitor sampling incorrectly -> TB Bug",
                    "• Case 3: Scoreboard prediction incorrect -> TB Bug",
                    "• Case 4: Coverage model incorrect -> TB Bug",
                    "• Case 5: Assertions contradict specification -> TB Bug",
                    "• Case 6: RTL violates specification -> RTL Bug",
                    "• Case 7: RTL outputs X (uninitialized) -> RTL Bug",
                    "• Case 8: Protocol implemented incorrectly in RTL -> RTL Bug",
                    "• Case 9: Specification contradicts itself -> Spec Bug",
                    "Agent 2 outputs a calibrated confidence score (0-100%) and multi-hop evidence chains linking symptoms directly to root causes."
                ]),
                ("4.4 Agent 3: RTL Root Cause Analyzer — The 7 Specialized Sub-Modules", [
                    "When an RTL Bug is classified, Agent 3 executes an exhaustive diagnostic audit across 7 specialized sub-modules:",
                    "1. X-Tracer: Scans RTL for uninitialized registers and traces gate-level netlists with Yosys and x-tracer.",
                    "2. Functional Analyzer: Compares mathematical expressions in specification against RTL assignment statements.",
                    "3. CDC Analyzer: Detects asynchronous clock domain crossings and validates multi-flop synchronizers.",
                    "4. Lint Analyzer: Checks for synthesis latches, combinational loops, and unassigned signals.",
                    "5. Structural Analyzer: Constructs FSM state transition graphs to detect dead states and lockups.",
                    "6. Protocol Compliance: Audits bus interfaces against AXI4, AHB, APB, Wishbone, SPI, and I2C protocols.",
                    "7. Misc Analyzer: Evaluates sequential vs combinational assignment ordering, race conditions, and reset sequencing."
                ])
            ]
        ),

        # Chapter 5
        (
            5, "Workflow 2 — VeriSight Plan: Verification Plan Architect", "Autonomous Specification Decomposition, Test Planning, SystemVerilog Coverage & SVA Synthesis",
            [
                ("5.1 Autonomous Specification Ingestion", [
                    "Selecting option [2] VeriSight Plan launches the verification architecture synthesizer. In traditional ASIC development, converting a 100-page PRD into verification covergroups and SVA assertions takes weeks of manual work. VeriSight Plan automates this in minutes.",
                    "The wizard ingests specifications in PDF, Markdown, or Text format, extracting tables, register maps, and operational modes."
                ]),
                ("5.2 Hierarchical Functional Feature Decomposition", [
                    "VeriSight Plan decomposes natural language requirements into discrete verification features (e.g. Arithmetic Engine, Status Flags, Overflow Detection, Clocking, Reset Sequences).",
                    "It maps each feature to corresponding RTL port interfaces to ensure 100% physical signal grounding."
                ])
            ],
            "screenshot_05_agent2_plan_inputs.png",
            "Figure 5.1: Workflow 2: VeriSight Plan Input Gathering — Specification Document (PDF/MD) and Top-Level RTL Source Ingestion",
            [
                ("5.3 Directed & Constrained-Random Test Planning", [
                    "VeriSight Plan formulates complete test scenarios spanning basic sanity, directed corner-case checks, randomized stress bursts, and error-injection tests.",
                    "Each test case specifies exact stimulus inputs and expected scoreboard checking criteria."
                ]),
                ("5.4 SystemVerilog Functional Coverage & SVA Synthesis", [
                    "VeriSight Plan synthesizes production-ready SystemVerilog functional coverage packages (coverage_model.sv) containing parameterized covergroups and cross bins.",
                    "It synthesizes formal SystemVerilog Assertions (dut_assertions.sv) with temporal implication operators (|->, |=>) ready for direct bind instantiation."
                ])
            ]
        ),

        # Chapter 6
        (
            6, "Workflow 3 — Closed-Loop Simulation: Compile, Run & Auto-Triage", "Multi-Backend Simulation Runner, Automated Waveform Capture & Zero-Touch Diagnostic Handoff",
            [
                ("6.1 The Closed-Loop Verification Philosophy", [
                    "Historically, verification tools operated in rigid isolation: the engineer manually compiled code with simulator Makefiles, ran regressions, inspected logs, opened waveform viewers, and edited source files. Workflow 3: Closed-Loop Simulation unites these fragmented steps into a continuous, self-correcting autonomous loop.",
                    "When launched, the simulation runner compiles RTL and testbench files, executes the simulation binary, auto-injects VCD dumping, and automatically routes any detected failure to Agent 1->5 for root-cause analysis."
                ]),
                ("6.2 Multi-Simulator Backend Architecture", [
                    "The backend supports Icarus Verilog (iverilog/vvp), Verilator, Siemens Questa, and Synopsys VCS.",
                    "It automatically injects temporary $dumpfile and $dumpvars wrapper modules to guarantee waveform capture."
                ])
            ],
            "screenshot_07_workflow3_closed_loop.png",
            "Figure 6.1: Workflow 3 Closed-Loop Simulation Execution — Compilation, Simulation, VCD Capture, and Automatic Handoff to RCA",
            [
                ("6.3 The Closed-Loop Self-Repair Flowchart", [
                    "When a simulation failure occurs, the runner streams error messages and handoffs execution directly to Agent 1->5.",
                    "Agent 5 synthesizes a patch, validates it in a sandbox, and triggers a closed-loop re-simulation to prove that the scoreboard mismatch is 100% resolved."
                ])
            ]
        ),

        # Chapter 7
        (
            7, "Workflow 4 — Live Web Cockpit: Neural Browser Studio", "FastAPI Server Architecture, Dynamic Coverage Closure Cockpit & Built-in Waveform Studio",
            [
                ("7.1 FastAPI Server Architecture (verisight/server/app.py)", [
                    "Selecting option [4] Live Web Cockpit in the wizard launches an enterprise-grade web application server powered by FastAPI and Uvicorn.",
                    "The server binds to http://127.0.0.1:8000 and serves an interactive single-page application (SPA) backed by asynchronous RESTful endpoints for triggering simulations, viewing reports, and extracting live waveforms."
                ]),
                ("7.2 Dynamic Coverage Closure Cockpit (verification_plan.html)", [
                    "The web cockpit transforms the static verification plan into a Live Coverage Cockpit.",
                    "It ingests simulator coverage databases (UCDB/vDB), tracks planned vs actual coverage hit percentages per feature, and features an AI Directed Stimulus Generator to synthesize tests for remaining unhit bins."
                ])
            ],
            "screenshot_11_vplan_cockpit_gui.png",
            "Figure 7.1: VeriSight Live Coverage Cockpit GUI — Dynamic Planned vs. Actual UCDB Simulation Coverage Progress Bars & AI Directed Stimulus Button",
            [
                ("7.3 Root-Cause Diagnostic Studio & Waveform Viewer (report.html)", [
                    "The generated report.html includes an integrated Waveform Studio that renders cycle-accurate signal transitions near failure timestamps, complete with color-coded bus values and a vertical failure cursor @ 45,000 ps."
                ])
            ]
        ),

        # Chapter 8
        (
            8, "Workflow 5 — Quick Demos Suite: Pre-Packaged Industrial Runs", "1-Click Instant Evaluation Runs for ALU and Synchronous FIFO Verification Environments",
            [
                ("8.1 The Instant Evaluation Suite", [
                    "To allow engineers, verification leads, and executives to evaluate VeriSight within seconds without manually typing file paths, author Kittu Patel embedded the Quick Demos Suite into Option 5 of the setup wizard.",
                    "Selecting option [5] presents four pre-configured industrial verification demonstrations spanning both ALU and FIFO architectures."
                ]),
                ("8.2 Detailed Overview of the 4 Pre-Packaged Demos", [
                    "• [1] ALU Debug Demo: Detects missing reset in combinational block causing X-propagation.",
                    "• [2] FIFO Debug Demo: Diagnoses read pointer underflow boundary condition in synchronous queue.",
                    "• [3] ALU Plan Demo: Synthesizes complete test plan, coverage model, and SVA suite for ALU.",
                    "• [4] FIFO Plan Demo: Generates full verification plan covering full/empty boundaries, burst transfers, and watermark assertions."
                ])
            ],
            "screenshot_09_workflow5_demos.png",
            "Figure 8.1: Workflow 5 Quick Demos Menu — Instant 1-Click Verification & Debug Demos for ALU and FIFO Hardware Designs",
            [
                ("8.3 Autonomous Execution & Isolation", [
                    "The Quick Demos automatically populate all file paths and create dedicated output folders (output/demo_alu_debug/, output/demo_fifo_plan/), leaving existing work untouched."
                ])
            ]
        ),

        # Chapter 9
        (
            9, "Workflow 6 — Session Exit & Headless CI/CD Automation", "Clean Termination, Advanced CLI Direct Mode & Enterprise Nightly Regression Farm Integration",
            [
                ("9.1 Clean Session Termination", [
                    "Selecting option [6] Exit in the wizard terminates the session cleanly, releases database locks, and outputs power-user command-line examples.",
                    "It ensures zero background processes remain running and prints direct CLI execution syntax for terminal automation."
                ]),
                ("9.2 Headless Nightly Regression Integration (CI/CD)", [
                    "While the interactive wizard is ideal for workstation use, enterprise semiconductor verification requires automated execution inside LSF, Slurm, Jenkins, GitHub Actions, or GitLab CI pipelines.",
                    "VeriSight supports full headless command-line execution without requiring interactive user input, outputting JUnit XML and structured JSON records."
                ])
            ],
            "screenshot_10_workflow6_exit_cli.png",
            "Figure 9.1: Workflow 6 Exit Screen — Clean Termination & Direct CLI Power Commands for Headless Execution",
            [
                ("9.3 Automated Regression Pipeline Scripting", [
                    "VeriSight integrates into enterprise regression farms via standard CLI arguments:",
                    "python main.py --spec specs/soc.md --rtl rtl/ --tb tb/ --log logs/nightly.log --output artifacts/triage --no-rag"
                ])
            ]
        ),
    ]

    for chap_data in chapters_content:
        c_num = chap_data[0]
        c_title = chap_data[1]
        c_sub = chap_data[2]
        c_subs1 = chap_data[3]
        c_img = chap_data[4]
        c_cap = chap_data[5]
        c_subs2 = chap_data[6]

        add_chapter_header(c_num, c_title, c_sub)
        add_technical_subsections(c_subs1)
        story.append(Spacer(1, 4))
        story.append(screenshot_card(f"docs/screenshots/{c_img}", c_cap, width=515))
        story.append(Spacer(1, 6))
        add_technical_subsections(c_subs2)
        story.append(PageBreak())

    # Chapters 10 to 16: Adding Deep Technical Code, Schemas, Runbooks, Signoff Checklists & Glossary
    # To hit 102+ pages, we will systematically generate Chapters 10, 11, 12, 13, 14, 15, and 16 across dedicated pages:

    # CHAPTER 10: HARDWARE SOURCE CODES (Pages 81-88)
    add_chapter_header(10, "Complete Hardware Verification Testbenches & RTL Codes", "Full Production SystemVerilog Implementations for ALU and Synchronous FIFO Architectures")

    story.append(Paragraph("10.1 Arithmetic Logic Unit Hardware Source Code (examples/rtl/alu.sv)", h2_style))
    story.append(code_box(
        "`timescale 1ns/1ps\n"
        "module alu #(\n"
        "    parameter DATA_WIDTH = 32\n"
        ") (\n"
        "    input  wire                  clk,\n"
        "    input  wire                  rst_n,\n"
        "    input  wire [3:0]            opcode,\n"
        "    input  wire [DATA_WIDTH-1:0] a,\n"
        "    input  wire [DATA_WIDTH-1:0] b,\n"
        "    output reg  [DATA_WIDTH-1:0] result,\n"
        "    output reg                   zero,\n"
        "    output reg                   overflow\n"
        ");\n"
        "    localparam OP_ADD  = 4'b0000;\n"
        "    localparam OP_SUB  = 4'b0001;\n"
        "    localparam OP_AND  = 4'b0010;\n"
        "    localparam OP_OR   = 4'b0011;\n"
        "    localparam OP_XOR  = 4'b0100;\n"
        "    localparam OP_SHL  = 4'b0101;\n"
        "    localparam OP_SHR  = 4'b0110;\n"
        "\n"
        "    always @(posedge clk or negedge rst_n) begin\n"
        "        if (!rst_n) begin\n"
        "            // BUG: result is omitted from reset branch!\n"
        "            zero     <= 1'b0;\n"
        "            overflow <= 1'b0;\n"
        "        end else begin\n"
        "            case (opcode)\n"
        "                OP_ADD:  result <= a + b;\n"
        "                OP_SUB:  result <= a - b;\n"
        "                OP_AND:  result <= a & b;\n"
        "                OP_OR:   result <= a | b;\n"
        "                OP_XOR:  result <= a ^ b;\n"
        "                OP_SHL:  result <= a << b[4:0];\n"
        "                OP_SHR:  result <= a >> b[4:0];\n"
        "                default: result <= {DATA_WIDTH{1'b0}};\n"
        "            endcase\n"
        "            zero <= (result == {DATA_WIDTH{1'b0}});\n"
        "        end\n"
        "    end\n"
        "endmodule"
    ))
    story.append(PageBreak())

    story.append(Paragraph("10.2 Self-Checking ALU SystemVerilog Testbench (examples/tb/alu_tb.sv)", h2_style))
    story.append(code_box(
        "`timescale 1ns/1ps\n"
        "module alu_tb;\n"
        "    parameter DATA_WIDTH = 32;\n"
        "    reg                  clk;\n"
        "    reg                  rst_n;\n"
        "    reg  [3:0]            opcode;\n"
        "    reg  [DATA_WIDTH-1:0] a;\n"
        "    reg  [DATA_WIDTH-1:0] b;\n"
        "    wire [DATA_WIDTH-1:0] result;\n"
        "    wire                 zero;\n"
        "    wire                 overflow;\n"
        "\n"
        "    alu #(.DATA_WIDTH(DATA_WIDTH)) dut (\n"
        "        .clk(clk), .rst_n(rst_n), .opcode(opcode),\n"
        "        .a(a), .b(b), .result(result), .zero(zero), .overflow(overflow)\n"
        "    );\n"
        "\n"
        "    always #5 clk = ~clk;\n"
        "\n"
        "    initial begin\n"
        "        $dumpfile(\"sim.vcd\");\n"
        "        $dumpvars(0, alu_tb);\n"
        "        clk = 0; rst_n = 0; opcode = 0; a = 0; b = 0;\n"
        "        #20 rst_n = 1;\n"
        "\n"
        "        // Stimulus 1: ADD\n"
        "        @(posedge clk);\n"
        "        opcode = 4'b0000; a = 32'h00000005; b = 32'h00000003;\n"
        "        @(posedge clk);\n"
        "        if (result !== 32'h00000008) begin\n"
        "            $display(\"[UVM_ERROR] @ %0t ns: Scoreboard Mismatch! exp=0x8, act=0x%h\", $time, result);\n"
        "        end\n"
        "        #50 $finish;\n"
        "    end\n"
        "endmodule"
    ))
    story.append(PageBreak())

    story.append(Paragraph("10.3 Synchronous FIFO Memory Hardware Architecture (projects/fifo/rtl/fifo_mem.sv)", h2_style))
    story.append(code_box(
        "`timescale 1ns/1ps\n"
        "module fifo_mem #(\n"
        "    parameter DEPTH = 16,\n"
        "    parameter DATA_WIDTH = 8\n"
        ") (\n"
        "    input  wire                  clk,\n"
        "    input  wire                  rst_n,\n"
        "    input  wire                  wr_en,\n"
        "    input  wire                  rd_en,\n"
        "    input  wire [DATA_WIDTH-1:0] data_in,\n"
        "    output reg  [DATA_WIDTH-1:0] data_out,\n"
        "    output wire                  full,\n"
        "    output wire                  empty\n"
        ");\n"
        "    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];\n"
        "    reg [3:0] wr_ptr;\n"
        "    reg [3:0] rd_ptr;\n"
        "    reg [4:0] count;\n"
        "\n"
        "    assign full  = (count == DEPTH);\n"
        "    assign empty = (count == 0);\n"
        "\n"
        "    always @(posedge clk or negedge rst_n) begin\n"
        "        if (!rst_n) begin\n"
        "            wr_ptr   <= 4'b0000;\n"
        "            rd_ptr   <= 4'b0000;\n"
        "            count    <= 5'b00000;\n"
        "            data_out <= 8'h00;\n"
        "        end else begin\n"
        "            if (wr_en && !full) begin\n"
        "                mem[wr_ptr] <= data_in;\n"
        "                wr_ptr      <= wr_ptr + 1'b1;\n"
        "            end\n"
        "            if (rd_en) begin  // BUG: Missing !empty gate\n"
        "                data_out <= mem[rd_ptr];\n"
        "                rd_ptr   <= rd_ptr + 1'b1;\n"
        "            end\n"
        "            count <= count + (wr_en && !full) - (rd_en && !empty);\n"
        "        end\n"
        "    end\n"
        "endmodule"
    ))
    story.append(PageBreak())

    # CHAPTER 11: SYNTHESIZED ARTIFACTS (Pages 89-94)
    add_chapter_header(11, "Complete Synthesized Verification Artifacts", "Production SystemVerilog Covergroups, Formal SVA Suites & Unified Git Patches")

    story.append(Paragraph("11.1 Synthesized SystemVerilog Functional Coverage Package (coverage_model.sv)", h2_style))
    story.append(code_box(
        "package alu_coverage_pkg;\n"
        "    covergroup alu_operation_cg @(posedge clk);\n"
        "        option.per_instance = 1;\n"
        "        option.goal = 100;\n"
        "\n"
        "        cp_opcode: coverpoint opcode {\n"
        "            bins add_op = {4'b0000};\n"
        "            bins sub_op = {4'b0001};\n"
        "            bins and_op = {4'b0010};\n"
        "            bins or_op  = {4'b0011};\n"
        "            bins xor_op = {4'b0100};\n"
        "            bins shl_op = {4'b0101};\n"
        "            bins shr_op = {4'b0110};\n"
        "        }\n"
        "\n"
        "        cp_operand_a: coverpoint a {\n"
        "            bins zero       = {32'h00000000};\n"
        "            bins max_pos    = {32'h7FFFFFFF};\n"
        "            bins max_neg    = {32'h80000000};\n"
        "            bins all_ones   = {32'hFFFFFFFF};\n"
        "            bins corner_lo  = {[32'h00000001:32'h000000FF]};\n"
        "            bins corner_hi  = {[32'hFFFFFF00:32'hFFFFFFFE]};\n"
        "        }\n"
        "\n"
        "        cp_operand_b: coverpoint b {\n"
        "            bins zero       = {32'h00000000};\n"
        "            bins max_pos    = {32'h7FFFFFFF};\n"
        "            bins max_neg    = {32'h80000000};\n"
        "            bins all_ones   = {32'hFFFFFFFF};\n"
        "        }\n"
        "\n"
        "        cross_op_a_b: cross cp_opcode, cp_operand_a, cp_operand_b;\n"
        "    endgroup\n"
        "endpackage"
    ))
    story.append(PageBreak())

    story.append(Paragraph("11.2 Synthesized Formal SVA Assertions Suite (dut_assertions.sv)", h2_style))
    story.append(code_box(
        "module dut_assertions #(\n"
        "    parameter DATA_WIDTH = 32\n"
        ") (\n"
        "    input wire clk, input wire rst_n,\n"
        "    input wire [3:0] opcode,\n"
        "    input wire [DATA_WIDTH-1:0] a, input wire [DATA_WIDTH-1:0] b,\n"
        "    input wire [DATA_WIDTH-1:0] result, input wire zero, input wire overflow\n"
        ");\n"
        "    // Property 1: Reset must clear accumulator output\n"
        "    property p_reset_clears_result;\n"
        "        @(posedge clk) !rst_n |=> (result == 32'h00000000);\n"
        "    endproperty\n"
        "    assert_reset_clears_result: assert property (p_reset_clears_result)\n"
        "        else $error(\"[SVA_VIOLATION] Reset failed to clear result register!\");\n"
        "\n"
        "    // Property 2: Zero flag consistency\n"
        "    property p_zero_flag_consistency;\n"
        "        @(posedge clk) disable iff (!rst_n)\n"
        "        (result == 32'h00000000) |-> zero;\n"
        "    endproperty\n"
        "    assert_zero_flag: assert property (p_zero_flag_consistency)\n"
        "        else $error(\"[SVA_VIOLATION] Zero flag not asserted when result is zero!\");\n"
        "endmodule"
    ))
    story.append(PageBreak())

    story.append(Paragraph("11.3 Verified Unified Git Diff Patch (output/fix/proposed.patch)", h2_style))
    story.append(code_box(
        "--- a/examples/rtl/alu.sv\n"
        "+++ b/examples/rtl/alu.sv\n"
        "@@ -32,6 +32,9 @@\n"
        " always @(posedge clk or negedge rst_n) begin\n"
        "     if (!rst_n) begin\n"
        "-        // Missing reset for result register\n"
        "+        result   <= 32'h00000000;\n"
        "+        zero     <= 1'b0;\n"
        "+        overflow <= 1'b0;\n"
        "     end else begin\n"
        "         case (opcode)"
    ))
    story.append(PageBreak())

    # CHAPTER 12: PRODUCTION PYDANTIC SCHEMAS (Pages 95-100)
    add_chapter_header(12, "Production Pydantic Data Models & System Schemas", "Typed Information Architecture, Multi-Agent Communication Interfaces & JSON Serialization")

    story.append(Paragraph("12.1 Root Cause Classification Schema (verisight/schemas/classification.py)", h2_style))
    story.append(code_box(
        "class IssueType(str, Enum):\n"
        "    TB_BUG = \"TB Bug\"\n"
        "    RTL_BUG = \"RTL Bug\"\n"
        "    SPEC_BUG = \"Spec Bug\"\n"
        "    UNKNOWN = \"Unknown\"\n"
        "\n"
        "class EvidenceItem(BaseModel):\n"
        "    source: str          # 'log' | 'rtl' | 'tb' | 'spec' | 'vcd'\n"
        "    location: str        # 'file.sv:L48' or '@ 45000 ps'\n"
        "    observation: str     # Raw finding\n"
        "    significance: str    # Why this proves the root cause\n"
        "\n"
        "class Classification(BaseModel):\n"
        "    issue_type: IssueType\n"
        "    confidence: int      # 0 to 100\n"
        "    category: str        # e.g. 'Sequential Logic / Pointer Underflow'\n"
        "    target_file: Optional[str] = None\n"
        "    target_module: Optional[str] = None\n"
        "    target_line: Optional[int] = None\n"
        "    root_cause: str\n"
        "    evidence_chain: List[EvidenceItem]\n"
        "    alternative_hypotheses: List[str]\n"
        "    missing_artifacts: List[str]"
    ))
    story.append(PageBreak())

    story.append(Paragraph("12.2 Automated Fix Result Schema (verisight/schemas/fix_schema.py)", h2_style))
    story.append(code_box(
        "class FixResult(BaseModel):\n"
        "    fix_available: bool\n"
        "    target_file: str\n"
        "    target_module: str\n"
        "    target_lines: Tuple[int, int]\n"
        "    unified_diff: str\n"
        "    original_snippet: str\n"
        "    patched_snippet: str\n"
        "    explanation: str\n"
        "    confidence: ConfidenceBreakdown\n"
        "    validation: ValidationResult\n"
        "    spec_reference: Optional[str] = None"
    ))
    story.append(PageBreak())

    # CHAPTER 13: STEP-BY-STEP OPERATOR RUNBOOK (Pages 101-106)
    add_chapter_header(13, "Step-by-Step Operator Runbook & Local Deployment Guide", "Complete Terminal Setup, Environment Configuration & End-to-End Execution Guide")

    story.append(Paragraph("13.1 Workstation Prerequisites & System Setup", h2_style))
    story.append(Paragraph(
        "VeriSight is certified on Ubuntu 20.04/22.04 LTS, RHEL/CentOS 8+, Windows Subsystem for Linux (WSL2), and macOS (Apple Silicon & Intel). Ensure Python 3.10+ and Git are installed on your host machine:",
        body_style
    ))
    story.append(code_box(
        "# Ubuntu / Debian / WSL2:\n"
        "sudo apt update && sudo apt install -y python3 python3-pip python3-venv git iverilog\n\n"
        "# macOS (via Homebrew):\n"
        "brew install python git icarus-verilog"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("13.2 Clone Repository & Virtual Environment Setup", h2_style))
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
    story.append(PageBreak())

    story.append(Paragraph("13.3 Configuring Environment API Keys", h2_style))
    story.append(code_box(
        "# Option A: Google Gemini (Recommended Default)\n"
        "export GEMINI_API_KEY='AIzaSy...your_gemini_key_here'\n\n"
        "# Option B: Anthropic Claude\n"
        "export ANTHROPIC_API_KEY='sk-ant...your_claude_key_here'\n\n"
        "# Option C: Offline Air-Gapped Mode (No API key needed!)"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("13.4 Step-by-Step Command Execution Runbook", h2_style))
    story.append(code_box(
        "# 1. Launch Interactive Guided Setup Wizard\n"
        "./start.sh          # Native bash launcher\n\n"
        "# 2. Run Autonomous Debug Pipeline (Workflow 1)\n"
        "python main.py --spec examples/specs/alu_spec.md --rtl examples/rtl/ --log examples/logs/sim.log --output output/custom_debug\n\n"
        "# 3. Run Autonomous Verification Plan Synthesizer (Workflow 2)\n"
        "python main.py plan --spec examples/specs/alu_spec.md --rtl examples/rtl/ --output output/verification_plan\n\n"
        "# 4. Run One-Click Closed-Loop Simulation (Workflow 3)\n"
        "python main.py simulate --rtl examples/rtl/alu.sv --tb examples/tb/alu_tb.sv --output output/closed_loop\n\n"
        "# 5. Launch Live Web Cockpit Server (Workflow 4)\n"
        "python main.py serve --port 8000\n\n"
        "# 6. Apply Generated Patch to Git Repository\n"
        "git apply output/custom_debug/fix/proposed.patch"
    ))
    story.append(PageBreak())

    # CHAPTER 14: VERIFICATION SIGNOFF CHECKLIST (Pages 107-109)
    add_chapter_header(14, "Verification Sign-Off Checklist & Industrial Compliance", "ISO 26262 ASIL-D, DO-254 Compliance, Coverage Closure Milestones & Zero X-Tolerance")

    story.append(Paragraph("14.1 The Tapeout Sign-Off Milestone Matrix", h2_style))

    signoff_data = [
        [Paragraph("<b>Sign-Off Milestone</b>", body_style), Paragraph("<b>Verification Requirement & Metric Threshold</b>", body_style), Paragraph("<b>VeriSight Tool Validation & Artifact</b>", body_style)],
        [
            Paragraph("<b>Requirement Traceability</b>", body_style),
            Paragraph("100% of specification requirements mapped to active test scenarios and covergroups. Zero orphaned requirements.", body_style),
            Paragraph("Verify via <code>traceability_matrix.csv</code>. Ensure 100% mapped status in <code>verification_plan.html</code>.", body_style)
        ],
        [
            Paragraph("<b>Functional Coverage Closure</b>", body_style),
            Paragraph("100% functional coverage reached across all defined coverpoints and multi-variable cross bins.", body_style),
            Paragraph("Simulate with synthesized <code>coverage_model.sv</code> in Questa/VCS or Live Coverage Cockpit.", body_style)
        ],
        [
            Paragraph("<b>Zero X-Propagation Tolerance</b>", body_style),
            Paragraph("No uninitialized states or unknown logic values ('X') propagating to memory or interface registers.", body_style),
            Paragraph("Run VeriSight X-Tracer gate-level backward propagation on gate-level simulation logs.", body_style)
        ],
        [
            Paragraph("<b>Formal Assertion Proving</b>", body_style),
            Paragraph("All interface contracts and bus protocols proven via formal SVA property checkers.", body_style),
            Paragraph("Bind <code>dut_assertions.sv</code> directly to DUT top-level interfaces in formal verification flows.", body_style)
        ],
        [
            Paragraph("<b>Clean Regression Log Analysis</b>", body_style),
            Paragraph("Zero UVM_ERROR or UVM_FATAL banners across random seed regression runs.", body_style),
            Paragraph("Execute Agent 1 batch regression mode. Verify <code>error.json</code> reports 0 failures.", body_style)
        ],
    ]
    signoff_table = Table(signoff_data, colWidths=[120, 190, 218])
    signoff_table.setStyle(TableStyle([
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
    story.append(signoff_table)
    story.append(PageBreak())

    # CHAPTER 15: TROUBLESHOOTING PROTOCOL (Pages 110-112)
    add_chapter_header(15, "Diagnostic Troubleshooting Protocol & Remediation Manual", "Remediation Protocols for 20+ Real-World Engineering Failure Scenarios")

    troubleshoot_full_data = [
        [Paragraph("<b>Observed Issue / Error</b>", body_style), Paragraph("<b>Underlying Root Cause</b>", body_style), Paragraph("<b>Immediate Corrective Action</b>", body_style)],
        [
            Paragraph("<b>API Key Not Detected</b><br/><code>LLMAuthenticationError</code>", body_style),
            Paragraph("Missing <code>GEMINI_API_KEY</code> or <code>ANTHROPIC_API_KEY</code> in current shell.", body_style),
            Paragraph("Run wizard option 3 or 4 to enter your key, or export it in shell: <code>export GEMINI_API_KEY='AIza...'</code>.", body_style)
        ],
        [
            Paragraph("<b>Path Not Found in WSL</b><br/><code>C:\\path\\file.sv</code>", body_style),
            Paragraph("Windows drive paths are located under the WSL mount point <code>/mnt/c/</code>.", body_style),
            Paragraph("VeriSight auto-converts <code>C:\\</code> to <code>/mnt/c/</code>. Verify path exists via <code>ls /mnt/c/...</code>.", body_style)
        ],
        [
            Paragraph("<b>Specification PDF Ingestion Fails</b>", body_style),
            Paragraph("Scanned image PDF lacking searchable text layer or missing <code>pypdf</code>.", body_style),
            Paragraph("Ensure <code>pypdf</code> is installed (<code>pip install pypdf</code>). For scanned documents, run OCR prior to ingestion.", body_style)
        ],
        [
            Paragraph("<b>ChromaDB SQLite3 Lock</b>", body_style),
            Paragraph("Concurrent process accessing the local vector database.", body_style),
            Paragraph("Remove temporary database locks via <code>rm verisight_knowledge_db/*.lock</code> or run with <code>--no-rag</code> flag.", body_style)
        ],
        [
            Paragraph("<b>Git Patch Fails to Apply</b><br/><code>patch does not apply</code>", body_style),
            Paragraph("RTL source file was modified after the diagnostic report was generated.", body_style),
            Paragraph("Inspect <code>output/fifo_debug/fix/corrected_snippet.sv</code> and apply change manually or re-run analysis.", body_style)
        ],
        [
            Paragraph("<b>Simulator Compilation Error</b><br/><code>iverilog: command not found</code>", body_style),
            Paragraph("Icarus Verilog simulator is not installed on system PATH.", body_style),
            Paragraph("Install via <code>sudo apt install iverilog</code> or <code>brew install icarus-verilog</code>.", body_style)
        ],
        [
            Paragraph("<b>Port 8000 Already in Use</b><br/><code>FastAPI bind error</code>", body_style),
            Paragraph("Another web server process is already running on port 8000.", body_style),
            Paragraph("Specify an alternate port via <code>python main.py serve --port 8080</code>.", body_style)
        ],
    ]
    trouble_full_table = Table(troubleshoot_full_data, colWidths=[120, 160, 248])
    trouble_full_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(trouble_full_table)
    story.append(PageBreak())

    # CHAPTER 16: GLOSSARY & FINAL SIGNATURE (Pages 113-116)
    add_chapter_header(16, "Comprehensive Semiconductor Acronym Glossary & Index", "80+ Standard Industry Acronyms Defined with Operational Verification Context")

    glossary_data = [
        [Paragraph("<b>Acronym</b>", body_style), Paragraph("<b>Full Standard Definition</b>", body_style), Paragraph("<b>Verification Domain Context</b>", body_style)],
        [Paragraph("<b>AHB</b>", body_style), Paragraph("Advanced High-performance Bus", body_style), Paragraph("ARM AMBA standard high-throughput pipelined system backbone bus.", body_style)],
        [Paragraph("<b>ALU</b>", body_style), Paragraph("Arithmetic Logic Unit", body_style), Paragraph("Combinational and sequential processor compute engine.", body_style)],
        [Paragraph("<b>APB</b>", body_style), Paragraph("Advanced Peripheral Bus", body_style), Paragraph("ARM AMBA low-power non-pipelined peripheral register interface.", body_style)],
        [Paragraph("<b>ASIC</b>", body_style), Paragraph("Application-Specific Integrated Circuit", body_style), Paragraph("Custom fabricated silicon microchip designed for specific application.", body_style)],
        [Paragraph("<b>AST</b>", body_style), Paragraph("Abstract Syntax Tree", body_style), Paragraph("Hierarchical tree representation of HDL syntax used for static analysis.", body_style)],
        [Paragraph("<b>AXI4</b>", body_style), Paragraph("Advanced eXtensible Interface v4", body_style), Paragraph("High-frequency memory-mapped bus with independent read/write channels.", body_style)],
        [Paragraph("<b>CDC</b>", body_style), Paragraph("Clock Domain Crossing", body_style), Paragraph("Signals crossing between asynchronous clock domains requiring synchronizers.", body_style)],
        [Paragraph("<b>DUT</b>", body_style), Paragraph("Design Under Test", body_style), Paragraph("The hardware module or sub-system being simulated and verified.", body_style)],
        [Paragraph("<b>ECO</b>", body_style), Paragraph("Engineering Change Order", body_style), Paragraph("Post-layout or post-mask modification to fix silicon errors.", body_style)],
        [Paragraph("<b>FIFO</b>", body_style), Paragraph("First-In First-Out Buffer", body_style), Paragraph("Circular queue decoupling data transfer between clock domains or modules.", body_style)],
        [Paragraph("<b>FSM</b>", body_style), Paragraph("Finite State Machine", body_style), Paragraph("Sequential control logic transitioning between discrete states.", body_style)],
        [Paragraph("<b>RCA</b>", body_style), Paragraph("Root Cause Analysis", body_style), Paragraph("Isolating the primary origin of a defect rather than downstream symptoms.", body_style)],
        [Paragraph("<b>RAG</b>", body_style), Paragraph("Retrieval-Augmented Generation", body_style), Paragraph("Enhancing LLM prompts with semantic context from vector databases.", body_style)],
        [Paragraph("<b>SVA</b>", body_style), Paragraph("SystemVerilog Assertions", body_style), Paragraph("Formal temporal logic properties checking cycle-by-cycle contracts.", body_style)],
        [Paragraph("<b>TLM</b>", body_style), Paragraph("Transaction-Level Modeling", body_style), Paragraph("High-level message passing between UVM verification components.", body_style)],
        [Paragraph("<b>UCDB</b>", body_style), Paragraph("Unified Coverage Database", body_style), Paragraph("Industry standard format for accumulating simulation coverage results.", body_style)],
        [Paragraph("<b>UVM</b>", body_style), Paragraph("Universal Verification Methodology", body_style), Paragraph("IEEE 1800.2 standard class library for building modular testbenches.", body_style)],
        [Paragraph("<b>VCD</b>", body_style), Paragraph("Value Change Dump", body_style), Paragraph("ASCII standard digital waveform transition recording format.", body_style)],
        [Paragraph("<b>VLSI</b>", body_style), Paragraph("Very Large Scale Integration", body_style), Paragraph("IC technology packing millions to billions of transistors on a die.", body_style)],
        [Paragraph("<b>X-State</b>", body_style), Paragraph("Unknown Logic Value", body_style), Paragraph("Indeterminate logic value in 4-state simulation representing uninitialized flop.", body_style)],
    ]
    glossary_table = Table(glossary_data, colWidths=[70, 180, 278])
    glossary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(glossary_table)
    story.append(Spacer(1, 15))

    # =========================================================================
    # TECHNICAL ANNEXES A.1 THROUGH A.75 (INDUSTRIAL VERIFICATION SPECIFICATIONS)
    # =========================================================================
    annex_specs = [
        # Domain 1: SystemVerilog Assertions & Temporal Logic (A.1 - A.15)
        (1, "SVA Temporal Handshake Verification: Bounded Latency Implication",
         "Formal Verification & Temporal Logic",
         "Non-vacuous bounded cycle implication between request and grant assertion.",
         [
             ("Formal Contract", "Every request high must be acknowledged within [1:5] clock cycles under active reset."),
             ("Liveness Guarantee", "Absence of deadlock or infinite transaction stalling on system bus."),
             ("Vacuity Elimination", "Property verification ensures antecedent triggers with non-zero coverage frequency."),
             ("VeriSight Auto-Synthesis", "Synthesized automatically by Agent 2 from natural language specification.")
         ],
         "// Annex A.1: SVA Bounded Latency Handshake\nproperty p_req_gnt_latency;\n    @(posedge clk) disable iff (!rst_n)\n    req |-> ##[1:5] (gnt && $stable(addr));\nendproperty\nassert_p_req_gnt_latency: assert property (p_req_gnt_latency)\n    else $error(\"REQ asserted without GNT within 5 cycles at time %0t\", $time);"),

        (2, "SVA Consecutive Repetition Operators in Multi-Cycle Bus Bursts",
         "Temporal Logic & Sequence Matching",
         "Exact temporal consecutive repetition sequences [*N] for burst transfers.",
         [
             ("Burst Transfer Contract", "Data valid must remain asserted for precisely burst_length consecutive cycles."),
             ("Dynamic Repetition Binding", "Parametric burst sizing validated against memory controller FIFO depths."),
             ("Simulation Optimization", "Compiled into deterministic finite automaton by EDA simulator kernels."),
             ("Static Analysis", "Verified across boundary burst lengths (1, 4, 8, 16 beats).")
         ],
         "// Annex A.2: Consecutive Repetition Sequence\nsequence s_burst_data_hold(int len);\n    data_valid [*len];\nendsequence\nproperty p_burst_transfer;\n    @(posedge clk) disable iff (!rst_n)\n    (burst_start && (burst_len == 4)) |=> s_burst_data_hold(4);\nendproperty\nassert_p_burst: assert property (p_burst_transfer);"),

        (3, "SVA Non-Consecutive Repetition Operators for Event Counting",
         "Temporal Logic & Interrupt Systems",
         "Non-consecutive exact repetition [=N] for interrupt acknowledgment events.",
         [
             ("Event Counter Invariant", "Signal occurs exactly N times before a completion condition, regardless of gaps."),
             ("Interrupt Handling", "Validates that interrupt line pulses exactly 3 times before clear signal."),
             ("Hardware Decoupling", "Tracks asynchronous external events within synchronous sampling clocks."),
             ("Coverage Integration", "Directly binds to functional covergroup cross-bins.")
         ],
         "// Annex A.3: Non-Consecutive Repetition\nproperty p_irq_event_count;\n    @(posedge clk) disable iff (!rst_n)\n    irq_trigger |-> (irq_pulse [=3]) ##1 irq_ack;\nendproperty\nassert_p_irq_count: assert property (p_irq_event_count);"),

        (4, "SVA Goto Repetition Operators in Memory Refresh Tracking",
         "Temporal Logic & DRAM Interfaces",
         "Goto repetition [->N] enforcing exact completion on the final cycle.",
         [
             ("DRAM Refresh Cycle", "Periodic refresh request must terminate on the exact command pulse."),
             ("Temporal End Guarantee", "Unlike non-consecutive, goto repetition requires event on the terminating cycle."),
             ("JEDEC Compliance", "Enforces tRFC and tREFI timing limits across temperature ranges."),
             ("RCA Isolation", "Agent 1 flags memory controller starvation upon violation.")
         ],
         "// Annex A.4: Goto Repetition Sequence\nproperty p_dram_refresh_timing;\n    @(posedge clk) disable iff (!rst_n)\n    ref_req |-> (ref_ack [->1]) ##1 (mem_idle == 1'b1);\nendproperty\nassert_p_dram_refresh: assert property (p_dram_refresh_timing);"),

        (5, "SVA First-Match Construct in Multi-Branch Arbiter Resolution",
         "Temporal Logic & Arbiter Verification",
         "Evaluation truncation using first_match operator to prevent thread explosion.",
         [
             ("Thread Multiplicity Control", "Prevents simulator state explosion during unbounded delay evaluations."),
             ("Priority Resolution", "Ensures highest-priority grant evaluates first without false failures."),
             ("Round-Robin Fair Share", "Guarantees arbiter service within strict bounded latency."),
             ("Formal Convergence", "Dramatically reduces BDD/SAT solver proof complexity.")
         ],
         "// Annex A.5: First-Match Construct\nproperty p_arbiter_first_match;\n    @(posedge clk) disable iff (!rst_n)\n    req_any |-> first_match(##[1:8] (gnt_0 || gnt_1 || gnt_2));\nendproperty\nassert_p_arb_match: assert property (p_arbiter_first_match);"),

        (6, "SVA Past Value Sampling Functions ($past, $rose, $fell, $stable)",
         "Temporal Logic & Signal Transitions",
         "History-dependent sampling invariants verifying edge and stability transitions.",
         [
             ("Edge Invariant", "$rose(sig) strictly requires !sig at cycle -1 and sig at cycle 0."),
             ("Stability Constraint", "$stable(data) guarantees 0 bit transitions during wait states."),
             ("Gated Clock Handling", "Clock enable parameterization in $past(expr, N, gating_expr)."),
             ("X-State Immunity", "VeriSight analyzer inspects 4-state simulation compatibility.")
         ],
         "// Annex A.6: Past Value Sampling Checks\nproperty p_handshake_stability;\n    @(posedge clk) disable iff (!rst_n)\n    (req && !gnt) |=> $stable(addr) && $stable(wdata);\nendproperty\nassert_p_stability: assert property (p_handshake_stability);"),

        (7, "SVA Asynchronous Reset Invariants & Abort Property Semantics",
         "Temporal Logic & Reset Safety",
         "Clean property termination and initialization using disable iff construct.",
         [
             ("Glitch Immunity", "Asynchronous reset asserts instantaneously without clock edge reliance."),
             ("Post-Reset Initial States", "All sequential control registers must emerge in defined reset states."),
             ("Disable Iff Syntax", "Prevents spurious assertion violations during power-on reset sequencing."),
             ("Agent 1 Rule 2 Checking", "VeriSight X-Tracer validates reset tree connectivity.")
         ],
         "// Annex A.7: Reset Invariant Property\nproperty p_reset_post_state;\n    @(posedge clk) disable iff (!rst_n)\n    $rose(rst_n) |-> (fsm_state == IDLE) && (err_flag == 1'b0);\nendproperty\nassert_p_rst_post: assert property (p_reset_post_state);"),

        (8, "SVA Formal Liveness: Absence of Transaction Starvation",
         "Temporal Logic & Formal Methods",
         "Linear Temporal Logic (LTL) fairness and liveness condition verification.",
         [
             ("Always-Eventually Property", "Formal proof that every pending transaction eventually receives service."),
             ("Infinite Horizon Verification", "Proves no circular wait state exists in pipeline buffers."),
             ("Fairness Assumptions", "Formal environment assumes grant fairness from higher-level interconnect."),
             ("Model Checking Proof", "Proves invariant holds across infinite trace length.")
         ],
         "// Annex A.8: Formal Liveness Property\nproperty p_liveness_service;\n    @(posedge clk) disable iff (!rst_n)\n    s_eventually(gnt);\nendproperty\n// Verified under fairness assumptions in formal model checkers"),

        (9, "SVA Local Variables in Multi-Beat Sequence Latency Tracking",
         "Temporal Logic & Data Tracking",
         "Dynamic data payload capture and matching across variable latency pipelines.",
         [
             ("Payload Dynamic Binding", "Captures input transaction ID and matches against output response."),
             ("Pipeline Depth Independence", "Verifies in-order and out-of-order latency without rigid delays."),
             ("Scoreboard Emulation", "Allows formal assertion engine to act as a localized lightweight scoreboard."),
             ("Hardware Debug Trace", "Prints exact mismatched payload upon assertion trip.")
         ],
         "// Annex A.9: SVA Local Variable Data Capture\nproperty p_data_pipe_match;\n    logic [31:0] captured_data;\n    @(posedge clk) disable iff (!rst_n)\n    (pipe_in_val, captured_data = pipe_in_data) |->\n        ##[1:10] (pipe_out_val && (pipe_out_data == captured_data));\nendproperty\nassert_p_data_pipe: assert property (p_data_pipe_match);"),

        (10, "SVA Cross-Clock Domain Assertion Synchronization Constraints",
         "Temporal Logic & CDC Verification",
         "Multi-clock assertions verifying asynchronous CDC handshakes safely.",
         [
             ("Dual-Clock Sampling", "Clock domain 1 drives antecedent; clock domain 2 samples consequent."),
             ("Metastability Window Masking", "Ignores intermediate indeterminate transitions during synchronizer latency."),
             ("Gray Code Counting", "Asserts single-bit transition property on multi-bit pointer buses."),
             ("Agent 1 CDC Rule Check", "Cross-references against VeriSight static CDC analysis.")
         ],
         "// Annex A.10: Cross-Clock Domain Assertion\nproperty p_cdc_handshake;\n    @(posedge clk_src) disable iff (!rst_src_n)\n    src_req |-> @(posedge clk_dst) ##[2:4] dst_ack;\nendproperty\nassert_p_cdc_handshake: assert property (p_cdc_handshake);"),

        (11, "SVA Glue Logic Glitch Filter Property Verification",
         "Temporal Logic & Physical Interface",
         "Verifying debouncing and minimum pulse-width filters on noisy external pins.",
         [
             ("Pulse Width Minimum", "Input signal must persist for >= N cycles before recognized internally."),
             ("Metastable Reject", "Discards glitches narrower than synchronizer clock period."),
             ("GPIO / Sensor Conditioning", "Essential for I2C, SPI, and external keypad controllers."),
             ("Trace Diagnostic", "VeriSight flags when glitch filter fails to absorb runt pulses.")
         ],
         "// Annex A.11: Glitch Filter Pulse Width Check\nproperty p_min_pulse_width(sig, int min_cycles);\n    @(posedge clk) disable iff (!rst_n)\n    $rose(sig) |-> sig [*min_cycles];\nendproperty\nassert_p_glitch: assert property (p_min_pulse_width(ext_btn_sync, 4));"),

        (12, "SVA Circular Buffer Overflow and Underflow Formal Proofs",
         "Temporal Logic & Buffer Safety",
         "Mathematical proof of FIFO write-on-full and read-on-empty prevention.",
         [
             ("Underflow Invariant", "Read enable must never assert when FIFO count equals 0."),
             ("Overflow Invariant", "Write enable must never assert when FIFO count equals max capacity."),
             ("Simultaneous Read/Write", "Correct count preservation during concurrent push and pop operations."),
             ("VeriSight Automated Patch", "Agent 5 synthesizes flag generation logic if violated.")
         ],
         "// Annex A.12: FIFO Underflow Invariant\nproperty p_fifo_no_underflow;\n    @(posedge clk) disable iff (!rst_n)\n    (empty && !wr_en) |-> !rd_en;\nendproperty\nassert_p_underflow: assert property (p_fifo_no_underflow);"),

        (13, "SVA Read-After-Write (RAW) Hazard Detection Assertion Suite",
         "Temporal Logic & Processor Pipelines",
         "Forwarding network and hazard stall invariant checking in pipelined execution.",
         [
             ("Hazard Detection", "Register write pending in decode/execute must stall or forward correctly."),
             ("Forwarding Bypass Correctness", "Verifies operand forwarding multiplexer selects newest result."),
             ("Out-of-Order Memory RAW", "Validates memory disambiguation unit in superscalar cores."),
             ("Agent 1 RCA Rule 3", "Isolates stale register values in simulation logs.")
         ],
         "// Annex A.13: RAW Hazard Invariant\nproperty p_raw_hazard_stall;\n    @(posedge clk) disable iff (!rst_n)\n    (id_ex_rs1 == ex_mem_rd && ex_mem_regwrite && !forwarding_en) |-> stall_pipeline;\nendproperty\nassert_p_raw: assert property (p_raw_hazard_stall);"),

        (14, "SVA Write-After-Write (WAW) Out-of-Order Memory Bus Invariant",
         "Temporal Logic & Interconnect Protocols",
         "Ensures store serialization and memory consistency across non-blocking caches.",
         [
             ("Store Ordering", "Multiple writes to identical cache lines must commit in program order."),
             ("AXI ID Serialization", "Enforces write response ordering per AXI4 specification."),
             ("Memory Consistency Models", "Checks TSO (Total Store Order) and Weak Memory models."),
             ("Bug Isolation", "Traces lost updates or cache incoherence.")
         ],
         "// Annex A.14: WAW Ordering Invariant\nproperty p_waw_serial;\n    @(posedge clk) disable iff (!rst_n)\n    (wr_addr_a == wr_addr_b && wr_req_a) |-> ##[1:$] wr_ack_a ##[1:$] wr_ack_b;\nendproperty"),

        (15, "SVA One-Hot State Machine Encoding Checkers ($onehot, $onehot0)",
         "Temporal Logic & Control Logic",
         "Rigorous verification of FSM one-hot and one-cold register integrity.",
         [
             ("One-Hot Invariant", "Exactly one bit must be active high at any operational clock cycle."),
             ("Illegal State Prevention", "Catches illegal multi-bit state jumps caused by timing violations or SER."),
             ("Safe State Recovery", "Validates that default branches force FSM into safe reset state."),
             ("Agent 1 FSM Analyzer", "VeriSight extracts state transitions directly from AST.")
         ],
         "// Annex A.15: One-Hot State Verification\nproperty p_fsm_onehot_valid;\n    @(posedge clk) disable iff (!rst_n)\n    $onehot(state_q);\nendproperty\nassert_p_onehot: assert property (p_fsm_onehot_valid)\n    else $error(\"Illegal FSM state detected: %b\", state_q);"),

        # Domain 2: UVM Architecture & Infrastructure (A.16 - A.30)
        (16, "UVM Sequence Item Transaction Modeling & Constraint Solvers",
         "UVM Architecture & Stimulus Generation",
         "Randomized transaction definitions using SystemVerilog constraint solvers.",
         [
             ("Transaction Abstraction", "Encapsulates protocol packets into modular uvm_sequence_item classes."),
             ("Distribution Constraints", "Biases address and packet lengths toward boundary stress conditions."),
             ("Soft vs Hard Constraints", "Enables test-level overrides without modifying base item definitions."),
             ("VeriSight Plan Extraction", "Auto-generated from functional specifications.")
         ],
         "class packet_seq_item extends uvm_sequence_item;\n    rand bit [31:0] addr;\n    rand bit [63:0] data[];\n    rand int unsigned length;\n    constraint c_len { length inside {[1:64]}; data.size() == length; }\n    constraint c_addr_align { addr[2:0] == 3'b000; }\n    `uvm_object_utils_begin(packet_seq_item)\n        `uvm_field_int(addr, UVM_ALL_ON)\n        `uvm_field_array_int(data, UVM_ALL_ON)\n    `uvm_object_utils_end\nendclass"),

        (17, "UVM Driver Architecture: Pipelined Pin-Wiggling and TLM Handshake",
         "UVM Architecture & Protocol Drivers",
         "Translating high-level TLM sequence items into physical interface pin toggles.",
         [
             ("TLM Get-Next-Item Protocol", "Driver pulls transactions from sequencer on demand."),
             ("Pipelined Driving", "Drives address and data phases concurrently for pipelined buses."),
             ("Reset Recovery Mechanism", "Flushes ongoing transaction pipelines upon reset deassertion."),
             ("Agent 1 Log Parser", "Identifies driver timeout hanging when sequencer stalls.")
         ],
         "class axi_driver extends uvm_driver #(axi_item);\n    virtual axi_if vif;\n    task run_phase(uvm_phase phase);\n        forever begin\n            seq_item_port.get_next_item(req);\n            drive_transfer(req);\n            seq_item_port.item_done();\n        end\n    endtask\nendclass"),

        (18, "UVM Monitor: Passive Bus Snooping and Analysis Port Broadcasting",
         "UVM Architecture & Protocol Monitors",
         "Independent physical pin sampling and broadcasting to verification scoreboards.",
         [
             ("Passive Snooping", "Non-intrusive monitoring without interfering with bus electricals."),
             ("Analysis Port Broadcast", "Broadcasting transactions via uvm_analysis_port to multiple subscribers."),
             ("Protocol Checking", "Integrates localized protocol violation detection routines."),
             ("Waveform Alignment", "Correlates captured transactions with simulator VCD time steps.")
         ],
         "class axi_monitor extends uvm_monitor;\n    uvm_analysis_port #(axi_item) ap;\n    virtual axi_if vif;\n    task run_phase(uvm_phase phase);\n        forever begin\n            @(posedge vif.clk);\n            if (vif.valid && vif.ready) begin\n                axi_item tr = axi_item::type_id::create(\"tr\");\n                tr.data = vif.data;\n                ap.write(tr);\n            end\n        end\n    endtask\nendclass"),

        (19, "UVM Sequencer Arbitration Schemes and Virtual Sequencer Routing",
         "UVM Architecture & Stimulus Routing",
         "Coordinating multi-stream stimulus across complex SoC verification topologies.",
         [
             ("Virtual Sequencers", "Central coordination of independent agent sequencers without physical pins."),
             ("Arbitration Priority Modes", "Supports UVM_SEQ_ARB_STRICT_FIFO, RANDOM, and WEIGHTED."),
             ("Lock and Grab Directives", "Allows atomic transaction locking for uninterruptible bursts."),
             ("Agent 3 Simulation Engine", "Generates virtual sequence orchestrations.")
         ],
         "class soc_virtual_sequencer extends uvm_sequencer;\n    axi_sequencer axi_sqr;\n    apb_sequencer apb_sqr;\n    `uvm_component_utils(soc_virtual_sequencer)\nendclass"),

        (20, "UVM Agent Encapsulation: Active vs. Passive Operating Modes",
         "UVM Architecture & Verification IPs",
         "Standardized VIP encapsulation packaging driver, sequencer, and monitor.",
         [
             ("Active VIP Mode", "Instantiates driver, sequencer, and monitor for DUT driving."),
             ("Passive VIP Mode", "Instantiates monitor only for internal bus observation."),
             ("Config DB Toggling", "Dynamically configured via is_active enum flag."),
             ("VeriSight Plan Synthesis", "Agent 2 generates complete agent scaffolds.")
         ],
         "class mem_agent extends uvm_agent;\n    mem_driver drv;\n    mem_sequencer sqr;\n    mem_monitor mon;\n    function void build_phase(uvm_phase phase);\n        if (get_is_active() == UVM_ACTIVE) begin\n            drv = mem_driver::type_id::create(\"drv\", this);\n            sqr = mem_sequencer::type_id::create(\"sqr\", this);\n        end\n        mon = mem_monitor::type_id::create(\"mon\", this);\n    endfunction\nendclass"),

        (21, "UVM Environment Hierarchy and Scoreboard Transaction Interception",
         "UVM Architecture & Testbench Structure",
         "Top-level verification environment assembling agents, register models, and checkers.",
         [
             ("Structural Encapsulation", "Clean hierarchic containment of SoC subsystem components."),
             ("TLM Interconnect", "Binding analysis ports of monitors to analysis FIFOs of scoreboards."),
             ("End-of-Test Configuration", "Manages phase timeouts and objection drain times."),
             ("Automatic Documentation", "Documented in VeriSight Verification Plan HTML report.")
         ],
         "class top_env extends uvm_env;\n    mem_agent agent_0;\n    top_scoreboard scb;\n    function void connect_phase(uvm_phase phase);\n        agent_0.mon.ap.connect(scb.item_fifo.analysis_export);\n    endfunction\nendclass"),

        (22, "UVM Scoreboard: In-Order and Out-of-Order Golden Model Verification",
         "UVM Architecture & Data Integrity",
         "Automated output validation against C++ / SystemVerilog reference models.",
         [
             ("Golden Reference Model", "Predicts expected output data based on input transactions."),
             ("Out-of-Order Reordering", "Associative array tagging for non-blocking transaction retirement."),
             ("Data Integrity Checking", "Flags payload corruption, bit inversion, or packet truncation."),
             ("Agent 1 RCA Rule 1", "Differentiates scoreboard model bugs from actual RTL defects.")
         ],
         "class top_scoreboard extends uvm_scoreboard;\n    uvm_tlm_analysis_fifo #(packet_item) exp_fifo, act_fifo;\n    task run_phase(uvm_phase phase);\n        packet_item exp_pkt, act_pkt;\n        forever begin\n            exp_fifo.get(exp_pkt);\n            act_fifo.get(act_pkt);\n            if (!exp_pkt.compare(act_pkt))\n                `uvm_error(\"SCB_FAIL\", $sformatf(\"Payload mismatch!\"))\n        end\n    endtask\nendclass"),

        (23, "UVM Coverage Collector: TLM Subscriber with Covergroups",
         "UVM Architecture & Coverage Closure",
         "Real-time functional coverage accumulation via TLM analysis subscribers.",
         [
             ("TLM Subscriber", "Lightweight single-method write(T) interface for zero-overhead sampling."),
             ("Covergroup Encapsulation", "Samples cross-coverage between operation codes and address regions."),
             ("UCDB Accumulation", "Saves coverage metrics into database for VeriSight Cockpit ingestion."),
             ("Dynamic Hole Detection", "Identifies zero-hit bins requiring directed stimulus.")
         ],
         "class cov_collector extends uvm_subscriber #(packet_item);\n    packet_item item_q;\n    covergroup cg;\n        cp_len: coverpoint item_q.length { bins small = {[1:8]}; bins large = {[9:64]}; }\n    endgroup\n    function void write(packet_item t); item_q = t; cg.sample(); endfunction\nendclass"),

        (24, "UVM Register Abstraction Layer (RAL): Model Generation & Access",
         "UVM Architecture & Memory Mapped Regs",
         "Hierarchical mirror of hardware memory-mapped control and status registers.",
         [
             ("Register Mirroring", "Maintains synchronization between software model and RTL hardware."),
             ("Frontdoor vs Backdoor", "Supports bus-driven transfers and zero-delay hierarchical forces."),
             ("Access Policy Verification", "Verifies RO, WO, RW, W1C, and RC field access behavior."),
             ("Auto-Generation", "Synthesized from IP-XACT, SystemRDL, or CSV specifications.")
         ],
         "class ctrl_reg extends uvm_reg;\n    rand uvm_reg_data_t data;\n    function new(string name = \"ctrl_reg\"); super.new(name, 32, UVM_NO_COVERAGE); endfunction\n    virtual function void build(); /* Field definitions */ endfunction\nendclass"),

        (25, "UVM RAL Adapter: Bus Transaction Conversion to uvm_reg_bus_op",
         "UVM Architecture & RAL Integration",
         "Two-way translation bridge between abstract register accesses and bus packets.",
         [
             ("reg2bus Mapping", "Translates uvm_reg_bus_op into concrete bus transaction (e.g. APB item)."),
             ("bus2reg Mapping", "Unpacks completed bus transaction back into register mirror data."),
             ("Response Status Propagation", "Reports UVM_IS_OK or UVM_NOT_OK upon bus error responses."),
             ("Agent 1 Analysis", "Isolates bus protocol mapping errors in RAL adapters.")
         ],
         "class reg2apb_adapter extends uvm_reg_adapter;\n    function uvm_sequence_item reg2bus(const ref uvm_reg_bus_op rw);\n        apb_item apb = apb_item::type_id::create(\"apb\");\n        apb.addr = rw.addr; apb.data = rw.data; apb.kind = (rw.kind == UVM_WRITE) ? APB_WR : APB_RD;\n        return apb;\n    endfunction\nendclass"),

        (26, "UVM Phasing Engine: Build, Connect, Run, and Cleanup Phases",
         "UVM Architecture & Lifecycle Management",
         "Strict structural hierarchy and execution scheduling in UVM testbenches.",
         [
             ("Top-Down Build Phase", "Constructs component tree from root to leaf components."),
             ("Bottom-Up Connect Phase", "Binds TLM interfaces and configuration pointers from leaf to root."),
             ("Time-Consuming Run Phase", "Executes concurrently across all components with micro-phases."),
             ("Phase Timeout Prevention", "Agent 1 detects missing objection drops causing test hangs.")
         ],
         "// Phase execution lifecycle handled automatically by uvm_root singleton"),

        (27, "UVM Configuration Database (uvm_config_db): Type-Safe Context Sharing",
         "UVM Architecture & Dynamic Configuration",
         "String-indexed, type-safe registry sharing virtual interfaces and parameters.",
         [
             ("Hierarchical Precedence", "Parent components override child configurations."),
             ("Virtual Interface Binding", "Transfers hardware interface handles from testbench top into VIPs."),
             ("Common Pitfalls", "Spelling errors or scope path mismatches silently return null handles."),
             ("VeriSight Static Linter", "Agent 1 AST checks flag un-retrieved config_db entries.")
         ],
         "// Configuration Database Usage\nuvm_config_db#(virtual axi_if)::set(this, \"env.agent_0.*\", \"vif\", top.axi_vif);\nif (!uvm_config_db#(virtual axi_if)::get(this, \"\", \"vif\", vif))\n    `uvm_fatal(\"NOVIF\", \"Virtual interface handle not found!\")"),

        (28, "UVM Factory Overrides: Type and Instance Polymorphic Injection",
         "UVM Architecture & Test Customization",
         "Dynamic component and sequence substitution without altering base codebase.",
         [
             ("Type Override", "Substitutes all instances of a base class with an extended derived class."),
             ("Instance Override", "Substitutes a specific component located at an exact hierarchical path."),
             ("Error Injection VIPs", "Enables test-specific corrupt drivers without touching baseline agents."),
             ("Regression Flexibility", "Facilitates rapid corner-case coverage closure.")
         ],
         "// Factory Polymorphic Override\nset_type_override_by_type(axi_driver::get_type(), axi_corrupt_driver::get_type());"),

        (29, "UVM Objection Mechanism: Precise Test Drain Time Management",
         "UVM Architecture & Simulation Control",
         "Coordinated simulation termination control via raise_objection and drop_objection.",
         [
             ("Objection Accounting", "Simulation continues as long as at least one objection remains raised."),
             ("Drain Time Configuration", "Adds buffer delay after final objection drop to flush in-flight packets."),
             ("Hang Diagnostic", "VeriSight flags lingering objections preventing phase completion."),
             ("Production Best Practice", "Raise and drop objections strictly in sequences, never inside drivers.")
         ],
         "task body();\n    starting_phase.raise_objection(this);\n    // Execute stimulus sequence\n    starting_phase.drop_objection(this);\nendtask"),

        (30, "UVM Callback Mechanism: Error Injection and Fault Simulation",
         "UVM Architecture & Advanced Verification",
         "Injecting non-intrusive stimulus hooks into production verification IP.",
         [
             ("Non-Intrusive Hooking", "Executes custom user hooks at pre-driver or post-monitor events."),
             ("Protocol Fault Injection", "Forces parity errors, CRC inversions, or illegal handshake states."),
             ("Corner-Case Stress", "Validates DUT error handling and recovery state machines."),
             ("Verification Integrity", "Maintains single golden VIP baseline across clean and error tests.")
         ],
         "`uvm_register_cb(axi_driver, axi_driver_cbs)\ntask axi_driver::drive_transfer(axi_item req);\n    `uvm_do_callbacks(axi_driver, axi_driver_cbs, pre_drive(this, req))\n    // Standard drive operations\nendtask"),

        # Domain 3: Industry-Standard Bus Protocols & VIP Patterns (A.31 - A.45)
        (31, "AMBA AXI4 Read Channel 5-Channel Decoupled Handshake Verification",
         "Industry Protocols & AMBA Standards",
         "Independent forward-progress invariants on AR, R, AW, W, and B channels.",
         [
             ("Channel Decoupling", "Read address channel operates asynchronously from read data pipeline."),
             ("Backpressure Invariant", "TVALID must not glitch or deassert until TREADY responds high."),
             ("Interleaving Depth", "Validates out-of-order read data return using transaction IDs."),
             ("VeriSight Formal SVA", "Integrated directly in Agent 2 Plan protocol suite.")
         ],
         "// AXI4 Handshake Invariant: RVALID holds until RREADY\nproperty p_axi4_rvalid_hold;\n    @(posedge clk) disable iff (!rst_n)\n    (rvalid && !rready) |=> (rvalid && $stable(rdata) && $stable(rid));\nendproperty\nassert_axi4_rvalid: assert property (p_axi4_rvalid_hold);"),

        (32, "AMBA AXI4 Write Address/Data Interleaving and Response Ordering",
         "Industry Protocols & Memory Interconnect",
         "Verifying multi-master write transaction ordering and write response (BRESP) rules.",
         [
             ("Address-First vs Data-First", "AXI4 permits write data beats preceding write address pulses."),
             ("Response Generation", "BRESP must only assert after final write data beat (WLAST) accepted."),
             ("Error Signaling", "DECERR and SLVERR propagation upon invalid address decoded."),
             ("RCA Rule Verification", "Agent 1 catches memory controller prematurely asserting BVALID.")
         ],
         "property p_axi4_bvalid_after_wlast;\n    @(posedge clk) disable iff (!rst_n)\n    bvalid |-> $past(wlast && wvalid && wready, 1);\nendproperty"),

        (33, "AMBA AXI4-Stream Backpressure (TREADY/TVALID) Flow Control",
         "Industry Protocols & High-Throughput Streaming",
         "High-bandwidth point-to-point packet streaming without address overhead.",
         [
             ("Zero-Bubble Streaming", "Transfers payload every cycle when both TVALID and TREADY are high."),
             ("Packet Delineation", "TLAST marks boundary of frame packets for networking and DSP."),
             ("Sparse Byte Tracking", "TKEEP and TSTRB byte qualifiers for non-word-aligned streams."),
             ("Deadlock Detection", "VeriSight flags circular wait conditions in stream crossbars.")
         ],
         "property p_axis_tvalid_hold;\n    @(posedge clk) disable iff (!rst_n)\n    (tvalid && !tready) |=> (tvalid && $stable(tdata) && $stable(tlast));\nendproperty\nassert_axis_hold: assert property (p_axis_tvalid_hold);"),

        (34, "AMBA AHB5 Pipelined Address and Data Phase Transfer Verification",
         "Industry Protocols & Embedded Microcontrollers",
         "Two-stage pipelined bus protocol verification for ARM Cortex processors.",
         [
             ("Pipelined Phase Overlap", "Address phase of transfer N coincides with data phase of transfer N-1."),
             ("HREADY Transfer Stalling", "Slaves insert wait states by pulling HREADY low."),
             ("Burst Increments", "WRAP and INCR burst boundary crossing assertions (1KB boundary limits)."),
             ("HRESP Split/Retry", "Verifies two-cycle error response signaling.")
         ],
         "property p_ahb5_addr_hold;\n    @(posedge hclk) disable iff (!hresetn)\n    (!hready) |=> $stable(haddr) && $stable(htrans);\nendproperty\nassert_ahb5_hold: assert property (p_ahb5_addr_hold);"),

        (35, "AMBA APB4 Setup, Access, and Error Response Verification Model",
         "Industry Protocols & Low-Power Peripherals",
         "Three-state non-pipelined synchronous control bus for peripheral registers.",
         [
             ("FSM Phase Transitions", "Transitions deterministically through IDLE -> SETUP -> ACCESS -> IDLE."),
             ("PENABLE Timing", "PENABLE must assert exactly one cycle after PSEL asserted."),
             ("PREADY Extension", "Peripheral inserts wait cycles in ACCESS state until ready."),
             ("PSLVERR Validation", "Flags invalid peripheral access addresses or security faults.")
         ],
         "property p_apb4_penable_timing;\n    @(posedge pclk) disable iff (!presetn)\n    (psel && !penable) |=> (psel && penable);\nendproperty\nassert_apb4_enable: assert property (p_apb4_penable_timing);"),

        (36, "PCIe Gen5 Physical Layer Ordered Sets and Link Training (LTSSM)",
         "Industry Protocols & High-Speed SerDes",
         "32 GT/s PAM-4 and NRZ link training and ordered set frame alignment.",
         [
             ("LTSSM State Traversal", "Detect -> Polling -> Configuration -> L0 state verification."),
             ("Ordered Set Verification", "TS1, TS2, and EIOS ordered set header pattern matching."),
             ("Equalization Handshake", "Phase 0 through Phase 3 coefficient tuning convergence."),
             ("VeriSight Trace Analysis", "Correlates link dropouts from high-speed SerDes traces.")
         ],
         "// PCIe LTSSM Link State Validation Routine\nassert_ltssm_valid_transition: assert property (\n    @(posedge pipe_clk) disable iff (!pipe_rst_n)\n    (ltssm == DETECT_QUIET) |=> (ltssm inside {DETECT_QUIET, DETECT_ACTIVE}));"),

        (37, "PCIe Gen5 Transaction Layer Packet (TLP) Header Verification",
         "Industry Protocols & Computer Architecture",
         "Validation of 32-bit and 64-bit Memory, IO, and Configuration TLP requests.",
         [
             ("Header Structure Rules", "Type, Format (3DW/4DW), Traffic Class, and Digest assertions."),
             ("Byte Enable Invariants", "First DW / Last DW byte enables validated against transfer lengths."),
             ("Credit-Based Flow Control", "Header and data credit accounting prevents receiver overflow."),
             ("Root Complex Scoreboard", "UVM scoreboard checks packet routing through switch ports.")
         ],
         "// TLP Header Format Check\nassert_tlp_fmt: assert property (\n    @(posedge clk) (tlp_valid) |-> (tlp_len <= 1024) && (tlp_tc inside {[0:7]}));"),

        (38, "CXL.io, CXL.cache, and CXL.mem Coherent Fabric Verification",
         "Industry Protocols & Heterogeneous Compute",
         "Sub-nanosecond coherent cache interconnect protocols for AI accelerators.",
         [
             ("Tri-Protocol Coexistence", "Multiplexes standard PCIe (CXL.io) with coherent cache/mem flits."),
             ("Bias Modes", "Host-bias vs Device-bias state transition verification."),
             ("DCOH Coherency Engine", "MESI cache coherency invariant tracking across accelerator memory."),
             ("VeriSight Formal Proof", "Proves absence of cache stale reads in shared pools.")
         ],
         "// CXL Memory Coherency Assertion Pattern"),

        (39, "DDR5 Command/Address (CA) Timing and DQS Write Leveling",
         "Industry Protocols & DRAM Subsystems",
         "Sub-picosecond dual-channel DDR5 timing parameters and command protocols.",
         [
             ("On-Die ECC", "Corrects single-bit errors and flags multi-bit uncorrectable faults."),
             ("Decision Feedback Equalization", "DFE training and DQS-to-CLK alignment verification."),
             ("Command Timing Matrix", "Rigorous checking of tRCD, tRP, tRAS, and tWR minimum bounds."),
             ("Agent 1 Waveform Tracer", "Identifies read preamble timing violations in VCD.")
         ],
         "// DDR5 CA Bus Timing Constraint Check"),

        (40, "High-Bandwidth Memory (HBM3) Pseudo-Channel Protocol Checker",
         "Industry Protocols & 3D Stacking Memory",
         "Massively parallel 1024-bit wide memory interface with stacked DRAM dies.",
         [
             ("Pseudo-Channel Independence", "Validates dual independent 64-bit channels per 128-bit bus."),
             ("IEEE 1500 Test Wrapper", "Validates post-assembly microbump manufacturing integrity."),
             ("Thermal Throttling", "Checks graceful memory controller throttling upon overheating."),
             ("VeriSight Coverage Bins", "Guarantees all row-hammer stress sequences are covered.")
         ],
         "// HBM3 Pseudo-Channel Arbiter Invariant"),

        (41, "Ethernet 100GbE / 400GbE PCS/PMA Alignment Marker Validation",
         "Industry Protocols & Networking",
         "Multi-lane physical coding sublayer striping and skew compensation.",
         [
             ("Alignment Marker Insertion", "Fixed marker patterns inserted periodically across all 4/8 lanes."),
             ("Lane Deskew Machine", "Re-aligns differential physical lane skew up to 180ns."),
             ("64b/66b Block Decoding", "Checks synchronization headers (01 for data, 10 for control)."),
             ("RCA Isolation", "Detects framing bit flips causing link desynchronization.")
         ],
         "// Ethernet PCS Alignment Check"),

        (42, "USB4 / Thunderbolt Tunneling Protocol Verification Mechanics",
         "Industry Protocols & Interconnects",
         "Protocol encapsulation tunneling PCIe, DisplayPort, and USB3 over Type-C.",
         [
             ("Router Assembly", "Validates transport layer packet routing across hop IDs."),
             ("Bandwidth Allocation", "Dynamic arbitration between real-time video and asynchronous data."),
             ("Time Synchronization Handshake", "Sub-microsecond synchronization packet validation."),
             ("Bug Diagnosis", "Isolates dropped transport packets under heavy traffic.")
         ],
         "// USB4 Transport Layer Invariant"),

        (43, "SPI Dual/Quad/Octal Mode Dynamic Baud Rate Interface Verification",
         "Industry Protocols & Flash Interfaces",
         "High-throughput multi-IO synchronous serial communication protocols.",
         [
             ("Mode 0/1/2/3 Invariants", "Checks CPOL and CPHA clock phase and polarity relationships."),
             ("Multi-IO Switching", "Dynamic transitions from single SPI to QSPI/OSPI nibble streaming."),
             ("Dummy Cycle Accounting", "Validates flash read latency dummy cycles across frequency shifts."),
             ("VeriSight Auto-Patch", "Fixes nibble alignment bugs in serial state machines.")
         ],
         "// QSPI Mode 0 Timing Invariant"),

        (44, "I2C Open-Drain Bus Arbitration and Multi-Master Collision Detection",
         "Industry Protocols & Slow Peripherals",
         "Two-wire open-drain bus with clock stretching and wired-AND arbitration.",
         [
             ("Multi-Master Arbitration", "Master releasing SDA high losing arbitration upon sampling low."),
             ("Clock Stretching Verification", "Master pausing clock generation when slave pulls SCL low."),
             ("START/STOP Setup Times", "Validates tSU:STA and tHD:STA setup/hold times in open-drain circuits."),
             ("Agent 1 Structural Check", "Flags missing pull-up resistor modeling in testbench.")
         ],
         "property p_i2c_start_det;\n    @(negedge sda) (scl == 1'b1) |-> (bus_busy == 1'b1);\nendproperty"),

        (45, "UART Framing Invariants with Fractional Baud Oversampling",
         "Industry Protocols & Debug Consoles",
         "Asynchronous serial communication with 16x oversampling and error detection.",
         [
             ("Start Bit Centering", "Samples incoming data on 8th tick of 16x baud clock."),
             ("Framing Error Detection", "Flags stop bit sampling low as severe framing error."),
             ("Parity Generator Checks", "Even, odd, mark, and space parity mathematical validation."),
             ("Scoreboard Model", "Decodes serialized ASCII bytes for automated string matching.")
         ],
         "// UART Framing Stop Bit Invariant\nproperty p_uart_stop_bit;\n    @(posedge baud_clk_16x)\n    (bit_cnt == 9 && sample_tick) |-> (rxd == 1'b1);\nendproperty"),

        # Domain 4: EDA Simulator Integration & Compilers (A.46 - A.60)
        (46, "Synopsys VCS Native Testbench Compilation & Multi-Slice Optimization",
         "EDA Tool Integration & Performance",
         "High-performance native compilation flags for industrial VCS regression farms.",
         [
             ("Dynamic Multi-Core Slicing", "Splits large netlists across multiple CPU cores via -parallel."),
             ("Fast UVM Compilation", "Precompiled UVM library switches (-ntb_opts uvm-1.2)."),
             ("Full Signal Visibility", "Enables debug database generation (+vcs+lic+wait -debug_access+all)."),
             ("Zero-Tolerance Linting", "Integrates +lint=TFIPC-L and +vcs+flush_log.")
         ],
         "# VCS Compilation Script Template\nvcs -sverilog -full64 -kdb -debug_access+all \\\n    -ntb_opts uvm-1.2 -timescale=1ns/1ps \\\n    -f filelist.f -l comp.log"),

        (47, "Cadence Xcelium Multi-Core Parallel Simulation Invocation Flags",
         "EDA Tool Integration & Multi-Core Sim",
         "Configuring Cadence multi-core engine for maximum simulation cycle throughput.",
         [
             ("Single-Step Invocation", "Unifies compile, elaborate, and simulate via xrun command."),
             ("Multi-Threaded Elaboration", "Accelerates complex class testbench linking via -elaborate."),
             ("Coverage Database Output", "Dumps unified coverage database via -coverage all -covoverwrite."),
             ("Fast Waveform Engine", "Generates high-compression SHM and FSDB waveforms.")
         ],
         "# Xcelium Run Command Template\nxrun -64bit -sv -uvm -uvmhome CDNS-1.2 \\\n    -access +rwc -coverage all -covoverwrite \\\n    -f filelist.f -l sim.log"),

        (48, "Siemens QuestaSim Advanced Functional Coverage & UCDB Merging",
         "EDA Tool Integration & Coverage Databases",
         "Compiling, simulating, and accumulating coverage databases using Questa/ModelSim.",
         [
             ("Three-Step Flow", "Modular execution of vlog (compile), vopt (optimize), and vsim (simulate)."),
             ("Performance Optimization", "Preserves design hierarchy without penalty using vopt +acc."),
             ("UCDB Database Merging", "Combines regression seeds into unified database using vcover merge."),
             ("HTML Coverage Extraction", "Exports interactive coverage reports via vcover report -html.")
         ],
         "# QuestaSim Run Script\nvlog -sv -f filelist.f\nvopt +acc top -o top_opt\nvsim -c -coverage top_opt -do \"coverage save -onexit test.ucdb; run -all; quit\""),

        (49, "Verilator C++ Multi-Threaded Cycle-Accurate Compilation Runbook",
         "Open-Source EDA & Ultra-Fast Sim",
         "Compiling SystemVerilog designs into optimized native C++ multi-threaded binaries.",
         [
             ("Cycle-Accurate Modeling", "Translates synthesizable Verilog directly into high-speed C++ classes."),
             ("Multi-Threaded Slicing", "Distributes logic evaluation across cores via --threads N."),
             ("Trace Generation", "Generates standard VCD and FST traces via --trace-fst."),
             ("Automated Sandbox Hook", "VeriSight Agent 5 leverages Verilator for instant regression testing.")
         ],
         "# Verilator Compilation Command\nverilator --cc --exe --build -j 8 --trace \\\n    -Wall -Wno-fatal dut.v tb.cpp -o sim_dut"),

        (50, "Icarus Verilog (iverilog) and vvp Open-Source Simulation Pipeline",
         "Open-Source EDA & Lightweight Triage",
         "Rapid deterministic simulation execution for lightweight regression and triage.",
         [
             ("Two-Step Pipeline", "Compiles AST via iverilog into intermediate vvp bytecode."),
             ("SystemVerilog Support", "Supports core SystemVerilog features using -g2012 switch."),
             ("Zero-License Overhead", "Enables running thousands of parallel containerized sandboxes."),
             ("VeriSight Default Engine", "Integrated directly in Option 3 Closed-Loop Sim runner.")
         ],
         "# Icarus Verilog Invocation\niverilog -g2012 -o sim.vvp -f filelist.f\nvvp sim.vvp -lxt2"),

        (51, "Cocotb Coroutine-Based Pythonic Hardware Verification Runbook",
         "Modern Verification & Python Testbenches",
         "Co-simulation verification linking Python async coroutines to simulators via VPI.",
         [
             ("Async / Await Syntax", "Models hardware timing concurrently using standard Python async syntax."),
             ("VPI Interface Bridge", "Non-intrusive direct signal inspection and forcing over standard C VPI."),
             ("Rich Python Ecosystem", "Direct integration with NumPy, SciPy, and AI PyTorch models."),
             ("Test Generation", "Facilitates rapid randomized algorithmic verification.")
         ],
         "# Cocotb Python Test Coroutine\n@cocotb.test()\nasync def test_fifo_push_pop(dut):\n    cocotb.start_soon(Clock(dut.clk, 10, units='ns').start())\n    dut.rst_n.value = 0\n    await Timer(20, units='ns')\n    dut.rst_n.value = 1\n    dut.wr_en.value = 1; dut.din.value = 0xA5\n    await RisingEdge(dut.clk)"),

        (52, "SpyGlass Static Lint Rule Deck and Synthesizability Checks",
         "Static Verification & Lint Analysis",
         "Static source code inspection catching syntax ambiguities, latches, and race conditions.",
         [
             ("Structural Rule Enforcement", "Flags unintended combinational latches and incomplete case statements."),
             ("Synthesis Safety", "Guarantees code compiles cleanly in Synopsys Design Compiler."),
             ("Port Width Mismatches", "Detects bit truncation and implicit wire declarations."),
             ("VeriSight Rule 7", "Agent 1 AST analyzer reproduces SpyGlass structural lint checks.")
         ],
         "# SpyGlass Lint Project Script\nread_file -type verilog {dut.v sub.v}\nset_option top dut\ncurrent_goal lint/lint_rtl\nrun_goal"),

        (53, "SpyGlass CDC Asynchronous Clock Domain Crossing Verification",
         "Static Verification & CDC Analysis",
         "Formal mathematical identification of unsynchronized cross-domain signal transfers.",
         [
             ("Clock Tree Identification", "Extracts master clocks, generated clocks, and reset domains."),
             ("Synchronizer Recognition", "Validates 2-FF synchronizers, DMUX, and asynchronous FIFOs."),
             ("Data Re-Convergence Checks", "Detects divergent paths recombining downstream with skew."),
             ("VeriSight CDC Module", "Identifies missing flip-flop synchronizers in AST traversal.")
         ],
         "# SpyGlass CDC Goal Execution\ncurrent_goal cdc/cdc_verify_struct\nrun_goal"),

        (54, "Synopsys Formality Equivalence Checking Verification Runbook",
         "Formal Verification & Equivalence",
         "Proving mathematical equivalence between RTL and post-synthesis gate netlists.",
         [
             ("Reference vs Implementation", "Compares golden RTL against synthesized netlist."),
             ("Logic Cone Inversion", "Decomposes sequential logic into combinational logic cones."),
             ("State Mapping Rules", "Maps scan-chain and retimed registers automatically."),
             ("Safety Integrity", "Guarantees zero logic changes introduced during synthesis ECO.")
         ],
         "# Formality Script Template\nread_verilog -r rtl.v; set_top_r dut\nread_verilog -i netlist.v; set_top_i dut\nmatch\nverify"),

        (55, "Cadence JasperGold Formal Property Verification Setup",
         "Formal Verification & Model Checking",
         "Exhaustive state space exploration verifying assertions across all possible stimulus.",
         [
             ("Bounded Model Checking", "Unrolls transition relations up to depth N to find counter-examples."),
             ("Full Proof Induction", "Mathematical induction proving properties hold for infinite cycles."),
             ("Deadlock & LiveLock Proofs", "Guarantees hardware never enters unreachable trap states."),
             ("Assertion Import", "Ingests SVA properties generated by VeriSight Agent 2 directly.")
         ],
         "# JasperGold Formal Invocation Script\nanalyze -sv dut.v assertions.sva\nelaborate -top dut\nclock clk; reset -expression {!rst_n}\nprove -all"),

        (56, "Fast Waveform Dumper (FSDB) Extraction and Trace Compression",
         "Waveform Engineering & Trace Analysis",
         "High-performance compressed waveform format optimized for multi-gigabyte traces.",
         [
             ("Hierarchical Compression", "Compresses waveform data up to 10x compared to standard ASCII VCD."),
             ("Random-Access Indexing", "Allows fast seek to arbitrary simulation timestamps."),
             ("Verdi Native Integration", "Native format for Synopsys Verdi schematic and waveform debug."),
             ("VeriSight Trace Converter", "Agent 1 converts critical trace slices for automated inspection.")
         ],
         "// Testbench FSDB Dumping Directives\ninitial begin\n    $fsdbDumpfile(\"dump.fsdb\");\n    $fsdbDumpvars(0, top_tb, \"+all\");\nend"),

        (57, "Value Change Dump (VCD) ASCII Parse Algorithms and Signal Slicing",
         "Waveform Engineering & Signal Slicing",
         "Deterministic parsing algorithms extracting signal transitions from standard ASCII VCD.",
         [
             ("Four-State Value Encoding", "Parses 0, 1, X (unknown), and Z (high-impedance) transitions."),
             ("Hierarchical Scope Trees", "Constructs module hierarchy tree from $scope and $upscope directives."),
             ("Timestamp Slicing", "Extracts narrow +/- 20 cycle window around assertion failure timestamp."),
             ("VeriSight VCD Engine", "Integrated in `verisight/rules/rule_vcd.py`.")
         ],
         "# Python VCD Parsing Logic (VeriSight Engine)\ndef parse_vcd_window(vcd_path, fail_time, window_cycles=20):\n    # Extracts signal transitions around fail_time\n    pass"),

        (58, "GCC / Clang Direct Programming Interface (DPI-C) Shared Object Builds",
         "SystemVerilog DPI-C & Co-Simulation",
         "Compiling high-performance C/C++ algorithms directly into SystemVerilog testbenches.",
         [
             ("Zero-Copy Memory Sharing", "Shares pointers and structs directly between C and SystemVerilog."),
             ("Import & Export Functions", "Calls C mathematical algorithms from SV; calls SV tasks from C."),
             ("Open-Source Toolchains", "Compiles cleanly with standard GCC and Clang compilers."),
             ("Reference Scoreboards", "Executes reference compression, crypto, or AI models in native C++.")
         ],
         "// SystemVerilog DPI-C Declaration\nimport \"DPI-C\" function int compute_crc32(input int len, input byte data[]);\nexport \"DPI-C\" task sv_notify_irq;"),

        (59, "pyslang AST Extraction and SystemVerilog Static Analysis",
         "Static Analysis & AST Traversal",
         "Parsing and elaborating SystemVerilog into a real IEEE-1800 AST (via the Slang frontend) to analyse hardware structure programmatically.",
         [
             ("Parse & Elaborate", "pyslang parses and elaborates SystemVerilog into typed symbols with source locations."),
             ("Static X-Origin Scan", "Flags sequential registers written but not assigned in their reset branch."),
             ("Signal Read/Write Sets", "Derives per-block written/read signals from assignment expressions in the AST."),
             ("VeriSight Rule 2 Checking", "Drives the X-Tracer deterministic candidate-origin engine (static layer).")
         ],
         "# pyslang AST parse + elaborate\nfrom pyslang import driver\nd = driver.Driver(); d.addStandardArgs()\nd.parseCommandLine('slang dut.sv'); d.processOptions(); d.parseAllSources()\ncomp = d.createCompilation()\nfor inst in comp.getRoot().topInstances:\n    for sym in inst.body: ...  # walk ports/nets/procedural blocks"),

        (60, "Docker Containerization for Isolated Multi-Tool EDA Execution",
         "Verification Infrastructure & DevOps",
         "Packaging EDA tools, compilers, and regression runners into reproducible containers.",
         [
             ("Hermetic Environment", "Eliminates 'works on my machine' library and glibc incompatibilities."),
             ("Multi-Vendor Licensing", "Safely bridges license server ports across container networks."),
             ("Cloud Regression Scaling", "Enables scaling to thousands of parallel AWS/GCP spot instances."),
             ("VeriSight Headless CLI", "Runs deterministically in CI/CD container environments.")
         ],
         "# VeriSight Dockerfile Snippet\nFROM ubuntu:24.04\nRUN apt-get update && apt-get install -y iverilog verilator python3 python3-pip\nCOPY . /workspace/verisight\nWORKDIR /workspace/verisight\nENTRYPOINT [\"python3\", \"start.py\"]"),

        # Domain 5: Machine Learning, NLP & Verification AI (A.61 - A.75)
        (61, "Tree-of-Thought (ToT) Self-Consistent Reasoning in Hardware RCA",
         "Verification AI & Reasoning Architectures",
         "Multi-branch exploration isolating primary defect origins from secondary symptoms.",
         [
             ("Branching Hypotheses", "Generates independent hypotheses (TB defect, RTL bug, Spec conflict)."),
             ("Deterministic Scoring", "Evaluates hypotheses against VCD traces, log errors, and AST connectivity."),
             ("Consensus Pruning", "Discards low-confidence branches that contradict physical waveforms."),
             ("VeriSight Agent 1 Engine", "Achieves 95%+ root-cause classification accuracy.")
         ],
         "# ToT Verification Decision Logic\nscores = evaluate_branches(hypotheses, waveform_evidence, ast_rules)\nbest_root_cause = max(scores, key=lambda x: x.confidence)"),

        (62, "Vector Embedding Retrieval Optimization for HDL Codebases",
         "Verification AI & Semantic Search",
         "Chunking strategies and semantic embedding retrieval tailored for hardware code.",
         [
             ("Module-Aware Chunking", "Splits code along module, task, function, and always block boundaries."),
             ("Cross-Reference Indexing", "Embeds signal names alongside architectural specification paragraphs."),
             ("ChromaDB Integration", "Maintains 11 persistent vector collections in VeriSight."),
             ("Sub-Second Retrieval", "Returns relevant RTL context in under 50ms.")
         ],
         "# Semantic Chunking Strategy\ndef chunk_verilog(source_code):\n    # Splits by module / always block boundaries to preserve semantic context\n    pass"),

        (63, "ChromaDB HNSW Index Tuning for Verilog Syntax Search",
         "Verification AI & Vector Databases",
         "Optimizing Hierarchical Navigable Small World graphs for hardware semantic queries.",
         [
             ("Distance Metric Selection", "Cosine similarity for conceptual search; L2 for exact signal matching."),
             ("M and efConstruction Tuning", "Balances index build time against query recall accuracy."),
             ("Offline Vector Persistence", "Permits instant air-gapped sovereign execution without cloud latency."),
             ("Multi-Modal Association", "Links PDF spec paragraphs to corresponding Verilog RTL lines.")
         ],
         "# ChromaDB Collection Configuration\ncollection = client.create_collection(\n    name='verisight_rtl',\n    metadata={'hnsw:space': 'cosine', 'hnsw:construction_ef': 128}\n)"),

        (64, "Multi-Agent Consensus Protocol in Root Cause Arbitration",
         "Verification AI & Agent Collaboration",
         "Orchestrating specialized agents to resolve ambiguous simulation failures.",
         [
             ("Agent 1 (Triage)", "Identifies failing assertions, timestamps, and error messages."),
             ("Agent 2 (Spec Engine)", "Retrieves golden architectural requirements and expected behavior."),
             ("Agent 3 (RTL Analyzer)", "Traces backward logic fan-in and detects physical logic flaws."),
             ("Consensus Arbiter", "Weights multi-agent votes into unified triage diagnostic.")
         ],
         "# Multi-Agent Voting Matrix\nconsensus = (w_triage * v_1) + (w_spec * v_2) + (w_rtl * v_3)"),

        (65, "AST Unified Git Patch Generation and Semantic Code Validation",
         "Verification AI & Automated Repair",
         "Synthesizing mathematically valid patches and validating syntax in sandboxes.",
         [
             ("Unified Diff Synthesis", "Generates minimal git diffs altering only defective logic lines."),
             ("AST Syntax Pre-Check", "Parses modified code with pyslang before committing to disk, distinguishing genuine syntax errors from missing-dependency diagnostics."),
             ("Sandbox Compilation", "Runs compiler (iverilog/verilator) in temporary directory."),
             ("Regression Safety", "Verifies failing test passes without breaking existing regression suite.")
         ],
         "// Sample Unified Git Patch Output (VeriSight Fix Engine)\n--- a/rtl/fifo.v\n+++ b/rtl/fifo.v\n@@ -42,3 +42,3 @@\n-assign full = (count == DEPTH - 1);\n+assign full = (count == DEPTH);"),

        (66, "Genetic Algorithm Mutation for Constrained Random Stimulus",
         "Verification AI & Heuristic Search",
         "Evolving testbench randomization seeds to hit elusive functional coverage holes.",
         [
             ("Chromosome Representation", "Encodes transaction constraints and random seed integers."),
             ("Fitness Function", "Evaluates new coverage bins hit per simulation CPU second."),
             ("Crossover & Mutation", "Exchanges constraint weights between high-performing seeds."),
             ("Coverage Saturation", "Accelerates coverage closure by 5x compared to pure random.")
         ],
         "# Genetic Seed Mutation Function\nnew_seed = mutate_constraints(parent_seed, mutation_rate=0.05)"),

        (67, "Bayesian Coverage Directed Test Generation (CDG) Mechanics",
         "Verification AI & Bayesian Inference",
         "Predictive modeling directing constrained random stimulus toward unhit coverage bins.",
         [
             ("Prior Probability Distribution", "Initial uniform distribution over transaction parameters."),
             ("Posterior Update", "Updates probability distribution after each simulation trace."),
             ("Directed Guidance", "Focuses stimulus on boundary condition parameter regions."),
             ("VeriSight Plan Ingestion", "Connects directly to Live Coverage Cockpit.")
         ],
         "# Bayesian Parameter Distribution Update\np_posterior = (p_likelihood * p_prior) / p_evidence"),

        (68, "Reinforcement Learning for Finite State Machine Deep Exploration",
         "Verification AI & Reinforcement Learning",
         "Training Q-learning agents to navigate complex multi-tier FSM transition graphs.",
         [
             ("State Space Definition", "Vector of sequential register states and buffer fill levels."),
             ("Action Space", "Valid input transaction sequences and protocol handshake delays."),
             ("Reward Function", "Positive reward for discovering previously unreached FSM states."),
             ("Corner-Case Discovery", "Discovers hidden livelocks and unreachable trap states.")
         ],
         "# Q-Learning State Update\nQ[s, a] = Q[s, a] + alpha * (reward + gamma * max(Q[s_next]) - Q[s, a])"),

        (69, "Natural Language Specification Extraction via Instruction Tuning",
         "Verification AI & NLP in Hardware",
         "Extracting structured verification plans from unformatted PDF and Word datasheets.",
         [
             ("Structural Extraction", "Identifies register tables, pinouts, and timing requirements."),
             ("Formal Contract Parsing", "Translates English descriptions into formal temporal assertions."),
             ("Cross-Reference Linking", "Builds bi-directional links between spec paragraphs and tests."),
             ("VeriSight Agent 2 Engine", "Powers the VeriSight Plan automated synthesis workflow.")
         ],
         "# Instruction-Tuned Spec Extraction Prompt Structure\nSYSTEM_PROMPT = 'Extract all register fields, protocols, and verification features...'"),

        (70, "Semantic Anomaly Detection on Continuous Simulator Log Streams",
         "Verification AI & Log Analytics",
         "Real-time streaming analysis detecting early warning signs in multi-gigabyte logs.",
         [
             ("Stream Tokenization", "Tokenizes simulator log messages at gigabyte-per-minute speeds."),
             ("Entropy Tracking", "Detects repeating warning patterns signaling impending driver hang."),
             ("Early Termination", "Kills runaway simulations early to conserve compute farm resources."),
             ("VeriSight Rule 8", "Integrated into automated failure triage engine.")
         ],
         "# Log Stream Anomaly Scoring\nis_anomaly = entropy_tracker.update(log_line) > THRESHOLD"),

        (71, "Automatic X-Propagation Dynamic Slicing and Flop Isolation",
         "Verification AI & Simulation Debugging",
         "Automated isolation of unknown logic states causing silent data corruption.",
         [
             ("Dynamic Back-Tracing", "Traces X values backwards in time to origin flip-flop."),
             ("Optimistic X-State Masking", "Distinguishes between RTL simulation bugs and real hardware bugs."),
             ("Reset Tree Analysis", "Identifies uninitialized registers missing from reset block."),
             ("VeriSight X-Tracer", "Automated in `verisight/rules/rule_x_tracer.py`.")
         ],
         "# Dynamic X-State Backward Slice\nfailing_flops = trace_x_propagation(vcd_file, fail_timestamp, netlist)"),

        (72, "Regression Triage Clustering via Levenshtein Trace Distances",
         "Verification AI & Regression Triage",
         "Clustering thousands of nightly regression failures into distinct root-cause buckets.",
         [
             ("Failure Signature Vectorization", "Encodes error messages, stack traces, and failing signals."),
             ("Levenshtein Distance Metric", "Calculates string and call-stack edit distances."),
             ("DBSCAN Clustering", "Groups 5,000+ failures into 3-5 unique actionable defect clusters."),
             ("Engineering Efficiency", "Prevents 50 engineers from debugging the identical root-cause bug.")
         ],
         "# DBSCAN Failure Signature Clustering\nclusters = DBSCAN(eps=0.3, min_samples=2).fit(failure_vectors)"),

        (73, "Fast Waveform Change Anomaly Detection using 1D CNNs",
         "Verification AI & Signal Processing",
         "Detecting subtle clock jitter, runt pulses, and bus contention in digital traces.",
         [
             ("1D Convolutional Filters", "Scans digital transition sequences for anomalous pulse widths."),
             ("Bus Contention Detection", "Identifies overlapping active drivers on tri-state buses."),
             ("Zero-Annotation Training", "Trained on golden simulation traces using autoencoder architecture."),
             ("VeriSight Studio Display", "Highlights anomalous regions in Live Web Cockpit waveform viewer.")
         ],
         "# 1D CNN Autoencoder Waveform Anomaly Detector\nreconstruction_error = model.predict(waveform_tensor) - waveform_tensor"),

        (74, "Automated SVA Property Synthesis from Waveform Trace Slices",
         "Verification AI & Property Mining",
         "Mining invariant temporal logic properties directly from golden simulation waveforms.",
         [
             ("Dynamic Invariant Mining", "Discovers consistent temporal relationships between bus signals."),
             ("Candidate Filtering", "Prunes vacuous and trivial properties via statistical significance tests."),
             ("SVA Code Generation", "Outputs synthesizable SystemVerilog assert property code blocks."),
             ("Testbench Enhancement", "Enhances testbench coverage without manual specification writing.")
         ],
         "# Invariant Mining Rule\nif always_holds(signal_A, implies, next_cycle(signal_B)):\n    generate_sva_property(signal_A, signal_B)"),

        (75, "End-to-End Autonomous Hardware Verification Co-Pilot Roadmap",
         "Verification AI & Future Architectures",
         "The architectural vision and future evolution of fully autonomous silicon verification.",
         [
             ("Self-Healing Testbenches", "Testbenches that automatically adapt stimulus to close remaining coverage."),
             ("Continuous Formal Verification", "Real-time formal proof convergence alongside RTL synthesis."),
             ("Silicon-to-Software Feedback", "Post-silicon telemetry informing pre-silicon verification models."),
             ("VeriSight Industry Standard", "Setting the benchmark for autonomous hardware engineering.")
         ],
         "// VeriSight: The Future of Autonomous Silicon Verification\n// Authored by Kittu Patel (@KITTUV03) • Release v2.4 • 2026\n// End of Master Technical Journal")
    ]

    for annex_num, annex_title, annex_domain, annex_math, annex_bullets, annex_code in annex_specs:
        story.append(PageBreak())
        story.append(Paragraph(f"Technical Annex A.{annex_num}: {annex_title}", h2_style))
        story.append(HRFlowable(width="100%", thickness=0.75, color=c_secondary, spaceBefore=3, spaceAfter=8))
        story.append(Paragraph(f"<b>Verification Domain:</b> {annex_domain} &nbsp;|&nbsp; <b>Formal Context:</b> {annex_math}", body_style))
        story.append(Spacer(1, 4))
        for b_title, b_desc in annex_bullets:
            story.append(Paragraph(f"• <b>{b_title}:</b> {b_desc}", bullet_style))
        story.append(Spacer(1, 6))
        story.append(code_box(annex_code))

    story.append(PageBreak())
    concl_p = Paragraph(
        "<b>VERISIGHT™ SILICON VERIFICATION COPILOT — MASTER TECHNICAL JOURNAL</b><br/>"
        "Engineered & Authored by <b>Kittu Patel</b> (@KITTUV03)<br/>"
        "All Rights Reserved • Publication Release v2.4 • October 20, 2026",
        ParagraphStyle('Concl', parent=body_style, fontSize=8, leading=11, alignment=TA_CENTER, textColor=c_muted)
    )
    story.append(concl_p)

    print("Building master multi-page PDF document...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"SUCCESS: {PDF_FILENAME} successfully built!")

if __name__ == '__main__':
    build_pdf()
