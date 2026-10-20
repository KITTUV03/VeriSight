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
            return  # Suppress on cover page

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(42, 755, "VERISIGHT™ SILICON VERIFICATION COPILOT")
        self.setFont("Helvetica", 8)
        self.drawRightString(570, 755, "OPERATOR'S JOURNAL & ARCHITECTURE FIELD GUIDE")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(42, 747, 570, 747)

        # Footer
        self.line(42, 45, 570, 45)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(42, 32, "Author: Patel Kittu (KITTUV03) • Mirafra Technologies • Confidential & Proprietary")
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

    # Custom styles
    c_primary = colors.HexColor("#0f172a")     # Slate 900
    c_secondary = colors.HexColor("#0284c7")   # Sky 600
    c_accent = colors.HexColor("#0369a1")      # Sky 700
    c_text = colors.HexColor("#1e293b")        # Slate 800
    c_muted = colors.HexColor("#64748b")       # Slate 500
    c_code_bg = colors.HexColor("#f1f5f9")     # Slate 100

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=34,
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
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_accent,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'Heading3_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=c_primary,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=c_text,
        alignment=TA_LEFT,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.2,
        leading=11,
        textColor=colors.HexColor("#0f172a")
    )

    caption_style = ParagraphStyle(
        'Caption_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.2,
        leading=11,
        textColor=c_muted,
        alignment=TA_CENTER,
        spaceBefore=3,
        spaceAfter=8
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
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    def code_box(code_text):
        escaped = code_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')
        p = Paragraph(escaped, code_style)
        t = Table([[p]], colWidths=[528])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
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

    # Top Accent Badge
    badge_p = Paragraph(
        "<font color='#0284c7'><b>OFFICIAL VERISIGHT OPERATIONAL JOURNAL & FIELD ENGINEERING MANUAL</b></font>",
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
    story.append(Paragraph("Dual-Engine Architecture: Diagnostic Debug RCA & Verification Plan Synthesizer", ParagraphStyle('Sub2', parent=subtitle_style, fontSize=10.5, textColor=c_muted)))
    story.append(Spacer(1, 20))

    story.append(HRFlowable(width="80%", thickness=2.5, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=25))

    # Metadata & Author Box
    author_table_data = [
        [
            Paragraph("<b>Document Title:</b>", body_style),
            Paragraph("VeriSight Comprehensive Operator's Journal & Technical Reference", body_style)
        ],
        [
            Paragraph("<b>Lead Author & Architect:</b>", body_style),
            Paragraph("<b>Patel Kittu</b> (GitHub: <i>@KITTUV03</i>)", body_style)
        ],
        [
            Paragraph("<b>Engineering Affiliation:</b>", body_style),
            Paragraph("Mirafra Technologies • Silicon Systems & AI Verification Group", body_style)
        ],
        [
            Paragraph("<b>Edition & Version:</b>", body_style),
            Paragraph("Production Release v2.4 (Enterprise Dual-Engine Suite)", body_style)
        ],
        [
            Paragraph("<b>Release Date:</b>", body_style),
            Paragraph("October 20, 2026", body_style)
        ],
        [
            Paragraph("<b>Core Capabilities:</b>", body_style),
            Paragraph("• Autonomous Simulation Failure Debugging (AST, CDC, Lint, X-Tracer)<br/>• Verification Plan, Functional Coverage & SVA Synthesis<br/>• ISO 26262 / DO-254 Bi-Directional Traceability Matrix<br/>• Interactive Guided Wizard & Headless CI/CD Regression Modes", body_style)
        ],
        [
            Paragraph("<b>Supported Standards:</b>", body_style),
            Paragraph("IEEE 1800 SystemVerilog, UVM 1.2, SVA (Assertions), VCD/FSDB, PDF/Markdown Specs", body_style)
        ]
    ]
    author_t = Table(author_table_data, colWidths=[150, 378])
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

    story.append(Spacer(1, 40))

    confidential_p = Paragraph(
        "<b>CONFIDENTIAL & PROPRIETARY:</b> This technical operational journal is prepared for semiconductor verification engineers, system architects, and design verification leads. No part of this document or software architecture may be reproduced without prior authorization from Patel Kittu.",
        ParagraphStyle('Conf', parent=body_style, fontSize=7.8, leading=11, textColor=c_muted, alignment=TA_CENTER)
    )
    story.append(confidential_p)
    story.append(PageBreak())

    # =========================================================================
    # DOCUMENT CONTROL & TABLE OF CONTENTS
    # =========================================================================
    story.append(Paragraph("Document Overview & Table of Contents", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    toc_data = [
        [Paragraph("<b>Chapter / Section</b>", body_style), Paragraph("<b>Core Subject Matter & Operational Focus</b>", body_style), Paragraph("<b>Key Artifacts / Screenshots</b>", body_style)],
        [Paragraph("<b>Chapter 1</b>", body_style), Paragraph("Introduction to VeriSight & The Autonomous Verification Paradigm", body_style), Paragraph("System Philosophy, Architecture", body_style)],
        [Paragraph("<b>Chapter 2</b>", body_style), Paragraph("Quick Start, Installation & Interactive Setup Wizard", body_style), Paragraph("Screenshot 01 (Welcome Menu)", body_style)],
        [Paragraph("<b>Chapter 3</b>", body_style), Paragraph("Step 2: LLM Configuration & Deterministic Fallback Mode", body_style), Paragraph("Screenshot 02 (LLM Configuration)", body_style)],
        [Paragraph("<b>Chapter 4</b>", body_style), Paragraph("VeriSight Agent 1: Root-Cause Failure Debugging (RCA) Engine", body_style), Paragraph("Screenshots 03 & 04 (Debug Inputs & Results)", body_style)],
        [Paragraph("<b>Chapter 5</b>", body_style), Paragraph("VeriSight Agent 2: Verification Plan & Coverage/SVA Architect", body_style), Paragraph("Screenshots 05 & 06 (Plan Inputs & Results)", body_style)],
        [Paragraph("<b>Chapter 6</b>", body_style), Paragraph("Option 3: Pre-Packaged Instant Demonstration Suite", body_style), Paragraph("Screenshot 07 (Quick Demos Menu)", body_style)],
        [Paragraph("<b>Chapter 7</b>", body_style), Paragraph("Option 4: Clean Session Termination & Advanced Headless CLI", body_style), Paragraph("Screenshot 08 (Exit & CLI Examples)", body_style)],
        [Paragraph("<b>Chapter 8</b>", body_style), Paragraph("Verification Engineering Best Practices & Sign-Off Checklist", body_style), Paragraph("ISO 26262 / DO-254 Compliance", body_style)],
        [Paragraph("<b>Chapter 9</b>", body_style), Paragraph("Schema Reference, Configuration Variables & Troubleshooting", body_style), Paragraph("Error Codes & Remediation", body_style)],
        [Paragraph("<b>Appendix</b>", body_style), Paragraph("Operator Quick-Reference Cheatsheet & Acronym Glossary", body_style), Paragraph("CLI Command Dictionary", body_style)],
    ]
    toc_table = Table(toc_data, colWidths=[80, 280, 168])
    toc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(toc_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Executive Summary from Author: Patel Kittu", h2_style))
    story.append(Paragraph(
        "Modern Very Large Scale Integration (VLSI) and System-on-Chip (SoC) verification cycles frequently consume between <b>60% and 75% of total ASIC project development time</b>. Functional verification teams spend thousands of engineering hours navigating gigabyte-scale simulation logs, tracing elusive multi-clock asynchronous Clock Domain Crossing (CDC) faults, resolving Unknown State (X) propagation bugs, and authoring exhaustive functional coverage models and SystemVerilog Assertions (SVA) from hundreds of pages of textual design specifications.",
        body_style
    ))
    story.append(Paragraph(
        "<b>VeriSight</b> was engineered by <b>Patel Kittu</b> to revolutionize silicon verification through a coordinated multi-agent artificial intelligence framework. Rather than acting as a simple generic chat assistant, VeriSight is deeply integrated into EDA toolchains. It combines formal static analysis (AST parsers, syntax checkers, linting, connectivity graphs, netlist X-tracing) with cutting-edge Large Language Models (LLMs) including Google Gemini 2.0 Flash and Anthropic Claude 3.5 Sonnet, paired with a vectorized ChromaDB historical sign-off knowledge base.",
        body_style
    ))
    story.append(Paragraph(
        "This journal serves as the definitive reference manual for operating both primary engines of the VeriSight platform: <b>Agent 1 (VeriSight Debug)</b> for automated root-cause localization and patch synthesis, and <b>Agent 2 (VeriSight Plan)</b> for automated extraction of verification features, test scenarios, functional coverage groups, and SVA suites.",
        body_style
    ))

    story.append(callout_box(
        "VeriSight supports interactive guided operation via terminal UI (TUI) as well as non-blocking headless execution designed for continuous integration (CI/CD) regression farms.",
        "info"
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 1: ARCHITECTURE
    # =========================================================================
    story.append(Paragraph("Chapter 1: The VeriSight Architecture & Philosophy", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "VeriSight is structured around a decoupled, modular dual-engine architecture. Each engine operates autonomously or in tandem depending on the verification phase: early-stage architecture planning versus late-stage regression debugging.",
        body_style
    ))

    arch_table_data = [
        [Paragraph("<b>Subsystem Engine</b>", body_style), Paragraph("<b>Target Verification Phase</b>", body_style), Paragraph("<b>Core Automated Responsibility</b>", body_style)],
        [
            Paragraph("<b>Agent 1: VeriSight Debug</b><br/><i>(Autonomous RCA Engine)</i>", body_style),
            Paragraph("Simulation Regressions, Silicon Bring-up, Testbench Failures", body_style),
            Paragraph("• Parses UVM/VMM simulation logs & fatal assertions.<br/>• Extracts RTL AST, port connectivity, and netlists.<br/>• Executes deterministic X-Tracer gate-level backward propagation.<br/>• Runs rule-based Lint, CDC, and Protocol analyzers.<br/>• Synthesizes root-cause classification & generates verified git diff patches.", body_style)
        ],
        [
            Paragraph("<b>Agent 2: VeriSight Plan</b><br/><i>(Autonomous Plan Architect)</i>", body_style),
            Paragraph("Pre-Silicon Spec Ingestion, Testbench Planning, Coverage Closure", body_style),
            Paragraph("• Ingests PDF, Markdown, and Text technical specifications.<br/>• Performs hierarchical feature decomposition & requirement tagging.<br/>• Formulates directed & constrained-random test scenarios.<br/>• Generates production SystemVerilog covergroups & cross bins.<br/>• Synthesizes SystemVerilog Assertions (SVA) sequences & properties.<br/>• Exports ISO 26262 / DO-254 Bi-Directional Traceability Matrices.", body_style)
        ],
        [
            Paragraph("<b>ChromaDB Vector Store</b><br/><i>(RAG Knowledge Base)</i>", body_style),
            Paragraph("Continuous Cross-Project Learning & Sign-Off Memory", body_style),
            Paragraph("• Indexes historical post-silicon bugs, errata, and past verification plans.<br/>• Provides semantic retrieval of known silicon failure modes.<br/>• Prevents re-occurrence of legacy silicon defects.", body_style)
        ],
        [
            Paragraph("<b>Interactive Wizard</b><br/><i>(Operator Interface)</i>", body_style),
            Paragraph("Developer Terminal & EDA Workstation", body_style),
            Paragraph("• Unified single-command launcher (<code>./start.sh</code>).<br/>• Auto-detects and validates project inputs with path fuzzy-matching.<br/>• Auto-launches interactive HTML verification dashboards in local browsers.", body_style)
        ]
    ]
    arch_t = Table(arch_table_data, colWidths=[120, 140, 268])
    arch_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(arch_t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Verification Data Flow Pipeline", h2_style))
    story.append(Paragraph(
        "The VeriSight pipeline follows a strict five-stage deterministic sequence: <b>Ingestion &rarr; Static Analysis & AST Extraction &rarr; Semantic Knowledge Augmentation (RAG) &rarr; Multi-Agent LLM Synthesis &rarr; Artifact & Patch Generation</b>. By coupling deterministic parsers with LLM reasoning, VeriSight eliminates the risk of hallucination while preserving high cognitive flexibility.",
        body_style
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 2: QUICK START & WIZARD
    # =========================================================================
    story.append(Paragraph("Chapter 2: Installation, Environment & Wizard Initialization", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "VeriSight has been designed for frictionless deployment in standard Linux EDA workstation environments (CentOS, RHEL, Ubuntu) and Windows Subsystem for Linux (WSL2).",
        body_style
    ))

    story.append(Paragraph("Prerequisites & Environment Setup", h2_style))
    story.append(Paragraph(
        "Ensure Python 3.10+ is available on your machine. Install VeriSight in editable mode within your project virtual environment:",
        body_style
    ))
    story.append(code_box(
        "# Clone the repository\n"
        "git clone git@github.com:KITTUV03/VeriSight.git\n"
        "cd VeriSight\n\n"
        "# Activate your virtual environment and install dependencies\n"
        "source .venv/bin/activate\n"
        "pip install -e '.[dev]'\n"
        "pip install pypdf reportlab"
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Launching the Interactive Guided Setup Wizard", h2_style))
    story.append(Paragraph(
        "To provide immediate usability without requiring engineers to remember complex CLI syntax, author <b>Patel Kittu</b> created the VeriSight Guided Wizard. The wizard can be launched using any of the following intuitive commands:",
        body_style
    ))
    story.append(code_box(
        "./start.sh          # Native executable bash launcher\n"
        "./start             # Symlinked shortcut\n"
        "python start.py     # Python direct bootstrap\n"
        "python main.py start # Main package entry point with 'start' verb\n"
        "python main.py -i   # Interactive flag"
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("The VeriSight Main Welcome Screen", h2_style))
    story.append(Paragraph(
        "When launched, the operator is greeted by the VeriSight welcome banner and the <b>Step 1: Choose Autonomous Workflow</b> selection menu. The terminal screen presents four clearly demarcated operational pathways, as depicted below:",
        body_style
    ))
    story.append(Spacer(1, 4))

    # SCREENSHOT 1
    story.append(screenshot_card(
        "docs/screenshots/screenshot_01_welcome_menu.png",
        "Figure 2.1: VeriSight Interactive Guided Setup Wizard — Main Welcome Banner & Step 1 Workflow Selection Menu",
        width=515,
        height=200
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Detailed Breakdown of the 4 Workflow Choices:", h3_style))
    story.append(Paragraph("• <b>[1] VeriSight Debug:</b> Initiates the autonomous Root-Cause Analysis (RCA) pipeline to diagnose simulation regressions, UVM testbench errors, and RTL bugs.", bullet_style))
    story.append(Paragraph("• <b>[2] VeriSight Plan:</b> Activates the Verification & Architecture Plan generator to ingest specification documents and synthesize test cases, functional coverage models, and SVA suites.", bullet_style))
    story.append(Paragraph("• <b>[3] Quick Demos:</b> Provides 1-click pre-packaged demonstrations on standard ALU and FIFO designs without requiring manual input typing.", bullet_style))
    story.append(Paragraph("• <b>[4] Exit:</b> Gracefully terminates the wizard session and displays advanced CLI examples for automation scripts.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 3: LLM CONFIGURATION
    # =========================================================================
    story.append(Paragraph("Chapter 3: LLM Configuration & Deterministic Fallback Mode", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "VeriSight features an intelligent LLM configuration layer that automatically detects active API credentials from the host environment, offers seamless custom key configuration, and supports a 100% offline deterministic execution mode for secure air-gapped defense and automotive semiconductor environments.",
        body_style
    ))

    story.append(Paragraph("Step 2: LLM Configuration Screen", h2_style))
    story.append(Paragraph(
        "Immediately after selecting an operational workflow in Step 1, VeriSight transitions to <b>Step 2: LLM Configuration</b>. The system scans the environment variables <code>GEMINI_API_KEY</code> and <code>ANTHROPIC_API_KEY</code> and displays an interactive status table:",
        body_style
    ))
    story.append(Spacer(1, 4))

    # SCREENSHOT 2
    story.append(screenshot_card(
        "docs/screenshots/screenshot_02_llm_config.png",
        "Figure 3.1: VeriSight LLM Configuration Screen — Multi-Provider Detection & Selection Table",
        width=515,
        height=234
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Operational Modes Supported by the Engine:", h2_style))
    
    llm_modes_data = [
        [Paragraph("<b>Configuration Option</b>", body_style), Paragraph("<b>Target Engine / Model</b>", body_style), Paragraph("<b>Characteristics & Use-Case</b>", body_style)],
        [
            Paragraph("<b>1. Google Gemini (Detected)</b>", body_style),
            Paragraph("<code>gemini-2.0-flash</code><br/><i>(Recommended Default)</i>", body_style),
            Paragraph("Ultra-fast latency, 1-million token context window, exceptional structured JSON schema compliance. Ideal for massive simulation logs and multi-page specifications.", body_style)
        ],
        [
            Paragraph("<b>2. Anthropic Claude (Detected)</b>", body_style),
            Paragraph("<code>claude-sonnet-5</code> / <code>3.5-sonnet</code>", body_style),
            Paragraph("State-of-the-art HDL code reasoning, advanced temporal logic synthesis for complex SVA assertions, and high-fidelity Verilog patch generation.", body_style)
        ],
        [
            Paragraph("<b>3 & 4. Custom Key Entry</b>", body_style),
            Paragraph("User-supplied API Key", body_style),
            Paragraph("Prompts the operator securely with masked input. VeriSight prompts whether to persist the entered key to the local <code>.env</code> file for zero-friction future sessions.", body_style)
        ],
        [
            Paragraph("<b>5. Offline Deterministic Mode</b>", body_style),
            Paragraph("No Cloud LLM<br/><i>(Deterministic Heuristics)</i>", body_style),
            Paragraph("Operates without external internet connectivity. Utilizes AST pattern matching, rule-based CDC analyzers, lint checkers, and netlist X-Tracers to produce verified diagnostics.", body_style)
        ]
    ]
    llm_table = Table(llm_modes_data, colWidths=[140, 130, 258])
    llm_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(llm_table)
    story.append(Spacer(1, 10))

    story.append(callout_box(
        "In offline deterministic mode, VeriSight disables cloud LLM API calls and relies strictly on deterministic Python verification analyzers. This guarantees 100% data residency within confidential foundry and defense firewalls.",
        "tip"
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 4: AGENT 1 (DEBUG ENGINE)
    # =========================================================================
    story.append(Paragraph("Chapter 4: VeriSight Agent 1 — Root-Cause Analysis & Fix Engine", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "<b>VeriSight Agent 1 (VeriSight Debug)</b> is an autonomous multi-modal root-cause analysis (RCA) pipeline. When modern chip simulations fail, debuggers are faced with millions of log lines, convoluted UVM transaction traces, and subtle sequential logic bugs. Agent 1 automates this entire diagnostic lifecycle.",
        body_style
    ))

    story.append(Paragraph("Step-by-Step Operator Guide: Providing Debug Inputs", h2_style))
    story.append(Paragraph(
        "When Agent 1 is selected, the wizard guides the engineer through input specification. VeriSight incorporates intelligent path normalization (converting Windows drive letters like <code>C:\\</code> into WSL paths like <code>/mnt/c/</code>), extension auto-completion (automatically detecting <code>.log</code>, <code>.sv</code>, <code>.md</code>), and fuzzy directory searching:",
        body_style
    ))
    story.append(Spacer(1, 4))

    # SCREENSHOT 3
    story.append(screenshot_card(
        "docs/screenshots/screenshot_03_agent1_debug_inputs.png",
        "Figure 4.1: Agent 1 Input Prompting — Simulation Log, RTL, Testbench, and Specification Ingestion",
        width=515,
        height=188
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Explanation of Agent 1 Required & Optional Inputs:", h3_style))
    story.append(Paragraph("• <b>Simulation Log (.log) [REQUIRED]:</b> The raw simulation log from Synopsys VCS, Cadence Xcelium, Siemens Questa, or Icarus Verilog containing UVM error banners, timestamps, and assertion failures.", bullet_style))
    story.append(Paragraph("• <b>RTL Source Directory (.sv, .v) [OPTIONAL]:</b> Design Under Test (DUT) hardware description files. VeriSight automatically discovers all RTL modules in the hierarchy.", bullet_style))
    story.append(Paragraph("• <b>UVM Testbench (.sv) [OPTIONAL]:</b> Testbench components (drivers, monitors, scoreboards, sequencers) for identifying testbench-level race conditions or scoreboard synchronization errors.", bullet_style))
    story.append(Paragraph("• <b>Design Specification (.md, .pdf) [OPTIONAL]:</b> Golden architectural specification to cross-verify whether the RTL implementation adheres to stated functional requirements.", bullet_style))
    story.append(Paragraph("• <b>Output Directory:</b> Destination for all diagnostic reports and generated code patches (defaults to <code>output/custom_debug/</code>).", bullet_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("The 5-Phase Diagnostic Execution Pipeline", h2_style))
    story.append(Paragraph(
        "Once inputs are confirmed, Agent 1 executes a synchronized 5-phase diagnostic sweep:",
        body_style
    ))
    story.append(Paragraph("1. <b>Log & AST Parsing:</b> Tokenizes simulation logs, extracts UVM phases, simulation timestamps, and locates exact assertion failure points.", bullet_style))
    story.append(Paragraph("2. <b>Static Analyzer Suite:</b> Concurrently runs five specialized analyzers: Clock Domain Crossing (CDC), Linting (combinational loops, latches), Protocol Checking, Structural AST checks, and Gate-level X-Propagation Tracing.", bullet_style))
    story.append(Paragraph("3. <b>ChromaDB RAG Retrieval:</b> Queries the localized vector database for similar historical silicon bugs and validated resolution patterns.", bullet_style))
    story.append(Paragraph("4. <b>Multi-Agent LLM Synthesis:</b> Aggregates the static analyzer findings and queries the configured LLM with strict verification schemas to classify the bug and identify the exact module and line number.", bullet_style))
    story.append(Paragraph("5. <b>Fix Engine & Patch Generation:</b> Synthesizes a minimal, non-regressive SystemVerilog fix and outputs a standard Git patch file.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 4
    story.append(screenshot_card(
        "docs/screenshots/screenshot_04_agent1_debug_results.png",
        "Figure 4.2: Agent 1 Execution Output & Results — Root Cause Classification, Confidence Score & Generated Reports",
        width=515,
        height=315
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Output Artifacts Generated by Agent 1:", h2_style))
    
    agent1_artifacts_data = [
        [Paragraph("<b>Generated Artifact</b>", body_style), Paragraph("<b>Format</b>", body_style), Paragraph("<b>Engineering Purpose & Value</b>", body_style)],
        [
            Paragraph("<b>report.html</b>", body_style),
            Paragraph("Interactive HTML", body_style),
            Paragraph("Visual browser dashboard featuring collapsible error traces, confidence gauges, code diff viewers, and analyzer summaries. Auto-opens in the default web browser upon run completion.", body_style)
        ],
        [
            Paragraph("<b>report.md</b>", body_style),
            Paragraph("Markdown", body_style),
            Paragraph("Comprehensive engineering documentation containing detailed diagnostic narrative, simulation timeline, and recommended post-fix verification tests. Ideal for Git commit logs.", body_style)
        ],
        [
            Paragraph("<b>error.json</b>", body_style),
            Paragraph("JSON Schema", body_style),
            Paragraph("Machine-readable error descriptor containing classification (<code>RTL_BUG</code>, <code>TB_BUG</code>, <code>ENV_BUG</code>), confidence percentage, module name, and line numbers for automated CI/CD bug trackers (Jira, Bugzilla).", body_style)
        ],
        [
            Paragraph("<b>summary.txt</b>", body_style),
            Paragraph("Plain Text", body_style),
            Paragraph("Concise executive briefing formatted for morning standups, verification status reports, and email notifications.", body_style)
        ],
        [
            Paragraph("<b>fix/proposed.patch</b>", body_style),
            Paragraph("Git Diff Patch", body_style),
            Paragraph("Production-ready unified patch file. Can be directly previewed or applied to the repository via <code>git apply output/fifo_debug/fix/proposed.patch</code>.", body_style)
        ]
    ]
    agent1_art_table = Table(agent1_artifacts_data, colWidths=[120, 110, 298])
    agent1_art_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(agent1_art_table)

    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 5: AGENT 2 (PLAN ENGINE)
    # =========================================================================
    story.append(Paragraph("Chapter 5: VeriSight Agent 2 — Verification Plan & Suite Architect", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "<b>VeriSight Agent 2 (VeriSight Plan)</b> represents a breakthrough in autonomous testbench architecture. In traditional silicon development, authoring a complete verification plan from architectural specifications takes weeks of manual work. Agent 2 ingests specifications in PDF, Markdown, or Text formats, analyzes the RTL interfaces, and synthesizes complete test plans, SystemVerilog functional coverage packages, and formal SVA assertion suites.",
        body_style
    ))

    story.append(Paragraph("Step-by-Step Operator Guide: Providing Planning Inputs", h2_style))
    story.append(Paragraph(
        "From the main wizard menu, select option <code>[2] VeriSight Plan</code>. The wizard prompts for the specification document and optional RTL sources:",
        body_style
    ))
    story.append(Spacer(1, 4))

    # SCREENSHOT 5
    story.append(screenshot_card(
        "docs/screenshots/screenshot_05_agent2_plan_inputs.png",
        "Figure 5.1: Agent 2 Input Prompting — Specification Document (PDF/MD) and RTL Ingestion",
        width=515,
        height=153
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Key Inputs for Verification Planning:", h3_style))
    story.append(Paragraph("• <b>Specification Document (.pdf, .md, .txt) [REQUIRED]:</b> The architectural specification describing device registers, protocol states, timing diagrams, and operational modes. Native PDF extraction is powered by <code>pypdf</code>.", bullet_style))
    story.append(Paragraph("• <b>RTL Source Directory (.sv, .v) [OPTIONAL]:</b> Top-level and sub-block RTL code. VeriSight parses port lists, clock/reset definitions, and parameter widths to ground the generated coverage and assertion models directly in actual hardware signal names.", bullet_style))
    story.append(Paragraph("• <b>Output Directory:</b> Target directory for the verification plan artifacts (defaults to <code>output/verification_plan/</code>).", bullet_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("The Autonomous Generation Architecture", h2_style))
    story.append(Paragraph(
        "Agent 2 executes five interconnected architectural modules to synthesize the complete verification suite:",
        body_style
    ))
    story.append(Paragraph("1. <b>Feature Decomposition (<code>feature_extractor.py</code>):</b> Hierarchically decomposes the specification into discrete functional blocks (e.g., Arithmetic Operations, Status Flags, Overflow Handlers, Clocking, Reset Sequences).", bullet_style))
    story.append(Paragraph("2. <b>Test Planning (<code>test_planner.py</code>):</b> Synthesizes directed, constrained-random, corner-case, and error-injection test cases with explicit stimulus and expected checking criteria.", bullet_style))
    story.append(Paragraph("3. <b>Coverage Architecture (<code>coverage_architect.py</code>):</b> Formulates complete SystemVerilog <code>covergroup</code> structures, sampling clocks, coverpoints with custom bins, and multi-variable <code>cross</code> coverage constructs.", bullet_style))
    story.append(Paragraph("4. <b>Assertion Architecture (<code>assertion_architect.py</code>):</b> Formulates SystemVerilog Assertions (SVA) with temporal operators (<code>|-></code>, <code>|=></code>, <code>##[1:5]</code>) for protocol invariants and interface contracts.", bullet_style))
    story.append(Paragraph("5. <b>Traceability Matrix (<code>traceability.py</code>):</b> Constructs an ISO 26262 and DO-254 compliant bi-directional traceability graph mapping every specification requirement to corresponding RTL signals, test cases, coverage points, and SVA properties.", bullet_style))
    story.append(Spacer(1, 6))

    # SCREENSHOT 6
    story.append(screenshot_card(
        "docs/screenshots/screenshot_06_agent2_plan_results.png",
        "Figure 5.2: Agent 2 Execution Output & Verification Plan Artifacts Generation",
        width=515,
        height=338
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Artifacts Generated by Agent 2 in output/verification_plan/:", h2_style))
    
    agent2_artifacts_data = [
        [Paragraph("<b>Artifact Filename</b>", body_style), Paragraph("<b>Language / Type</b>", body_style), Paragraph("<b>Content & Verification Functionality</b>", body_style)],
        [
            Paragraph("<b>verification_plan.html</b>", body_style),
            Paragraph("HTML5 / Interactive", body_style),
            Paragraph("Executive verification dashboard with live search filtering, requirement coverage heatmaps, test status tracking, and expandable SVA code inspection.", body_style)
        ],
        [
            Paragraph("<b>verification_plan.md</b>", body_style),
            Paragraph("Markdown", body_style),
            Paragraph("Comprehensive engineering verification plan formatted for direct inclusion in Git repositories, documentation wikis, and design review meetings.", body_style)
        ],
        [
            Paragraph("<b>traceability_matrix.csv</b>", body_style),
            Paragraph("CSV Spreadsheet", body_style),
            Paragraph("Bi-directional traceability matrix satisfying ISO 26262 (ASIL-D) and DO-254 safety sign-off requirements: <code>Requirement_ID &rarr; RTL_Signal &rarr; Test_ID &rarr; Covergroup &rarr; SVA_Property</code>.", body_style)
        ],
        [
            Paragraph("<b>coverage_model.sv</b>", body_style),
            Paragraph("SystemVerilog", body_style),
            Paragraph("Production-ready SystemVerilog functional coverage package containing parameterized <code>covergroup</code> models, explicit transition bins, and cross coverage ready for UVM subscriber integration.", body_style)
        ],
        [
            Paragraph("<b>dut_assertions.sv</b>", body_style),
            Paragraph("SystemVerilog (SVA)", body_style),
            Paragraph("Synthesized SVA checker module ready for direct SystemVerilog <code>bind</code> instantiation onto the DUT top-level interface.", body_style)
        ],
        [
            Paragraph("<b>verification_plan.json</b>", body_style),
            Paragraph("JSON Schema", body_style),
            Paragraph("Strict schema-compliant database containing all features, tests, coverage goals, and assertion definitions for programmatic ingestion by EDA coverage closure databases.", body_style)
        ]
    ]
    agent2_art_table = Table(agent2_artifacts_data, colWidths=[130, 110, 288])
    agent2_art_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(agent2_art_table)

    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 6: OPTION 3 (QUICK DEMOS)
    # =========================================================================
    story.append(Paragraph("Chapter 6: Option 3 — Guided Quick Demonstration Suite", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "To allow new verification engineers, prospective users, and engineering leadership to evaluate VeriSight within seconds without manually preparing or browsing for input files, author <b>Patel Kittu</b> integrated the <b>Quick Demos Suite</b> into Option 3 of the setup wizard.",
        body_style
    ))

    story.append(Paragraph("Selecting Pre-Packaged Demos", h2_style))
    story.append(Paragraph(
        "Selecting option <code>[3] Quick Demos</code> in Step 1 and confirming the LLM in Step 2 brings up the demo selection menu shown below:",
        body_style
    ))
    story.append(Spacer(1, 4))

    # SCREENSHOT 7
    story.append(screenshot_card(
        "docs/screenshots/screenshot_07_option3_demos.png",
        "Figure 6.1: Option 3 Quick Demos Menu — Instant 1-Click Verification & Debug Demos",
        width=515,
        height=200
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Deep Dive into the 4 Pre-Configured Demonstrations:", h2_style))
    
    demos_data = [
        [Paragraph("<b>Demo Option</b>", body_style), Paragraph("<b>Target Hardware & Bug Profile</b>", body_style), Paragraph("<b>Pre-Configured Inputs & Expected Outcome</b>", body_style)],
        [
            Paragraph("<b>[1] ALU Debug Demo</b>", body_style),
            Paragraph("Arithmetic Logic Unit (ALU)<br/><i>Combinational Latch / Missing Reset</i>", body_style),
            Paragraph("<b>Inputs:</b> <code>examples/specs/alu_spec.md</code>, <code>examples/rtl/</code>, <code>examples/logs/sim.log</code>.<br/><b>Outcome:</b> Detects uninitialized accumulator output during reset and produces a patch adding synchronous reset clearing.", body_style)
        ],
        [
            Paragraph("<b>[2] FIFO Debug Demo</b>", body_style),
            Paragraph("Synchronous FIFO Memory<br/><i>Read Pointer Underflow Bug</i>", body_style),
            Paragraph("<b>Inputs:</b> <code>projects/fifo/specs/spec.md</code>, <code>projects/fifo/rtl/</code>, <code>projects/fifo/logs/sim.log</code>.<br/><b>Outcome:</b> Identifies read pointer decrement when FIFO is empty and generates a patch enforcing empty flag gating.", body_style)
        ],
        [
            Paragraph("<b>[3] ALU Plan Demo</b>", body_style),
            Paragraph("Arithmetic Logic Unit (ALU)<br/><i>Full Verification Suite Synthesis</i>", body_style),
            Paragraph("<b>Inputs:</b> <code>examples/specs/alu_spec.md</code>, <code>examples/rtl/</code>.<br/><b>Outcome:</b> Synthesizes 8 functional features, 14 test cases, 12 SystemVerilog coverpoints, 10 SVA properties, and HTML dashboard.", body_style)
        ],
        [
            Paragraph("<b>[4] FIFO Plan Demo</b>", body_style),
            Paragraph("Synchronous FIFO Queue<br/><i>Memory & Protocol Architecture</i>", body_style),
            Paragraph("<b>Inputs:</b> <code>projects/fifo/specs/spec.md</code>, <code>projects/fifo/rtl/</code>.<br/><b>Outcome:</b> Generates full testbench plan covering full/empty boundaries, simultaneous read/write bursts, and watermarking SVA assertions.", body_style)
        ]
    ]
    demos_t = Table(demos_data, colWidths=[120, 140, 268])
    demos_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(demos_t)
    story.append(Spacer(1, 10))

    story.append(callout_box(
        "The Quick Demos automatically populate all file paths and create dedicated output folders (<code>output/demo_alu_debug/</code>, <code>output/demo_fifo_plan/</code>), leaving existing work untouched.",
        "tip"
    ))
    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 7: OPTION 4 & CLI AUTOMATION
    # =========================================================================
    story.append(Paragraph("Chapter 7: Option 4 — Clean Exit & Headless CI/CD Automation", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "Selecting option <code>[4] Exit</code> in the wizard terminates the interactive session cleanly and displays advanced command-line (CLI) usage patterns for automated nightly regression flows and CI/CD pipelines.",
        body_style
    ))

    # SCREENSHOT 8
    story.append(screenshot_card(
        "docs/screenshots/screenshot_08_cli_and_exit.png",
        "Figure 7.1: Option 4 Exit Screen — Clean Termination & Direct CLI Power Commands",
        width=515,
        height=292
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Automated Headless & Regression Execution (CI/CD)", h2_style))
    story.append(Paragraph(
        "While the interactive wizard is ideal for interactive debugging, enterprise semiconductor verification requires automated execution inside LSF, Slurm, Jenkins, or GitHub Actions. VeriSight supports full headless command-line execution without requiring interactive user input:",
        body_style
    ))

    story.append(Paragraph("1. Direct Simulation Debug Execution:", h3_style))
    story.append(code_box(
        "python main.py \\\n"
        "    --spec examples/specs/alu_spec.md \\\n"
        "    --rtl examples/rtl/ \\\n"
        "    --tb examples/tb/ \\\n"
        "    --log examples/logs/sim.log \\\n"
        "    --output output/regression_run_01 \\\n"
        "    --provider gemini \\\n"
        "    --model gemini-2.0-flash"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. Direct Verification Plan Synthesis Execution:", h3_style))
    story.append(code_box(
        "python main.py plan \\\n"
        "    --spec examples/specs/alu_spec.md \\\n"
        "    --rtl examples/rtl/ \\\n"
        "    --output output/verification_plan \\\n"
        "    --provider anthropic"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Comprehensive CLI Parameter Reference Table:", h2_style))
    
    cli_params_data = [
        [Paragraph("<b>CLI Argument</b>", body_style), Paragraph("<b>Type / Default</b>", body_style), Paragraph("<b>Description & Operational Function</b>", body_style)],
        [Paragraph("<code>--spec &lt;path&gt;</code>", body_style), Paragraph("File Path (.md, .pdf, .txt)", body_style), Paragraph("Path to architectural specification document.", body_style)],
        [Paragraph("<code>--rtl &lt;path&gt;</code>", body_style), Paragraph("Directory or File (.sv, .v)", body_style), Paragraph("Path to Design Under Test (DUT) hardware description files.", body_style)],
        [Paragraph("<code>--tb &lt;path&gt;</code>", body_style), Paragraph("Directory or File (.sv)", body_style), Paragraph("Path to UVM / SystemVerilog testbench source files.", body_style)],
        [Paragraph("<code>--log &lt;path&gt;</code>", body_style), Paragraph("File Path (.log, .txt)", body_style), Paragraph("Path to simulation log containing failure messages.", body_style)],
        [Paragraph("<code>--output &lt;dir&gt;</code>", body_style), Paragraph("Directory (default: output)", body_style), Paragraph("Destination directory for generated reports, HTML, and patches.", body_style)],
        [Paragraph("<code>--provider &lt;name&gt;</code>", body_style), Paragraph("gemini | anthropic", body_style), Paragraph("Selects cloud LLM provider (defaults to detected environment key).", body_style)],
        [Paragraph("<code>--model &lt;name&gt;</code>", body_style), Paragraph("Model String", body_style), Paragraph("Overrides target LLM model name (e.g. gemini-2.0-flash, claude-sonnet-5).", body_style)],
        [Paragraph("<code>--no-rag</code>", body_style), Paragraph("Boolean Flag", body_style), Paragraph("Disables ChromaDB vector knowledge base queries for air-gapped runs.", body_style)],
        [Paragraph("<code>-i, --interactive</code>", body_style), Paragraph("Boolean Flag", body_style), Paragraph("Launches the interactive wizard interface.", body_style)],
    ]
    cli_table = Table(cli_params_data, colWidths=[120, 110, 298])
    cli_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(cli_table)

    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 8: BEST PRACTICES
    # =========================================================================
    story.append(Paragraph("Chapter 8: Verification Engineering Best Practices & Sign-Off Checklist", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "To achieve tapeout-ready silicon sign-off, functional verification teams must adhere to disciplined engineering methodologies. This chapter outlines best practices for integrating VeriSight into production semiconductor design flows.",
        body_style
    ))

    story.append(Paragraph("1. Closing the Verification Coverage Hole", h2_style))
    story.append(Paragraph(
        "A common pitfall in digital verification is relying exclusively on line and branch code coverage. While code coverage confirms that specific HDL statements executed, it provides zero assurance that functional features operate correctly under stressful corner-cases. VeriSight Agent 2 addresses this by enforcing <b>multi-dimensional cross coverage</b>:",
        body_style
    ))
    story.append(Paragraph("• Cross operational modes with bus error responses (e.g. <code>burst_type &times; error_resp</code>).", bullet_style))
    story.append(Paragraph("• Cross FIFO occupancy thresholds with concurrent read/write transactions.", bullet_style))
    story.append(Paragraph("• Sample coverage points strictly synchronous to design clocks rather than asynchronous events.", bullet_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. Formal SystemVerilog Assertions (SVA) Guidelines", h2_style))
    story.append(Paragraph(
        "VeriSight synthesizes SVA properties using overlapping (<code>|-&gt;</code>) and non-overlapping (<code>|=&gt;</code>) implication operators. Follow these guidelines when integrating <code>dut_assertions.sv</code> into your testbench:",
        body_style
    ))
    story.append(Paragraph("• <b>Use <code>bind</code> instantiations:</b> Never manually edit RTL source files to insert assertions. Use SystemVerilog <code>bind</code> directives to connect <code>dut_assertions.sv</code> directly to DUT signal hierarchies.", bullet_style))
    story.append(Paragraph("• <b>Disable during reset:</b> Ensure all properties include active-low or active-high reset disqualifiers (e.g. <code>disable iff (!rst_n)</code>) to prevent false assertions during power-on initialization.", bullet_style))
    story.append(Paragraph("• <b>Pair Assert with Cover:</b> For every <code>assert property</code>, include an identical <code>cover property</code> to verify in simulation that the assertion precondition was actually exercised.", bullet_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("3. Tapeout Sign-Off Readiness Checklist (Table 8.1)", h2_style))

    checklist_data = [
        [Paragraph("<b>Sign-Off Milestone</b>", body_style), Paragraph("<b>Verification Requirement</b>", body_style), Paragraph("<b>VeriSight Tool Validation</b>", body_style)],
        [
            Paragraph("<b>Requirement Traceability</b>", body_style),
            Paragraph("100% of specification requirements mapped to active test scenarios and covergroups.", body_style),
            Paragraph("Verify via <code>traceability_matrix.csv</code>. Ensure zero unmapped requirements in <code>verification_plan.html</code>.", body_style)
        ],
        [
            Paragraph("<b>Functional Coverage Closure</b>", body_style),
            Paragraph("100% functional coverage reached across all defined coverpoints and cross bins.", body_style),
            Paragraph("Simulate with synthesized <code>coverage_model.sv</code> in Questa/VCS coverage engines.", body_style)
        ],
        [
            Paragraph("<b>Zero X-Propagation Bugs</b>", body_style),
            Paragraph("No uninitialized states or unknown logic values propagating to memory or interfaces.", body_style),
            Paragraph("Run VeriSight X-Tracer gate-level backward propagation on gate-level simulation logs.", body_style)
        ],
        [
            Paragraph("<b>Clean Regression Log Analysis</b>", body_style),
            Paragraph("Zero UVM_ERROR or UVM_FATAL banners across random seed regression runs.", body_style),
            Paragraph("Execute Agent 1 batch regression mode. Verify <code>error.json</code> reports 0 failures.", body_style)
        ]
    ]
    check_table = Table(checklist_data, colWidths=[130, 190, 208])
    check_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(check_table)

    story.append(PageBreak())

    # =========================================================================
    # CHAPTER 9: SCHEMAS & TROUBLESHOOTING
    # =========================================================================
    story.append(Paragraph("Chapter 9: System Schemas, Configuration & Troubleshooting", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph(
        "This chapter details the underlying Pydantic schema representations, key environment configuration flags in <code>verisight/config.py</code>, and troubleshooting resolutions for common runtime errors.",
        body_style
    ))

    story.append(Paragraph("VeriSight Unified Configuration Schema (verisight/config.py)", h2_style))
    story.append(Paragraph(
        "VeriSight encapsulates all subsystem configurations into typed Pydantic models. Engineers can customize these settings programmatically or via environment variables:",
        body_style
    ))
    story.append(code_box(
        "class VeriSightConfig(BaseModel):\n"
        "    llm: LLMConfig = Field(default_factory=LLMConfig)\n"
        "    chroma: ChromaConfig = Field(default_factory=ChromaConfig)\n"
        "    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)\n"
        "    xtracer: XTracerConfig = Field(default_factory=XTracerConfig)\n"
        "    fix: FixConfig = Field(default_factory=FixConfig)\n"
        "    log_level: str = 'INFO'"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Troubleshooting & Error Remediation Guide (Table 9.1)", h2_style))

    troubleshoot_data = [
        [Paragraph("<b>Observed Issue / Error</b>", body_style), Paragraph("<b>Underlying Cause</b>", body_style), Paragraph("<b>Immediate Corrective Action</b>", body_style)],
        [
            Paragraph("<b>API Key Not Detected</b><br/><code>LLMAuthenticationError</code>", body_style),
            Paragraph("Missing <code>GEMINI_API_KEY</code> or <code>ANTHROPIC_API_KEY</code> in current shell.", body_style),
            Paragraph("Run the wizard and select option 3 or 4 to enter your key, or export it in your shell: <code>export GEMINI_API_KEY='AIza...'</code>.", body_style)
        ],
        [
            Paragraph("<b>Path Not Found in WSL</b><br/><code>C:\\path\\file.sv</code>", body_style),
            Paragraph("Windows drive paths are located under the WSL mount point <code>/mnt/c/</code>.", body_style),
            Paragraph("VeriSight auto-converts <code>C:\\</code> to <code>/mnt/c/</code>. Verify the path exists in Linux via <code>ls /mnt/c/...</code>.", body_style)
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
            Paragraph("Inspect <code>output/fifo_debug/fix/corrected_snippet.sv</code> and apply the change manually or re-run analysis.", body_style)
        ]
    ]
    trouble_table = Table(troubleshoot_data, colWidths=[130, 160, 238])
    trouble_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(trouble_table)

    story.append(PageBreak())

    # =========================================================================
    # APPENDIX & OPERATOR CHEATSHEET
    # =========================================================================
    story.append(Paragraph("Appendix: Operator Command Cheatsheet & Acronym Glossary", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph("Quick-Reference Command Dictionary", h2_style))

    cheatsheet_data = [
        [Paragraph("<b>Operational Goal</b>", body_style), Paragraph("<b>Command-Line Syntax</b>", body_style)],
        [Paragraph("Launch Interactive Setup Wizard", body_style), Paragraph("<code>./start.sh</code> &nbsp;or&nbsp; <code>python main.py start</code>", body_style)],
        [Paragraph("Run ALU Debug 1-Click Demo", body_style), Paragraph("<code>python main.py --spec examples/specs/alu_spec.md --rtl examples/rtl/ --log examples/logs/sim.log</code>", body_style)],
        [Paragraph("Run FIFO Debug 1-Click Demo", body_style), Paragraph("<code>python main.py --spec projects/fifo/specs/spec.md --rtl projects/fifo/rtl/ --log projects/fifo/logs/sim.log</code>", body_style)],
        [Paragraph("Synthesize Verification Plan (Markdown/PDF)", body_style), Paragraph("<code>python main.py plan --spec examples/specs/alu_spec.md --rtl examples/rtl/</code>", body_style)],
        [Paragraph("Run in 100% Offline Mode (No Cloud LLM)", body_style), Paragraph("Select option 5 in LLM Setup, or run with <code>--no-rag</code> and omit API keys", body_style)],
        [Paragraph("Execute Pytest Unit Test Suite", body_style), Paragraph("<code>python -m pytest tests/ -v</code>", body_style)],
        [Paragraph("Apply Generated RTL Code Fix", body_style), Paragraph("<code>git apply output/fifo_debug/fix/proposed.patch</code>", body_style)],
        [Paragraph("View Interactive HTML Report in Browser", body_style), Paragraph("<code>open output/fifo_debug/report.html</code> &nbsp;or&nbsp; <code>xdg-open output/verification_plan/verification_plan.html</code>", body_style)],
    ]
    cheat_t = Table(cheatsheet_data, colWidths=[190, 338])
    cheat_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(cheat_t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Semiconductor Verification Acronym Glossary", h2_style))

    acronym_data = [
        [Paragraph("<b>Acronym</b>", body_style), Paragraph("<b>Full Standard Definition</b>", body_style)],
        [Paragraph("<b>AST</b>", body_style), Paragraph("Abstract Syntax Tree — Hierarchical syntactic tree representation of HDL code.", body_style)],
        [Paragraph("<b>CDC</b>", body_style), Paragraph("Clock Domain Crossing — Signals transmitted between asynchronous clock regimes.", body_style)],
        [Paragraph("<b>DUT</b>", body_style), Paragraph("Design Under Test — The target hardware module being simulated or verified.", body_style)],
        [Paragraph("<b>RCA</b>", body_style), Paragraph("Root Cause Analysis — Algorithmic isolation of the primary source of a silicon defect.", body_style)],
        [Paragraph("<b>RAG</b>", body_style), Paragraph("Retrieval-Augmented Generation — Semantic context injection from vector databases.", body_style)],
        [Paragraph("<b>SVA</b>", body_style), Paragraph("SystemVerilog Assertions — Formal temporal logic properties verifying protocol rules.", body_style)],
        [Paragraph("<b>UVM</b>", body_style), Paragraph("Universal Verification Methodology — IEEE 1800.2 standard class library for testbenches.", body_style)],
        [Paragraph("<b>X-State</b>", body_style), Paragraph("Unknown Logic State — Uninitialized logic value in 4-state simulation ('X').", body_style)],
    ]
    acronym_t = Table(acronym_data, colWidths=[100, 428])
    acronym_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(acronym_t)
    story.append(Spacer(1, 20))

    # Concluding signature
    concl_p = Paragraph(
        "<b>VeriSight™ Silicon Verification Copilot</b> — Engineered by <b>Patel Kittu</b> (@KITTUV03).<br/>"
        "Mirafra Technologies • All Rights Reserved • 2026",
        ParagraphStyle('Concl', parent=body_style, fontSize=8.5, leading=12, alignment=TA_CENTER, textColor=c_muted)
    )
    story.append(concl_p)

    print("Building multi-page PDF document...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"SUCCESS: {PDF_FILENAME} successfully built!")

if __name__ == '__main__':
    build_pdf()
