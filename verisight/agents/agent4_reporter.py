"""
Agent 4 — Report Generator.

Generates comprehensive reports from the analysis pipeline:
- error.json — Machine-readable error report
- report.md — Detailed Markdown report
- report.html — Styled HTML report
- summary.txt — Executive summary

Stores debugging session in ChromaDB for future RAG retrieval.
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from jinja2 import Environment, FileSystemLoader, BaseLoader

from verisight.agents.base_agent import BaseAgent
from verisight.schemas.knowledge_schema import UnifiedKnowledge
from verisight.schemas.classification import Classification, EvidenceItem
from verisight.schemas.rtl_analysis import RTLAnalysis
from verisight.schemas.report_schema import (
    ErrorReport, RecommendedFix, PreventionMeasure,
)
from verisight.rag.knowledge_base import KnowledgeBase
from verisight.utils.file_utils import save_json, save_text
from verisight.utils.logger import get_logger

logger = get_logger("agent4_reporter")


class ReportGeneratorAgent(BaseAgent):
    """
    Agent 4: Report Generator.

    Produces error.json, report.md, report.html, and summary.txt.
    """

    def __init__(
        self,
        output_dir: str = "output",
        knowledge_base: Optional[KnowledgeBase] = None,
    ):
        super().__init__("report_generator")
        self.output_dir = Path(output_dir)
        self.kb = knowledge_base
        self.template_dir = Path(__file__).parent.parent.parent / "templates"

    def execute(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        rtl_analysis: Optional[RTLAnalysis] = None,
    ) -> ErrorReport:
        """
        Generate all reports from the analysis pipeline.

        Args:
            knowledge: UnifiedKnowledge from Agent 1.
            classification: Classification from Agent 2.
            rtl_analysis: Optional RTLAnalysis from Agent 3.

        Returns:
            ErrorReport — the final machine-readable report.
        """
        self.logger.info("=" * 60)
        self.logger.info("Agent 4: Report Generator — Starting")
        self.logger.info("=" * 60)

        session_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # Build the error report
        report = self._build_error_report(
            knowledge, classification, rtl_analysis, session_id, timestamp
        )

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save error.json
        save_json(report, self.output_dir / "error.json")

        # Save classification summary.json
        save_json(classification, self.output_dir / "summary.json")

        # Save RTL analysis sub-module JSONs
        if rtl_analysis:
            analysis_dir = self.output_dir / "analysis"
            analysis_dir.mkdir(exist_ok=True)
            save_json(rtl_analysis.xtrace, analysis_dir / "xtrace.json")
            save_json(rtl_analysis.functional, analysis_dir / "functional.json")
            save_json(rtl_analysis.cdc, analysis_dir / "cdc.json")
            save_json(rtl_analysis.lint, analysis_dir / "lint.json")
            save_json(rtl_analysis.structural, analysis_dir / "structure.json")
            save_json(rtl_analysis.protocol, analysis_dir / "protocol.json")
            save_json(rtl_analysis.misc, analysis_dir / "misc.json")

        # Generate text reports
        report_context = self._build_report_context(
            knowledge, classification, rtl_analysis, report
        )

        # Generate Markdown report
        md_report = self._generate_markdown_report(report_context)
        save_text(md_report, self.output_dir / "report.md")

        # Generate HTML report
        html_report = self._generate_html_report(report_context)
        save_text(html_report, self.output_dir / "report.html")

        # Generate summary.txt
        summary = self._generate_summary(report_context)
        save_text(summary, self.output_dir / "summary.txt")

        # Store session in ChromaDB
        if self.kb:
            self._store_session(report, knowledge, session_id)

        self.logger.info("=" * 60)
        self.logger.info("Agent 4: Report Generation Complete")
        self.logger.info(f"  Output directory: {self.output_dir}")
        self.logger.info(f"  error.json, summary.json, report.md, report.html, summary.txt")
        self.logger.info("=" * 60)

        return report

    def _build_error_report(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        rtl_analysis: Optional[RTLAnalysis],
        session_id: str,
        timestamp: str,
    ) -> ErrorReport:
        """Build the final ErrorReport from all analysis results."""

        # Build recommended fixes
        fixes = []
        if classification.recommended_fix:
            fixes.append(RecommendedFix(
                action=classification.recommended_fix,
                priority="high",
            ))

        if rtl_analysis:
            for x_origin in rtl_analysis.xtrace.x_origins:
                fixes.append(RecommendedFix(
                    action=f"Add reset for signal '{x_origin.origin_signal}' in module",
                    file=x_origin.file,
                    module=x_origin.origin_module,
                    priority="critical",
                    code_suggestion=(
                        f"In the reset clause: {x_origin.origin_signal} <= '0;"
                    ),
                ))

            for issue in rtl_analysis.functional.issues:
                fixes.append(RecommendedFix(
                    action=issue.description,
                    file=issue.file,
                    module=issue.module,
                    priority=issue.severity,
                ))

        # Build prevention measures
        prevention = [
            PreventionMeasure(
                category="lint_rule",
                description="Enable lint rule for uninitialized sequential registers",
                implementation="Add reset checking lint rule to CI pipeline",
            ),
            PreventionMeasure(
                category="assertion",
                description="Add SVA assertions for X detection on all outputs",
                implementation="assert property (@(posedge clk) !$isunknown(result));",
            ),
            PreventionMeasure(
                category="review_checklist",
                description="Add reset verification to code review checklist",
                implementation="Verify all sequential registers have reset values",
            ),
        ]

        # Determine affected signals
        affected_signals = []
        if rtl_analysis:
            for x in rtl_analysis.xtrace.x_origins:
                affected_signals.append(x.origin_signal)
                affected_signals.extend(x.affected_outputs)

        # Build evidence chain
        evidence = list(classification.evidence)
        if rtl_analysis and rtl_analysis.xtrace.x_origins:
            for x in rtl_analysis.xtrace.x_origins:
                evidence.append(EvidenceItem(
                    source="rtl",
                    reference=f"{x.file}:{x.line_number}",
                    description=f"Signal '{x.origin_signal}' never reset in module '{x.origin_module}'",
                ))

        # Determine primary RTL file and line
        rtl_file = ""
        rtl_line = 0
        if rtl_analysis and rtl_analysis.xtrace.x_origins:
            rtl_file = rtl_analysis.xtrace.x_origins[0].file
            rtl_line = rtl_analysis.xtrace.x_origins[0].line_number

        return ErrorReport(
            classification=classification.classification,
            module=classification.component or (
                knowledge.rtl.top_module if knowledge.rtl.modules else ""
            ),
            confidence=classification.confidence,
            root_cause=classification.reason,
            category=classification.category or (
                rtl_analysis.primary_category if rtl_analysis else ""
            ),
            affected_signals=list(set(affected_signals)),
            simulation_timestamp=(
                knowledge.logs.errors[0].timestamp
                if knowledge.logs.errors else ""
            ),
            spec_reference=classification.spec_reference,
            log_reference=classification.log_reference,
            rtl_file=rtl_file,
            rtl_line=rtl_line,
            evidence=evidence,
            reasoning=classification.reasoning_chain,
            recommended_fixes=fixes,
            prevention_measures=prevention,
            severity="high" if classification.confidence >= 80 else "medium",
            tags=[
                classification.classification.lower().replace(" ", "_"),
                classification.category.lower().replace(" ", "_") if classification.category else "unclassified",
            ],
            session_id=session_id,
            timestamp=timestamp,
        )

    def _build_report_context(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        rtl_analysis: Optional[RTLAnalysis],
        report: ErrorReport,
    ) -> dict:
        """Build template context for report generation."""
        return {
            "report": report,
            "classification": classification,
            "rtl_analysis": rtl_analysis,
            "knowledge": knowledge,
            "timestamp": report.timestamp,
            "session_id": report.session_id,
            "simulation_status": knowledge.logs.summary.pass_fail,
            "simulation_time": knowledge.logs.summary.simulation_time,
            "error_count": knowledge.logs.summary.total_errors,
            "fatal_count": knowledge.logs.summary.total_fatals,
            "errors": knowledge.logs.errors[:10],
            "mismatches": knowledge.logs.scoreboard_mismatches[:10],
        }

    def _generate_markdown_report(self, context: dict) -> str:
        """Generate Markdown report."""
        report = context["report"]
        classification = context["classification"]
        rtl_analysis = context.get("rtl_analysis")

        lines = [
            f"# VeriSight Debugging Report",
            f"",
            f"**Session:** {report.session_id}",
            f"**Generated:** {report.timestamp}",
            f"**Simulation Status:** {context['simulation_status']}",
            f"**Simulation Time:** {context['simulation_time']}",
            f"",
            f"---",
            f"",
            f"## Executive Summary",
            f"",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Classification** | {report.classification} |",
            f"| **Module** | {report.module} |",
            f"| **Confidence** | {report.confidence}% |",
            f"| **Category** | {report.category} |",
            f"| **Severity** | {report.severity} |",
            f"",
            f"**Root Cause:** {report.root_cause}",
            f"",
        ]

        # Affected signals
        if report.affected_signals:
            lines.extend([
                f"**Affected Signals:** `{'`, `'.join(report.affected_signals)}`",
                f"",
            ])

        # Error Timeline
        lines.extend([
            f"## Error Timeline",
            f"",
            f"| Time | Severity | Message |",
            f"|------|----------|---------|",
        ])
        for err in context["errors"]:
            lines.append(f"| {err.timestamp} | {err.severity} | {err.message[:80]} |")
        lines.append("")

        # Mismatch Details
        if context["mismatches"]:
            lines.extend([
                f"## Scoreboard Mismatches",
                f"",
                f"| Time | Expected | Actual |",
                f"|------|----------|--------|",
            ])
            for m in context["mismatches"]:
                lines.append(f"| {m.timestamp} | {m.expected} | {m.actual} |")
            lines.append("")

        # Evidence Chain
        if report.evidence:
            lines.extend([
                f"## Evidence Chain",
                f"",
            ])
            for i, ev in enumerate(report.evidence, 1):
                lines.append(f"{i}. **[{ev.source}]** {ev.reference} — {ev.description}")
            lines.append("")

        # Reasoning Chain
        if report.reasoning:
            lines.extend([
                f"## Reasoning Chain",
                f"",
            ])
            for r in report.reasoning:
                lines.append(f"**Step {r.step}:** {r.observation}")
                lines.append(f"  → *Inference:* {r.inference}")
                if r.source:
                    lines.append(f"  → *Source:* {r.source}")
                lines.append("")

        # RTL Analysis Details
        if rtl_analysis:
            lines.extend([
                f"## RTL Analysis",
                f"",
            ])

            if rtl_analysis.xtrace.x_origins:
                lines.extend([
                    f"### X Propagation",
                    f"",
                ])
                for x in rtl_analysis.xtrace.x_origins:
                    lines.append(
                        f"- **{x.origin_signal}** in `{x.origin_module}` "
                        f"(line {x.line_number}) — Cause: {x.origin_cause}"
                    )
                lines.append("")

            if rtl_analysis.functional.issues:
                lines.extend([
                    f"### Functional Issues",
                    f"",
                ])
                for issue in rtl_analysis.functional.issues:
                    lines.append(f"- [{issue.severity}] {issue.description}")
                lines.append("")

            if rtl_analysis.lint.issues:
                lines.extend([
                    f"### Lint Issues",
                    f"",
                ])
                for issue in rtl_analysis.lint.issues:
                    lines.append(f"- [{issue.issue_type}] {issue.description}")
                lines.append("")

        # Recommended Fixes
        if report.recommended_fixes:
            lines.extend([
                f"## Recommended Fixes",
                f"",
            ])
            for i, fix in enumerate(report.recommended_fixes, 1):
                lines.append(f"{i}. **[{fix.priority}]** {fix.action}")
                if fix.code_suggestion:
                    lines.append(f"   ```systemverilog")
                    lines.append(f"   {fix.code_suggestion}")
                    lines.append(f"   ```")
            lines.append("")

        # Prevention Measures
        if report.prevention_measures:
            lines.extend([
                f"## Future Prevention",
                f"",
            ])
            for pm in report.prevention_measures:
                lines.append(f"- **[{pm.category}]** {pm.description}")
                if pm.implementation:
                    lines.append(f"  - Implementation: `{pm.implementation}`")
            lines.append("")

        # Spec References
        if report.spec_reference:
            lines.extend([
                f"## Specification References",
                f"",
                f"- {report.spec_reference}",
                f"",
            ])

        lines.extend([
            f"---",
            f"*Report generated by VeriSight v1.0.0*",
        ])

        return "\n".join(lines)

    def _generate_html_report(self, context: dict) -> str:
        """Generate styled HTML report."""
        report = context["report"]

        # Inline HTML with CSS (no external template needed)
        severity_colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#28a745",
        }
        severity_color = severity_colors.get(report.severity, "#6c757d")

        classification_colors = {
            "RTL Bug": "#dc3545",
            "TB Bug": "#fd7e14",
            "Spec Bug": "#ffc107",
            "Unknown": "#6c757d",
        }
        class_color = classification_colors.get(report.classification, "#6c757d")

        # Build error table rows
        error_rows = ""
        for err in context["errors"]:
            error_rows += f"""
                <tr>
                    <td>{err.timestamp}</td>
                    <td><span class="badge badge-error">{err.severity}</span></td>
                    <td>{err.message[:100]}</td>
                </tr>"""

        # Build evidence list
        evidence_items = ""
        for ev in report.evidence:
            evidence_items += f"""
                <div class="evidence-item">
                    <span class="evidence-source">[{ev.source}]</span>
                    <strong>{ev.reference}</strong> — {ev.description}
                </div>"""

        # Build fix list
        fix_items = ""
        for fix in report.recommended_fixes:
            fix_items += f"""
                <div class="fix-item">
                    <span class="badge badge-{fix.priority}">{fix.priority}</span>
                    {fix.action}
                    {'<pre><code>' + fix.code_suggestion + '</code></pre>' if fix.code_suggestion else ''}
                </div>"""

        # Build reasoning chain
        reasoning_items = ""
        for r in report.reasoning:
            reasoning_items += f"""
                <div class="reasoning-step">
                    <strong>Step {r.step}:</strong> {r.observation}<br>
                    <em>→ Inference: {r.inference}</em>
                    {'<br><small>Source: ' + r.source + '</small>' if r.source else ''}
                </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VeriSight Debugging Report — {report.session_id}</title>
    <style>
        :root {{
            --bg: #0d1117; --card-bg: #161b22; --border: #30363d;
            --text: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
            --error: #f85149; --warn: #d29922; --success: #3fb950;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg); color: var(--text); line-height: 1.6;
            padding: 2rem; max-width: 1200px; margin: 0 auto;
        }}
        h1 {{ color: var(--accent); margin-bottom: 0.5rem; font-size: 1.8rem; }}
        h2 {{
            color: var(--accent); margin: 2rem 0 1rem; padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }}
        h3 {{ color: var(--text); margin: 1.5rem 0 0.5rem; }}
        .meta {{ color: var(--text-muted); margin-bottom: 2rem; }}
        .summary-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem; margin: 1rem 0 2rem;
        }}
        .summary-card {{
            background: var(--card-bg); border: 1px solid var(--border);
            border-radius: 8px; padding: 1rem;
        }}
        .summary-card .label {{ color: var(--text-muted); font-size: 0.85rem; }}
        .summary-card .value {{ font-size: 1.4rem; font-weight: 700; margin-top: 0.3rem; }}
        .badge {{
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 0.8rem; font-weight: 600;
        }}
        .badge-critical {{ background: #f8514922; color: #f85149; }}
        .badge-high {{ background: #fd7e1422; color: #fd7e14; }}
        .badge-medium {{ background: #d2992222; color: #d29922; }}
        .badge-low {{ background: #3fb95022; color: #3fb950; }}
        .badge-error {{ background: #f8514922; color: #f85149; }}
        table {{
            width: 100%; border-collapse: collapse; margin: 1rem 0;
            background: var(--card-bg);
        }}
        th, td {{
            padding: 0.6rem 1rem; text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--text-muted); font-weight: 600; }}
        .evidence-item, .fix-item, .reasoning-step {{
            background: var(--card-bg); border: 1px solid var(--border);
            border-radius: 6px; padding: 0.8rem 1rem; margin: 0.5rem 0;
        }}
        .evidence-source {{
            color: var(--accent); font-weight: 600; margin-right: 0.5rem;
        }}
        pre {{
            background: #0d1117; border: 1px solid var(--border);
            padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem;
            overflow-x: auto;
        }}
        code {{ color: #79c0ff; font-family: 'JetBrains Mono', monospace; }}
        .root-cause {{
            background: var(--card-bg); border-left: 4px solid {class_color};
            padding: 1rem 1.5rem; border-radius: 0 6px 6px 0; margin: 1rem 0;
        }}
        footer {{
            margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border);
            color: var(--text-muted); font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <h1>🔍 VeriSight Debugging Report</h1>
    <div class="meta">
        Session: {report.session_id} &bull;
        Generated: {report.timestamp} &bull;
        Simulation: {context['simulation_status']} ({context['simulation_time']})
    </div>

    <div class="summary-grid">
        <div class="summary-card">
            <div class="label">Classification</div>
            <div class="value" style="color: {class_color}">{report.classification}</div>
        </div>
        <div class="summary-card">
            <div class="label">Confidence</div>
            <div class="value">{report.confidence}%</div>
        </div>
        <div class="summary-card">
            <div class="label">Module</div>
            <div class="value">{report.module or 'N/A'}</div>
        </div>
        <div class="summary-card">
            <div class="label">Category</div>
            <div class="value">{report.category or 'N/A'}</div>
        </div>
        <div class="summary-card">
            <div class="label">Severity</div>
            <div class="value"><span class="badge badge-{report.severity}">{report.severity}</span></div>
        </div>
        <div class="summary-card">
            <div class="label">Errors</div>
            <div class="value" style="color: var(--error)">{context['error_count']}</div>
        </div>
    </div>

    <div class="root-cause">
        <h3>Root Cause</h3>
        <p>{report.root_cause}</p>
        {'<p><strong>Affected Signals:</strong> <code>' + '</code>, <code>'.join(report.affected_signals) + '</code></p>' if report.affected_signals else ''}
    </div>

    <h2>Error Timeline</h2>
    <table>
        <thead><tr><th>Time</th><th>Severity</th><th>Message</th></tr></thead>
        <tbody>{error_rows}</tbody>
    </table>

    {'<h2>Evidence Chain</h2>' + evidence_items if evidence_items else ''}
    {'<h2>Reasoning</h2>' + reasoning_items if reasoning_items else ''}
    {'<h2>Recommended Fixes</h2>' + fix_items if fix_items else ''}

    <footer>Report generated by VeriSight v1.0.0</footer>
</body>
</html>"""

        return html

    def _generate_summary(self, context: dict) -> str:
        """Generate plain-text executive summary."""
        report = context["report"]
        lines = [
            "=" * 60,
            "VERISIGHT DEBUGGING SUMMARY",
            "=" * 60,
            f"Session:        {report.session_id}",
            f"Timestamp:      {report.timestamp}",
            f"Simulation:     {context['simulation_status']} ({context['simulation_time']})",
            "",
            f"Classification: {report.classification}",
            f"Confidence:     {report.confidence}%",
            f"Module:         {report.module}",
            f"Category:       {report.category}",
            f"Severity:       {report.severity}",
            "",
            f"ROOT CAUSE:",
            f"  {report.root_cause}",
            "",
        ]

        if report.affected_signals:
            lines.append(f"AFFECTED SIGNALS: {', '.join(report.affected_signals)}")
            lines.append("")

        if report.recommended_fixes:
            lines.append("RECOMMENDED FIXES:")
            for i, fix in enumerate(report.recommended_fixes, 1):
                lines.append(f"  {i}. [{fix.priority}] {fix.action}")
            lines.append("")

        lines.extend([
            "=" * 60,
            "Generated by VeriSight v1.0.0",
        ])

        return "\n".join(lines)

    def _store_session(
        self,
        report: ErrorReport,
        knowledge: UnifiedKnowledge,
        session_id: str,
    ) -> None:
        """Store the debugging session in ChromaDB for future RAG."""
        try:
            # Build problem description from log errors
            error_msgs = [e.message for e in knowledge.logs.errors[:5]]
            problem = "; ".join(error_msgs) if error_msgs else report.root_cause

            # Build affected files list
            files = knowledge.input_files.get("rtl", []) + knowledge.input_files.get("tb", [])

            self.kb.store_session(
                session_id=session_id,
                problem=problem,
                cause=report.root_cause,
                fix="; ".join(f.action for f in report.recommended_fixes[:3]),
                classification=report.classification,
                files=files[:10],
                metadata={
                    "module": report.module,
                    "category": report.category,
                    "confidence": str(report.confidence),
                    "severity": report.severity,
                },
            )
            self.logger.info(f"Session stored in RAG knowledge base: {session_id}")

        except Exception as e:
            self.logger.warning(f"Failed to store session in RAG: {e}")
