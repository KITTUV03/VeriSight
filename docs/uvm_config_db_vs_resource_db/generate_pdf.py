import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
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

            # 1. Prepend watermark directly to the background of the PDF content stream
            temp_c = canvas.Canvas(None, pagesize=letter)
            temp_c.saveState()
            temp_c.setFont("Helvetica-Bold", 58)
            temp_c.setFillColor(colors.HexColor("#E2E8F0")) # Subtle, professional slate watermark
            temp_c.translate(letter[0] / 2.0, letter[1] / 2.0)
            temp_c.rotate(45)
            temp_c.drawCentredString(0, 0, "Kittu Patel")
            temp_c.restoreState()

            self._code = temp_c._code + self._code

            # 2. Draw running header & footer on foreground
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.saveState()
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#334155"))
            self.drawString(45, letter[1] - 32, "UVM ARCHITECTURE DEEP DIVE: uvm_resource_db vs. uvm_config_db")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawRightString(letter[0] - 45, letter[1] - 32, "TECHNICAL WHITEPAPER")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.6)
            self.line(45, letter[1] - 36, letter[0] - 45, letter[1] - 36)
            self.restoreState()

        # Running Footer (all pages)
        self.saveState()
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(45, 38, letter[0] - 45, 38)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(45, 26, "Author: Kittu Patel | SystemVerilog & UVM Architecture Series")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 45, 26, page_str)
        self.restoreState()

def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=45,
        rightMargin=45,
        topMargin=46,
        bottomMargin=48
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"), # Dark Navy
        spaceBefore=7,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=4
    )

    body_bold = ParagraphStyle(
        'BodyDarkBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'CodeSnippet',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A")
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E3A8A")
    )

    table_header_style = ParagraphStyle(
        'TH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        alignment=1 # Center
    )

    table_cell_bold = ParagraphStyle(
        'TCB',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A")
    )

    table_cell_style = ParagraphStyle(
        'TC',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#334155")
    )

    story = []

    # ================= PAGE 1 =================
    story.append(Paragraph("Under the Hood of UVM: Architectural Analysis of uvm_resource_db vs. uvm_config_db", title_style))
    story.append(Paragraph("A Deep Source-Code & Implementation Perspective on Scope Resolution, Precedence, and Internal Pool Mechanics", subtitle_style))
    story.append(Paragraph("Author: <b>Kittu Patel</b> | Core Focus: SystemVerilog / UVM Verification Infrastructure", meta_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#1E3A8A"), spaceAfter=6, spaceBefore=0))

    story.append(Paragraph("1. Executive Summary & The Fundamental Misconception", h1_style))
    story.append(Paragraph(
        "A widespread misconception across the verification community is that <code>uvm_resource_db</code> and <code>uvm_config_db</code> are two independent, isolated configuration storage engines within the Universal Verification Methodology (UVM). In reality, <b>they share the exact same underlying singleton database</b>: the <code>uvm_resource_pool</code>. Furthermore, in the UVM class library (IEEE 1800.2 / Accellera UVM), <code>uvm_config_db#(T)</code> is directly declared as <code>class uvm_config_db#(type T=int) extends uvm_resource_db#(T)</code>.",
        body_style
    ))
    story.append(Paragraph(
        "While <code>uvm_resource_db</code> provides a generic, scope-string and type-based key-value repository, <code>uvm_config_db</code> is an architectural facade engineered to introduce <b>hierarchical context awareness</b>, <b>top-down elaboration precedence</b>, and <b>lifecycle tracking</b> tailored specifically to the <code>uvm_component</code> tree.",
        body_style
    ))

    story.append(Paragraph("2. Architectural Blueprint: The Singleton Pool Engine", h1_style))
    story.append(Paragraph(
        "The underlying storage engine is <code>uvm_resource_pool</code>, accessed globally via <code>uvm_resource_pool::get()</code>. Every entry placed into either database is encapsulated in a <code>uvm_resource#(T)</code> container, which stores the value payload, string scope, regex matching expression, precedence integer, and access history.",
        body_style
    ))

    # Architecture Callout Box
    arch_box_data = [[
        Paragraph(
            "<b>Internal Pool Tables:</b><br/>"
            "• <b>Name Table (<code>rtab</code>):</b> Associative array <code>uvm_resource_types::rsrc_q_t rtab[string]</code> mapping field/name strings to queues of resource handles.<br/>"
            "• <b>Type Table (<code>ttab</code>):</b> Associative array <code>uvm_resource_types::rsrc_q_t ttab[uvm_resource_base]</code> mapping resource type-handles to queues.<br/>"
            "• <b>Precedence Queue:</b> When multiple resources match a query, the pool sorts them by a numerical <code>precedence</code> property. Ties are broken in FIFO order (last-write-wins).",
            callout_style
        )
    ]]
    arch_box = Table(arch_box_data, colWidths=[522])
    arch_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(arch_box)
    story.append(Spacer(1, 6))

    story.append(Paragraph("3. Architectural Comparison Matrix", h1_style))
    
    # Table Comparison
    matrix_data = [
        [
            Paragraph("Architectural Dimension", table_header_style),
            Paragraph("uvm_resource_db#(T)", table_header_style),
            Paragraph("uvm_config_db#(T)", table_header_style)
        ],
        [
            Paragraph("OOP Inheritance", table_cell_bold),
            Paragraph("Direct interface to <code>uvm_resource_pool</code>", table_cell_style),
            Paragraph("Subclass: <code>extends uvm_resource_db#(T)</code>", table_cell_style)
        ],
        [
            Paragraph("API Signature (set)", table_cell_bold),
            Paragraph("<code>set(scope, name, val, accessor)</code>", table_cell_style),
            Paragraph("<code>set(cntxt, inst_name, field_name, value)</code>", table_cell_style)
        ],
        [
            Paragraph("Scope Construction", table_cell_bold),
            Paragraph("Manual raw strings & regex (e.g., <code>\"top.*\"</code>)", table_cell_style),
            Paragraph("Auto-concatenates <code>cntxt.get_full_name()</code> + <code>inst_name</code>", table_cell_style)
        ],
        [
            Paragraph("Precedence in build_phase", table_cell_bold),
            Paragraph("Uniform (1000). Last write wins chronologically", table_cell_style),
            Paragraph("<b>Hierarchical (1000 - depth)</b>. Parent overrides child", table_cell_style)
        ],
        [
            Paragraph("Precedence in run_phase", table_cell_bold),
            Paragraph("Uniform (1000). Last write wins", table_cell_style),
            Paragraph("Reverts to Uniform (1000). Last write wins", table_cell_style)
        ],
        [
            Paragraph("Type-Based Lookup", table_cell_bold),
            Paragraph("Supported via <code>read_by_type(scope, val)</code>", table_cell_style),
            Paragraph("Not supported (field name mandatory)", table_cell_style)
        ],
        [
            Paragraph("Dynamic Synchronization", table_cell_bold),
            Paragraph("Manual polling or event triggers", table_cell_style),
            Paragraph("Built-in task: <code>wait_modified(cntxt, inst, field)</code>", table_cell_style)
        ],
        [
            Paragraph("Diagnostic Tracing", table_cell_bold),
            Paragraph("Generic pool dump (<code>dump()</code>)", table_cell_style),
            Paragraph("Dedicated CLI: <code>+UVM_CONFIG_DB_TRACE</code> & audit APIs", table_cell_style)
        ]
    ]

    mat_table = Table(matrix_data, colWidths=[110, 206, 206])
    mat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(mat_table)

    # Force PageBreak to guarantee exact multi-page alignment
    story.append(PageBreak())

    # ================= PAGE 2 =================
    story.append(Paragraph("4. Under the Hood: Scope Resolution in uvm_config_db::set", h1_style))
    story.append(Paragraph(
        "When an engineer calls <code>uvm_config_db#(T)::set(cntxt, inst_name, field_name, value)</code>, the method executes a rigorous path normalization algorithm before invoking the lower-level resource database:",
        body_style
    ))

    code_p2_1 = (
        "// Source excerpt adapted from uvm_config_db.svh\n"
        "static function void set(uvm_component cntxt, string inst_name, string field_name, T value);\n"
        "  uvm_root top = uvm_root::get();\n"
        "  string lookup_inst_name;\n"
        "  if (cntxt == null) cntxt = top;\n"
        "  if (inst_name == \"\") lookup_inst_name = cntxt.get_full_name();\n"
        "  else if (cntxt.get_full_name() != \"\") lookup_inst_name = {cntxt.get_full_name(), \".\", inst_name};\n"
        "  else lookup_inst_name = inst_name;\n"
        "  // Calculates precedence and pushes into uvm_resource_db\n"
        "  rsrc_t r = new(field_name, lookup_inst_name);\n"
        "  r.write(value, cntxt);\n"
        "  m_set_precedence(r, cntxt);\n"
        "  r.set();\n"
        "endfunction"
    )
    code_box1 = Table([[Paragraph(code_p2_1.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style)]], colWidths=[522])
    code_box1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.8, colors.HexColor("#94A3B8")),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(code_box1)
    story.append(Spacer(1, 4))

    story.append(Paragraph("5. The Secret Sauce: Precedence Mechanics & Parent-Wins Rule", h1_style))
    story.append(Paragraph(
        "The defining behavioral differentiator between the two databases is <b>how configuration conflicts are arbitrated during elaboration</b>. In standard <code>uvm_resource_db</code>, entries written to the same scope and name simply overwrite each other in temporal order (the last write wins).",
        body_style
    ))
    story.append(Paragraph(
        "To allow parent components (like a test or top environment) to impose configuration overrides down the hierarchy without depending on phase execution order, <code>uvm_config_db</code> calculates dynamic precedence:",
        body_style
    ))

    # Formula Callout Box
    formula_data = [[
        Paragraph(
            "<b>The Build-Phase Precedence Formula:</b><br/>"
            "<code>precedence = uvm_resource_base::default_precedence - cntxt.get_depth();</code><br/>"
            "• <code>default_precedence = 1000</code><br/>"
            "• <code>uvm_top</code> (depth = 0) &rarr; Precedence = <b>1000</b><br/>"
            "• <code>base_test</code> (depth = 1) &rarr; Precedence = <b>999</b><br/>"
            "• <code>top_env</code> (depth = 2) &rarr; Precedence = <b>998</b><br/>"
            "• <code>agent</code> (depth = 3) &rarr; Precedence = <b>997</b><br/>"
            "<i>Because parent components possess lower depth integers, they are awarded higher precedence values!</i>",
            callout_style
        )
    ]]
    f_box = Table(formula_data, colWidths=[522])
    f_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BFDBFE")),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(f_box)
    story.append(Spacer(1, 4))

    story.append(Paragraph("6. Architectural Trace: Resolving Competing Writes", h1_style))
    story.append(Paragraph(
        "When <code>uvm_config_db#(T)::get()</code> is executed, the lookup delegates to <code>uvm_resource_pool</code>, which retrieves all matching resources and executes <code>sort_by_precedence()</code>:",
        body_style
    ))

    code_p2_2 = (
        "// TEST level (Depth 1): Runs early in build_phase\n"
        "uvm_config_db#(int)::set(this, \"env.agent*\", \"is_active\", UVM_PASSIVE); // Precedence = 999\n\n"
        "// ENV level (Depth 2): Runs later in build_phase\n"
        "uvm_config_db#(int)::set(this, \"agent*\", \"is_active\", UVM_ACTIVE);     // Precedence = 998\n\n"
        "// AGENT level (Depth 3): Reads configuration\n"
        "uvm_config_db#(int)::get(this, \"\", \"is_active\", is_active);\n"
        "// RESULT: is_active == UVM_PASSIVE (Test wins, even though Env wrote LATER!)"
    )
    code_box2 = Table([[Paragraph(code_p2_2.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style)]], colWidths=[522])
    code_box2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.8, colors.HexColor("#94A3B8")),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(code_box2)
    story.append(Spacer(1, 4))

    story.append(Paragraph("7. The Phase Shift: Runtime Transition to Last-Write-Wins", h1_style))
    story.append(Paragraph(
        "Crucially, the hierarchical precedence rule applies <b>strictly during the build_phase</b>. Once the UVM simulation transitions into runtime phases (e.g., <code>run_phase</code>), <code>uvm_config_db::set</code> abandons depth-based calculations and assigns the default precedence (1000) to all writes. When multiple entries share the exact same precedence, the resource pool resolves them via FIFO queue ordering, effectively converting the lookup back to <b>Last Write Wins</b>.",
        body_style
    ))

    # Force PageBreak to guarantee exact multi-page alignment
    story.append(PageBreak())

    # ================= PAGE 3 =================
    story.append(Paragraph("8. Advanced Facilities in uvm_config_db", h1_style))
    story.append(Paragraph(
        "Beyond hierarchical precedence, <code>uvm_config_db</code> provides specialized verification mechanisms that are completely absent in bare <code>uvm_resource_db</code>:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Runtime Synchronization (<code>wait_modified</code>):</b> A blocking task enabling components to stall execution until a specific configuration entry is altered during the <code>run_phase</code>: <code>uvm_config_db#(int)::wait_modified(this, \"\", \"clock_div\");</code>",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Configuration Audit API:</b> Calling <code>uvm_config_db::check_config_usage()</code> scans the pool and alerts engineers to configurations set by testbenches that were never read by any component (revealing silent naming typos).",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Diagnostic Tracing:</b> Passing <code>+UVM_CONFIG_DB_TRACE</code> on the simulator command line triggers verbose runtime logs detailing every <code>set</code> and <code>get</code> operation, hierarchical scope matching, and precedence resolution.",
        bullet_style
    ))

    story.append(Paragraph("9. Specialized Capabilities of uvm_resource_db", h1_style))
    story.append(Paragraph(
        "While <code>uvm_config_db</code> is the recommended standard for component configuration, <code>uvm_resource_db</code> remains vital for specific use cases:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Type-Based Resolution (<code>read_by_type</code>):</b> Allows retrieving an object solely by its parameterized datatype without specifying a string field name (useful in polymorphic service factories).",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Non-Component Scopes (Sequences & Transactions):</b> <code>uvm_sequence_item</code> and <code>uvm_sequence</code> objects are transient and do not reside in the static <code>uvm_component</code> hierarchy. <code>uvm_resource_db</code> provides clean string-scoped access without requiring artificial component context handles.",
        bullet_style
    ))

    story.append(Paragraph("10. Critical Pitfalls & Performance Hazards", h1_style))
    
    pitfall_data = [[
        Paragraph(
            "<b>Top 3 Production Traps in UVM Verification:</b><br/>"
            "1. <b>The Dangerous Hybrid Anti-Pattern:</b> Writing a setting using <code>uvm_resource_db::set()</code> and reading it with <code>uvm_config_db::get()</code> (or vice versa). Because <code>uvm_resource_db</code> assigns uniform precedence while <code>uvm_config_db</code> applies depth-adjusted precedence, the lookup order becomes erratic and nondeterministic.<br/>"
            "2. <b>Wildcard Regular Expression Explosion:</b> Overusing broad wildcards (e.g., <code>\"*\"</code>) forces <code>uvm_resource_pool</code> to execute costly regex evaluations across every entry in the associative table on every lookup, significantly slowing simulation elaboration.<br/>"
            "3. <b>Unchecked Return Status:</b> Always verify the boolean return of <code>get()</code>. A missing virtual interface or null configuration object leads to fatal runtime null-pointer dereferences.",
            callout_style
        )
    ]]
    pitfall_box = Table(pitfall_data, colWidths=[522])
    pitfall_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#FECACA")),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(pitfall_box)
    story.append(Spacer(1, 4))

    story.append(Paragraph("11. Senior DV Engineer Decision Framework & Golden Rules", h1_style))

    rules_table_data = [
        [
            Paragraph("Verification Scenario", table_header_style),
            Paragraph("Recommended Engine", table_header_style),
            Paragraph("Architectural Rationale", table_header_style)
        ],
        [
            Paragraph("Passing Virtual Interfaces (vif)", table_cell_bold),
            Paragraph("<code>uvm_config_db#(virtual intf)</code>", table_cell_style),
            Paragraph("Enforces top-down authority; Top/Test binds interface directly to agents.", table_cell_style)
        ],
        [
            Paragraph("Agent & Subsystem Configuration Objects", table_cell_bold),
            Paragraph("<code>uvm_config_db#(cfg_obj)</code>", table_cell_style),
            Paragraph("Preserves hierarchical override integrity during <code>build_phase</code>.", table_cell_style)
        ],
        [
            Paragraph("Global Test Parameters across Sequences", table_cell_bold),
            Paragraph("<code>uvm_resource_db#(T)</code>", table_cell_style),
            Paragraph("Sequences lack component hierarchy context; raw scope strings avoid confusion.", table_cell_style)
        ],
        [
            Paragraph("Runtime Configuration Handshakes", table_cell_bold),
            Paragraph("<code>uvm_config_db#(T)::wait_modified</code>", table_cell_style),
            Paragraph("Provides built-in reactive event synchronization without custom semaphores.", table_cell_style)
        ]
    ]

    rules_table = Table(rules_table_data, colWidths=[130, 155, 237])
    rules_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(rules_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "<b>Key Takeaway for Verification Architects:</b> Treat <code>uvm_resource_db</code> as the foundational raw memory mechanism, and <code>uvm_config_db</code> as the structured, object-oriented memory manager with built-in hierarchy arbitration. In 95% of testbench design, <code>uvm_config_db</code> is the required standard.",
        body_bold
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated {filename}")

if __name__ == '__main__':
    output_pdf = "docs/uvm_config_db_vs_resource_db/UVM_Resource_DB_vs_Config_DB_Deep_Dive.pdf"
    build_pdf(output_pdf)
