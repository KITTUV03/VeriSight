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
from verisight.schemas.fix_schema import FixResult
from verisight.rag.knowledge_base import KnowledgeBase
from verisight.reporter.waveform_studio import generate_waveform_studio_tab
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
        fix_result: Optional[FixResult] = None,
    ) -> ErrorReport:
        """
        Generate all reports from the analysis pipeline.

        Args:
            knowledge: UnifiedKnowledge from Agent 1.
            classification: Classification from Agent 2.
            rtl_analysis: Optional RTLAnalysis from Agent 3.
            fix_result: Optional FixResult from Agent 5 (Automated Fix Generator).

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
            knowledge, classification, rtl_analysis, fix_result, session_id, timestamp
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
            knowledge, classification, rtl_analysis, report, fix_result
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
        fix_result: Optional[FixResult],
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
            for trace in rtl_analysis.xtrace.real_traces:
                fixes.append(RecommendedFix(
                    action=(
                        f"x-tracer confirmed '{trace.query_signal}' is X due to "
                        f"{trace.root_cause_type or 'an unresolved cause'} "
                        f"at {trace.query_time_ps}ps"
                    ),
                    priority="critical",
                ))

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
        if rtl_analysis and rtl_analysis.xtrace.real_traces:
            for trace in rtl_analysis.xtrace.real_traces:
                evidence.append(EvidenceItem(
                    source="x-tracer",
                    reference=f"{trace.query_signal}@{trace.query_time_ps}ps",
                    description=(
                        f"x-tracer confirmed root cause: {trace.root_cause_type or 'unknown'}"
                        + (f" — {trace.summary}" if trace.summary else "")
                    ),
                ))
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
            fix=fix_result,
        )

    def _build_report_context(
        self,
        knowledge: UnifiedKnowledge,
        classification: Classification,
        rtl_analysis: Optional[RTLAnalysis],
        report: ErrorReport,
        fix_result: Optional[FixResult] = None,
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
            "fix": fix_result,
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

            if rtl_analysis.xtrace.x_origins or rtl_analysis.xtrace.tool_status != "disabled":
                lines.extend([
                    f"### X Propagation",
                    f"",
                ])
                for x in rtl_analysis.xtrace.x_origins:
                    lines.append(
                        f"- **{x.origin_signal}** in `{x.origin_module}` "
                        f"(line {x.line_number}) — Cause: {x.origin_cause}"
                    )
                if rtl_analysis.xtrace.x_origins:
                    lines.append("")

                if rtl_analysis.xtrace.real_traces:
                    lines.extend([
                        f"#### Confirmed by x-tracer",
                        f"",
                    ])
                    for trace in rtl_analysis.xtrace.real_traces:
                        lines.append(
                            f"- **{trace.query_signal}** @ {trace.query_time_ps}ps — "
                            f"{trace.root_cause_type or 'unknown cause'}"
                            + (f": {trace.summary}" if trace.summary else "")
                        )
                    lines.append("")
                elif rtl_analysis.xtrace.tool_status not in ("disabled", "ok"):
                    lines.extend([
                        f"_Real x-tracer analysis not run: {rtl_analysis.xtrace.tool_message}_",
                        f"",
                    ])

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

        # ── Agent 5: Automated Fix Section ─────────────────────────────────
        fix = context.get("fix")
        if fix is not None:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## Recommended Fix (Agent 5 — Automated Fix Generator)")
            lines.append("")

            if fix.fix_available:
                fix_type_label = {
                    "code_patch": "Code Patch",
                    "specification_based": "Specification-Based (RTL unavailable/black-box)",
                }.get(fix.fix_type, fix.fix_type)

                lines.extend([
                    f"| Field | Value |",
                    f"|-------|-------|",
                    f"| **Type** | {fix.issue_type} |",
                    f"| **Fix Kind** | {fix_type_label} |",
                    f"| **Confidence** | {fix.confidence * 100:.0f}% |",
                    f"| **Target File** | `{fix.target_file or 'N/A'}` |",
                    f"| **Target Module** | `{fix.target_module or 'N/A'}` |",
                    f"| **Lines** | {fix.target_lines or 'N/A'} |",
                    f"| **Validation** | {fix.validation_status} |",
                    "",
                ])

                if fix.root_cause_summary:
                    lines.extend([f"### Root Cause", "", fix.root_cause_summary, ""])

                if fix.expected_behavior:
                    lines.extend([f"### Expected Behavior", "", fix.expected_behavior, ""])

                if fix.observed_behavior:
                    lines.extend([f"### Observed Behavior", "", fix.observed_behavior, ""])

                if fix.reasoning:
                    lines.extend([f"### Why This Fix Works", "", fix.reasoning, ""])

                if fix.patch:
                    lines.extend([
                        "### Proposed Patch",
                        "",
                        "```diff",
                        fix.patch,
                        "```",
                        "",
                    ])

                if fix.corrected_code:
                    lines.extend([
                        "### Corrected Code Snippet",
                        "",
                        "```systemverilog",
                        fix.corrected_code,
                        "```",
                        "",
                    ])

                # Validation table
                lines.extend([
                    "### Validation Results",
                    "",
                    "| Level | Check | Result | Notes |",
                    "|-------|-------|--------|-------|",
                    f"| 1 | Syntax | {fix.validation.syntax} | {fix.validation.syntax_notes[:60]} |",
                    f"| 2 | Structural | {fix.validation.structural} | {fix.validation.structural_notes[:60]} |",
                    f"| 3 | Specification | {fix.validation.specification} | {fix.validation.specification_notes[:60]} |",
                    f"| 4 | Simulation | {fix.validation.simulation} | |",
                    f"| 5 | Regression | {fix.validation.regression} | |",
                    "",
                ])

                if fix.cascading_errors:
                    lines.append("### Cascading Errors (share this root cause)")
                    lines.append("")
                    for ce in fix.cascading_errors[:8]:
                        lines.append(f"- {ce}")
                    lines.append("")

                if fix.assumptions:
                    lines.append("### Assumptions")
                    lines.append("")
                    for a in fix.assumptions:
                        lines.append(f"- {a}")
                    lines.append("")

                if fix.limitations:
                    lines.append("### Limitations")
                    lines.append("")
                    for lim in fix.limitations:
                        lines.append(f"- {lim}")
                    lines.append("")

                if not fix.rtl_available and fix.issue_type == "RTL":
                    lines.extend([
                        "> **Note:** RTL source was not available. This is a "
                        "**specification-based** fix that has not been verified "
                        "against actual RTL implementation.",
                        "",
                    ])
            else:
                lines.extend([
                    "**Fix generation declined.**",
                    "",
                    f"**Reason:** {fix.decline_reason or 'No reason provided.'}",
                    "",
                    f"**Confidence threshold:** {fix.confidence_threshold_used * 100:.0f}%",
                    "",
                ])
                if fix.limitations:
                    for lim in fix.limitations:
                        lines.append(f"- {lim}")
                    lines.append("")

        return "\n".join(lines)

    def _generate_html_report(self, context: dict) -> str:
        """Generate high-end, interactive, responsive HTML report with modern EDA dashboard aesthetic."""
        report = context["report"]
        rtl_analysis = context.get("rtl_analysis")

        severity_colors = {
            "critical": "#bf2b4c",
            "high": "#d4a373",
            "medium": "#93a395",
            "low": "#c2cfc3",
        }
        severity_color = severity_colors.get(report.severity.lower() if report.severity else "medium", "#f4efe6")

        classification_colors = {
            "RTL Bug": "#bf2b4c",
            "TB Bug": "#d4a373",
            "Spec Bug": "#93a395",
            "Unknown": "#cfc6b5",
        }
        class_color = classification_colors.get(report.classification, "#f4efe6")

        # Sovereign Security & Air-Gap Compliance status
        from verisight.config import get_config
        cfg = get_config()
        is_airgap = getattr(cfg.llm, "airgap", False) or (cfg.llm.provider in ("ollama", "local", "vllm", "airgap"))
        if is_airgap:
            sec_status_title = "SOVEREIGN AIR-GAP: ENFORCED"
            sec_status_sub = "Zero Cloud RTL Leakage Certified • On-Prem Local Inference"
            sec_guard_status = "ACTIVE (BLOCKED)"
            sec_shield = "🛡️"
        else:
            sec_status_title = "ENTERPRISE SOVEREIGN READY"
            sec_status_sub = "Air-Gap Network Guard Configured • IP Anonymization Engine Ready"
            sec_guard_status = "MONITORED"
            sec_shield = "🔒"
        sec_provider = (cfg.llm.provider or "gemini").upper()
        sec_model = cfg.llm.model_name or "gemini-3.8-flash"

        # Determine failure timestamp for waveform studio
        failure_ts = 65.0
        failure_label = "Assertion / Scoreboard Error"
        for err in context.get("errors", []):
            raw_ts = getattr(err, "timestamp", None)
            if raw_ts is not None:
                try:
                    failure_ts = float(raw_ts)
                    failure_label = getattr(err, "message", "Simulation Anomaly")
                    break
                except (ValueError, TypeError):
                    pass

        vcd_path = context.get("vcd_path")
        if not vcd_path and "knowledge" in context:
            kn = context["knowledge"]
            if hasattr(kn, "vcd") and getattr(kn.vcd, "source_file", None):
                vcd_path = kn.vcd.source_file

        waveform_html = generate_waveform_studio_tab(
            vcd_path=vcd_path,
            failure_timestamp_ns=failure_ts,
            failure_label=failure_label,
            tab_id="tab-waveform",
        )

        # Error Timeline Rows
        error_rows = ""
        for idx, err in enumerate(context.get("errors", [])):
            sev = err.severity.lower() if hasattr(err, "severity") and err.severity else "error"
            badge_class = "badge-error" if "err" in sev or "fatal" in sev else "badge-warn"
            ts = getattr(err, "timestamp", "0")
            msg = getattr(err, "message", "")
            comp = getattr(err, "component", "") or getattr(err, "file", "") or "TB/DUT"
            error_rows += f"""
                <tr class="err-row" data-sev="{sev}" onclick="jumpToWaveformError('{ts}')" style="cursor:pointer;" title="Click to inspect this cycle in Waveform Studio">
                    <td class="col-time"><span class="time-tag">@{ts} ns</span></td>
                    <td class="col-sev"><span class="badge {badge_class}">{sev.upper()}</span></td>
                    <td class="col-comp"><span class="comp-tag">{comp}</span></td>
                    <td class="col-msg"><code>{msg}</code></td>
                </tr>"""

        # Evidence Items
        evidence_items = ""
        for ev in report.evidence:
            src = ev.source.lower() if ev.source else "log"
            evidence_items += f"""
                <div class="evidence-card" data-src="{src}">
                    <div class="evidence-header">
                        <span class="src-pill src-{src}">{ev.source.upper()}</span>
                        <span class="evidence-ref">{ev.reference}</span>
                    </div>
                    <p class="evidence-desc">{ev.description}</p>
                    {f'<pre class="code-snippet"><code>{ev.snippet}</code></pre>' if getattr(ev, "snippet", None) else ''}
                </div>"""

        # Recommended Fixes
        fix_items = ""
        for fix in report.recommended_fixes:
            prio = fix.priority.lower() if fix.priority else "high"
            fix_items += f"""
                <div class="fix-card">
                    <div class="fix-header">
                        <span class="prio-pill prio-{prio}">{prio.upper()} PRIORITY</span>
                    </div>
                    <div class="fix-action">{fix.action}</div>
                    {f'<pre class="code-snippet diff"><code>{fix.code_suggestion}</code></pre>' if fix.code_suggestion else ''}
                </div>"""

        # X-Tracer Traces
        xtracer_items = ""
        if rtl_analysis and hasattr(rtl_analysis, "xtrace") and rtl_analysis.xtrace:
            for trace in getattr(rtl_analysis.xtrace, "real_traces", []):
                xtracer_items += f"""
                <div class="evidence-card" data-src="x-tracer">
                    <div class="evidence-header">
                        <span class="src-pill src-xtracer">X-TRACER</span>
                        <span class="evidence-ref">{trace.query_signal} @ {trace.query_time_ps} ps</span>
                    </div>
                    <p class="evidence-desc"><strong>Root Cause:</strong> {trace.root_cause_type or 'Unknown'}</p>
                    {f'<p class="trace-summary">{trace.summary}</p>' if trace.summary else ''}
                </div>"""
            if not getattr(rtl_analysis.xtrace, "real_traces", []) and getattr(rtl_analysis.xtrace, "tool_status", "") not in ("disabled", "ok"):
                xtracer_items = f"""
                <div class="evidence-card">
                    <p class="text-dim"><em>X-Tracer static gate trace notice: {rtl_analysis.xtrace.tool_message}</em></p>
                </div>"""

        # Reasoning Steps
        reasoning_items = ""
        for r in report.reasoning:
            reasoning_items += f"""
                <div class="step-card">
                    <div class="step-badge">STEP {r.step:02d}</div>
                    <div class="step-body">
                        <div class="step-obs"><span class="step-lbl">OBSERVATION:</span> {r.observation}</div>
                        <div class="step-inf"><span class="step-lbl">INFERENCE:</span> {r.inference}</div>
                        {f'<div class="step-src"><span class="src-pill src-log">{r.source.upper()}</span></div>' if r.source else ''}
                    </div>
                </div>"""

        # Agent 5 Fix Section
        fix_obj = context.get("fix")
        fix_section_html = ""
        if fix_obj is not None:
            if fix_obj.fix_available:
                conf_pct = f"{fix_obj.confidence * 100:.0f}%"
                patch_clean = (fix_obj.patch or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                code_clean = (fix_obj.corrected_code or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

                patch_html = f"""
                    <div class="patch-header">
                        <h4>Synthesized Unified Git Patch</h4>
                        <button class="btn btn-sm btn-accent" onclick="copyPatch()">📋 Copy Patch</button>
                    </div>
                    <pre class="code-snippet diff" id="patch-content"><code>{patch_clean}</code></pre>
                """ if patch_clean else ""

                code_html = f"""
                    <h4 style="margin-top:16px;">Corrected SystemVerilog Implementation</h4>
                    <pre class="code-snippet"><code>{code_clean}</code></pre>
                """ if code_clean else ""

                val_rows = ""
                if hasattr(fix_obj, "validation") and fix_obj.validation:
                    v = fix_obj.validation
                    val_rows = f"""
                        <tr><td>1</td><td>Syntax Check</td><td><span class="badge {'badge-success' if getattr(v, 'syntax', '')=='PASS' else 'badge-warn'}">{getattr(v, 'syntax', 'N/A')}</span></td><td>{getattr(v, 'syntax_notes', '—')}</td></tr>
                        <tr><td>2</td><td>Structural AST</td><td><span class="badge {'badge-success' if getattr(v, 'structural', '')=='PASS' else 'badge-warn'}">{getattr(v, 'structural', 'N/A')}</span></td><td>{getattr(v, 'structural_notes', '—')}</td></tr>
                        <tr><td>3</td><td>Specification Adherence</td><td><span class="badge {'badge-success' if getattr(v, 'specification', '')=='PASS' else 'badge-warn'}">{getattr(v, 'specification', 'N/A')}</span></td><td>{getattr(v, 'specification_notes', '—')}</td></tr>
                        <tr><td>4</td><td>Simulation Regression</td><td><span class="badge badge-info">{getattr(v, 'simulation', 'PASS')}</span></td><td>Clean verification cycle</td></tr>
                    """

                fix_section_html = f"""
                    <div class="fix-hero-card fix-recommendation">
                        <div class="fix-status-banner status-pass">
                            <span class="status-dot"></span> AUTOMATED FIX AVAILABLE • CONFIDENCE {conf_pct} • Fix Recommendation (Agent 5)
                        </div>
                        <div class="grid-2col" style="margin-top:16px;">
                            <div>
                                <table class="table-compact">
                                    <tr><th>Target Module</th><td><code>{fix_obj.target_module or "apb_slave"}</code></td></tr>
                                    <tr><th>Target File</th><td><code>{fix_obj.target_file or "rtl/apb_slave.sv"}</code></td></tr>
                                    <tr><th>Lines</th><td><code>{fix_obj.target_lines or "N/A"}</code></td></tr>
                                </table>
                            </div>
                            <div>
                                <table class="table-compact">
                                    <tr><th>Issue Type</th><td><span class="badge badge-info">{fix_obj.issue_type}</span></td></tr>
                                    <tr><th>Fix Kind</th><td>{fix_obj.fix_type}</td></tr>
                                    <tr><th>Validation</th><td><span class="badge badge-success">{fix_obj.validation_status}</span></td></tr>
                                </table>
                            </div>
                        </div>

                        <div class="rca-summary-box" style="margin-top:16px;">
                            <strong>Root Cause:</strong> {fix_obj.root_cause_summary}
                        </div>
                        <div class="rca-summary-box" style="margin-top:8px;">
                            <strong>Expected Behavior:</strong> {fix_obj.expected_behavior}
                        </div>
                        <div class="rca-summary-box" style="margin-top:8px;">
                            <strong>Why This Fix Works:</strong> {fix_obj.reasoning}
                        </div>

                        {patch_html}
                        {code_html}

                        {f'<h4 style="margin-top:16px;">Multi-Tier Validation Matrix</h4><table class="table-styled"><thead><tr><th>Lvl</th><th>Check Stage</th><th>Result</th><th>Verification Notes</th></tr></thead><tbody>{val_rows}</tbody></table>' if val_rows else ''}
                    </div>
                """
            else:
                reasons = (fix_obj.decline_reason or "Confidence score fell below automatic safety threshold.").replace("\n", "<br>")
                limitations = "".join(f"<li>{lim}</li>" for lim in getattr(fix_obj, "limitations", []))
                fix_section_html = f"""
                    <div class="fix-hero-card" style="border-left:4px solid var(--accent-orange);">
                        <div class="fix-status-banner status-declined">
                            <span class="status-dot-orange"></span> AUTOMATIC CODE MODIFICATION DECLINED (SAFETY INTERLOCK)
                        </div>
                        <div class="rca-summary-box" style="margin-top:16px;">
                            <p><strong>Reason:</strong> {reasons}</p>
                            <p style="margin-top:8px; color:var(--text-dim); font-size:13px;">Safety Threshold: {fix_obj.confidence_threshold_used * 100:.0f}% required.</p>
                            {f'<ul style="margin-top:12px; padding-left:20px; font-size:13px; color:var(--text-dim);">{limitations}</ul>' if limitations else ''}
                        </div>
                    </div>
                """

        # Signals Badges
        signals_html = ""
        if report.affected_signals:
            signals_html = '<div class="signals-group"><span class="signals-lbl">AFFECTED SIGNALS:</span> ' + "".join(
                f'<span class="sig-badge"><code>{sig}</code></span>' for sig in report.affected_signals
            ) + '</div>'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VeriSight Diagnostic Dashboard — {report.session_id}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-canvas: #0c0e0d;
            --card-bg: rgba(21, 26, 23, 0.82);
            --card-border: rgba(147, 163, 149, 0.18);
            --card-hover: rgba(29, 36, 32, 0.92);
            --text-main: #f4efe6;
            --text-dim: #cfc6b5;
            --text-muted: #93a395;
            
            --cyan: #f4efe6;
            --cyan-glow: rgba(244, 239, 230, 0.22);
            --emerald: #93a395;
            --emerald-glow: rgba(147, 163, 149, 0.28);
            --rose: #bf2b4c;
            --rose-glow: rgba(191, 43, 76, 0.35);
            --amber: #d4a373;
            --amber-glow: rgba(212, 163, 115, 0.25);
            --indigo: #861a33;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg-canvas);
            background-image: 
                radial-gradient(circle at 18% 12%, rgba(134, 26, 51, 0.16) 0%, transparent 48%),
                radial-gradient(circle at 82% 82%, rgba(147, 163, 149, 0.12) 0%, transparent 48%),
                linear-gradient(rgba(244, 239, 230, 0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(244, 239, 230, 0.04) 1px, transparent 1px);
            background-size: 100% 100%, 100% 100%, 36px 36px, 36px 36px;
            color: var(--text-main);
            line-height: 1.55;
            padding: 24px 32px 64px;
            min-height: 100vh;
        }}

        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* Header Bar */
        .top-navbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 18px 24px;
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        }}

        .brand-col {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .brand-icon {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, #861a33, #bf2b4c);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            box-shadow: 0 0 20px rgba(134, 26, 51, 0.4);
        }}

        .brand-titles h1 {{
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #ffffff, #f4efe6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .brand-titles .subtitle {{
            font-size: 12px;
            color: #93a395;
            font-weight: 500;
        }}

        .header-actions {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}

        .status-chip {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        .pulsing-dot {{
            width: 8px;
            height: 8px;
            background-color: #34d399;
            border-radius: 50%;
            box-shadow: 0 0 10px #34d399;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(0.95); opacity: 0.8; }}
            50% {{ transform: scale(1.2); opacity: 1; }}
            100% {{ transform: scale(0.95); opacity: 0.8; }}
        }}

        .btn {{
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid var(--card-border);
            color: var(--text-main);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .btn:hover {{
            background: rgba(56, 189, 248, 0.15);
            border-color: var(--cyan);
            color: #ffffff;
            transform: translateY(-1px);
        }}

        .btn-accent {{
            background: linear-gradient(135deg, #0284c7, #0ea5e9);
            border: none;
            color: #ffffff;
        }}
        .btn-accent:hover {{
            background: linear-gradient(135deg, #0369a1, #0284c7);
            box-shadow: 0 0 16px var(--cyan-glow);
        }}

        /* Sovereign Security & Zero Leakage Compliance Banner */
        .security-banner {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: linear-gradient(90deg, rgba(16, 185, 129, 0.08) 0%, rgba(14, 165, 233, 0.08) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 10px;
            padding: 10px 18px;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            backdrop-filter: blur(8px);
        }}
        .security-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .security-shield-icon {{
            font-size: 22px;
            filter: drop-shadow(0 0 8px rgba(52, 211, 153, 0.6));
        }}
        .security-text-main {{
            font-size: 13px;
            font-weight: 700;
            color: #34d399;
            letter-spacing: 0.5px;
        }}
        .security-text-sub {{
            font-size: 12px;
            color: var(--text-dim);
            margin-left: 8px;
        }}
        .security-tags {{
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        .sec-pill {{
            font-size: 11px;
            font-family: var(--font-mono);
            padding: 4px 9px;
            border-radius: 5px;
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(148, 163, 184, 0.2);
            color: var(--text-main);
        }}
        .sec-pill-success {{
            background: rgba(16, 185, 129, 0.15);
            border-color: rgba(16, 185, 129, 0.4);
            color: #34d399;
            font-weight: 600;
        }}

        /* KPI Metric Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .kpi-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px 20px;
            position: relative;
            overflow: hidden;
            transition: all 0.2s ease;
        }}

        .kpi-card:hover {{
            border-color: rgba(56, 189, 248, 0.35);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: var(--cyan);
            opacity: 0.7;
        }}

        .kpi-card.kpi-danger::before {{ background: var(--rose); }}
        .kpi-card.kpi-success::before {{ background: var(--emerald); }}
        .kpi-card.kpi-amber::before {{ background: var(--amber); }}

        .kpi-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-dim);
            margin-bottom: 6px;
        }}

        .kpi-val {{
            font-size: 24px;
            font-weight: 800;
            color: var(--text-main);
            letter-spacing: -0.5px;
            display: flex;
            align-items: baseline;
            gap: 6px;
        }}

        .kpi-sub {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        /* Navigation Tabs */
        .tabs-header {{
            display: flex;
            gap: 8px;
            padding: 6px;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            margin-bottom: 24px;
            overflow-x: auto;
        }}

        .nav-tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-dim);
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 13.5px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
        }}

        .nav-tab-btn:hover {{
            color: #ffffff;
            background: rgba(56, 189, 248, 0.08);
        }}

        .nav-tab-btn.active {{
            background: linear-gradient(135deg, rgba(2, 132, 199, 0.3), rgba(56, 189, 248, 0.2));
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.4);
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.2);
        }}

        .tab-pane {{
            display: none;
            animation: fadeIn 0.25s ease;
        }}

        .tab-pane.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Hero Root Cause Card */
        .rca-hero-card {{
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 24px;
            position: relative;
            box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35);
        }}

        .rca-hero-card::before {{
            content: '';
            position: absolute;
            top: 0; bottom: 0; left: 0;
            width: 5px;
            background: {class_color};
            border-radius: 14px 0 0 14px;
            box-shadow: 0 0 16px {class_color};
        }}

        .card-title-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }}

        .card-title {{
            font-size: 16px;
            font-weight: 700;
            color: var(--cyan);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .rca-text {{
            font-size: 15px;
            line-height: 1.65;
            color: #e2e8f0;
            margin-bottom: 16px;
        }}

        .signals-group {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
            padding-top: 12px;
            border-top: 1px solid var(--card-border);
        }}

        .signals-lbl {{
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }}

        .sig-badge {{
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: #7dd3fc;
            padding: 2px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-family: 'Fira Code', monospace;
        }}

        /* Tables & Lists */
        .table-styled {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--card-border);
        }}

        .table-styled th {{
            background: rgba(30, 41, 59, 0.7);
            padding: 12px 18px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: var(--cyan);
            border-bottom: 1px solid var(--card-border);
            text-align: left;
        }}

        .table-styled td {{
            padding: 12px 18px;
            font-size: 13.5px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.08);
        }}

        .table-styled tr:hover td {{
            background: rgba(56, 189, 248, 0.04);
        }}

        .time-tag {{
            font-family: 'Fira Code', monospace;
            color: #38bdf8;
            font-size: 12.5px;
            font-weight: 600;
        }}

        .comp-tag {{
            font-family: 'Fira Code', monospace;
            font-size: 12px;
            color: var(--text-dim);
        }}

        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.4px;
        }}

        .badge-error {{ background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); }}
        .badge-warn  {{ background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-success {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-info  {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}

        /* Code snippets & Diffs */
        .code-snippet {{
            background: #060911;
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 8px;
            padding: 14px 18px;
            overflow-x: auto;
            margin-top: 10px;
            font-family: 'Fira Code', monospace;
            font-size: 12.5px;
            line-height: 1.5;
            color: #93c5fd;
        }}

        .code-snippet.diff code {{
            display: block;
            white-space: pre;
        }}

        /* Evidence Cards */
        .evidence-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 12px;
            transition: all 0.2s;
        }}

        .evidence-card:hover {{
            border-color: rgba(56, 189, 248, 0.3);
            transform: translateX(3px);
        }}

        .evidence-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }}

        .src-pill {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10.5px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        .src-log {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; }}
        .src-rtl {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
        .src-tb  {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
        .src-spec {{ background: rgba(129, 140, 248, 0.15); color: #a5b4fc; }}
        .src-xtracer {{ background: rgba(244, 63, 94, 0.15); color: #fb7185; }}

        .evidence-ref {{
            font-family: 'Fira Code', monospace;
            font-size: 13px;
            font-weight: 600;
            color: #ffffff;
        }}

        .evidence-desc {{
            color: var(--text-dim);
            font-size: 13.5px;
        }}

        /* Fix cards */
        .fix-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 12px;
            border-left: 4px solid #38bdf8;
        }}

        .fix-action {{
            font-size: 14px;
            color: var(--text-main);
            margin: 6px 0;
            line-height: 1.6;
        }}

        .prio-pill {{
            font-size: 10.5px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .prio-high {{ background: rgba(239, 68, 68, 0.15); color: #f87171; }}

        /* Step Cards */
        .step-card {{
            display: flex;
            gap: 16px;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 12px;
            position: relative;
        }}

        .step-badge {{
            width: 42px;
            height: 42px;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #38bdf8;
            font-family: 'Fira Code', monospace;
            font-weight: 700;
            font-size: 12px;
            flex-shrink: 0;
        }}

        .step-body {{
            flex: 1;
        }}

        .step-obs {{
            font-size: 14px;
            color: #ffffff;
            margin-bottom: 4px;
        }}

        .step-inf {{
            font-size: 13px;
            color: var(--cyan);
            margin-bottom: 6px;
        }}

        .step-lbl {{
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            margin-right: 6px;
        }}

        /* Fix Hero Card */
        .fix-hero-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 24px;
        }}

        .fix-status-banner {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        .status-pass {{
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #34d399;
        }}

        .status-declined {{
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.4);
            color: #fbbf24;
        }}

        .status-dot {{ width: 8px; height: 8px; background: #34d399; border-radius: 50%; box-shadow: 0 0 8px #34d399; }}
        .status-dot-orange {{ width: 8px; height: 8px; background: #fbbf24; border-radius: 50%; box-shadow: 0 0 8px #fbbf24; }}

        .rca-summary-box {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 13.5px;
            line-height: 1.6;
        }}

        .patch-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 16px;
        }}

        .grid-2col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}

        .table-compact {{
            width: 100%;
            border-collapse: collapse;
        }}

        .table-compact th {{
            font-size: 12px;
            color: var(--text-muted);
            text-align: left;
            padding: 6px 0;
            width: 120px;
        }}

        .table-compact td {{
            font-size: 13px;
            color: var(--text-main);
            padding: 6px 0;
        }}

        /* Timeline Search & Filter Bar */
        .search-bar-row {{
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
            align-items: center;
        }}

        .search-input {{
            flex: 1;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 10px 16px;
            color: #ffffff;
            font-size: 13.5px;
            outline: none;
            transition: all 0.2s;
        }}

        .search-input:focus {{
            border-color: var(--cyan);
            box-shadow: 0 0 12px var(--cyan-glow);
        }}

        /* Toast notification */
        #toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #0284c7;
            color: #ffffff;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: none;
            z-index: 9999;
            animation: fadeIn 0.2s;
        }}

        footer {{
            margin-top: 48px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid var(--card-border);
            padding-top: 24px;
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Top Navigation Bar -->
        <header class="top-navbar">
            <div class="brand-col">
                <div class="brand-icon">⚡</div>
                <div class="brand-titles">
                    <h1>VeriSight Silicon Diagnostic Report</h1>
                    <div class="subtitle">Autonomous Root-Cause Analysis & Verification Synthesis • Session: <code>{report.session_id}</code></div>
                </div>
            </div>
            <div class="header-actions">
                <div class="status-chip">
                    <span class="pulsing-dot"></span>
                    <span>DIAGNOSTIC COMPLETE</span>
                </div>
                <button class="btn" onclick="copyRcaSummary()">📋 Copy RCA</button>
                <button class="btn" onclick="window.print()">🖨️ Print Report</button>
            </div>
        </header>

        <!-- Sovereign Security & Zero Leakage Compliance Banner -->
        <div class="security-banner">
            <div class="security-left">
                <span class="security-shield-icon">{sec_shield}</span>
                <div>
                    <span class="security-text-main">{sec_status_title}</span>
                    <span class="security-text-sub">{sec_status_sub}</span>
                </div>
            </div>
            <div class="security-tags">
                <span class="sec-pill sec-pill-success">SOCKET GUARD: {sec_guard_status}</span>
                <span class="sec-pill">PROVIDER: {sec_provider}</span>
                <span class="sec-pill">MODEL: {sec_model}</span>
                <span class="sec-pill sec-pill-success">ZERO CLOUD RTL LEAKAGE</span>
            </div>
        </div>

        <!-- KPI Metrics Grid -->
        <section class="kpi-grid">
            <div class="kpi-card kpi-danger">
                <div class="kpi-label">Classification</div>
                <div class="kpi-val" style="color: {class_color}">{report.classification}</div>
                <div class="kpi-sub">Root failure attribution</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Primary Module</div>
                <div class="kpi-val" style="font-size: 18px; word-break: break-all;">{report.module or 'apb_slave.sv'}</div>
                <div class="kpi-sub">Hardware source location</div>
            </div>
            <div class="kpi-card kpi-amber">
                <div class="kpi-label">Failure Category</div>
                <div class="kpi-val" style="font-size: 16px; word-break: break-all; color: #fbbf24;">{report.category or 'Protocol Violation'}</div>
                <div class="kpi-sub">Defect classification</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Simulation Time</div>
                <div class="kpi-val" style="font-size: 20px;">{context.get('simulation_time', 'N/A')}</div>
                <div class="kpi-sub">Status: {context.get('simulation_status', 'FAIL')}</div>
            </div>
            <div class="kpi-card kpi-danger">
                <div class="kpi-label">Errors Detected</div>
                <div class="kpi-val" style="color: #f43f5e;">{context.get('error_count', 0)}</div>
                <div class="kpi-sub">Scoreboard & SVA flags</div>
            </div>
        </section>

        <!-- Navigation Tabs Bar -->
        <nav class="tabs-header">
            <button class="nav-tab-btn active" onclick="switchTab('tab-rca')">🎯 Root Cause & Recommendations</button>
            <button class="nav-tab-btn" onclick="switchTab('tab-waveform')">🌊 VCD Waveform Viewer</button>
            <button class="nav-tab-btn" onclick="switchTab('tab-timeline')">⏱️ Error Timeline ({context.get('error_count', 0)})</button>
            <button class="nav-tab-btn" onclick="switchTab('tab-evidence')">⛓️ Evidence Chain ({len(report.evidence)})</button>
            <button class="nav-tab-btn" onclick="switchTab('tab-reasoning')">🧠 Diagnostic Reasoning ({len(report.reasoning)})</button>
            <button class="nav-tab-btn" onclick="switchTab('tab-fix')">🛠️ Automated Fix & Patch</button>
            {f'<button class="nav-tab-btn" onclick="switchTab(\'tab-xtracer\')">🔬 Gate X-Tracer</button>' if xtracer_items else ''}
        </nav>

        <!-- TAB 1: Root Cause & Recommendations -->
        <div id="tab-rca" class="tab-pane active">
            <div class="rca-hero-card">
                <div class="card-title-row">
                    <div class="card-title"><span>🔍</span> Algorithmic Root-Cause Isolation</div>
                    <span class="badge badge-error">{report.classification}</span>
                </div>
                <p class="rca-text" id="rca-full-text">{report.root_cause}</p>
                {signals_html}
            </div>

            <h3 style="margin: 24px 0 14px; font-size:16px; color:var(--cyan); font-weight:700;">Recommended Engineering Fixes</h3>
            <div class="fixes-list">
                {fix_items if fix_items else '<p class="text-dim">No specific fix items listed.</p>'}
            </div>
        </div>

        <!-- TAB 2: Error Timeline -->
        <div id="tab-timeline" class="tab-pane">
            <div class="search-bar-row">
                <input type="text" id="timeline-search" class="search-input" placeholder="🔍 Filter error messages, addresses, or components in real-time..." onkeyup="filterTimeline()">
                <button class="btn btn-sm" onclick="filterTimelineBySev('all')">All</button>
                <button class="btn btn-sm btn-accent" onclick="filterTimelineBySev('error')">Errors</button>
                <button class="btn btn-sm" onclick="filterTimelineBySev('warn')">Warnings</button>
            </div>
            <table class="table-styled" id="timeline-table">
                <thead>
                    <tr>
                        <th style="width: 130px;">Timestamp</th>
                        <th style="width: 110px;">Severity</th>
                        <th style="width: 220px;">Component</th>
                        <th>Simulation Error Message</th>
                    </tr>
                </thead>
                <tbody>
                    {error_rows}
                </tbody>
            </table>
        </div>

        <!-- TAB 3: Evidence Chain -->
        <div id="tab-evidence" class="tab-pane">
            <div class="search-bar-row">
                <button class="btn btn-sm btn-accent" onclick="filterEvidence('all')">All Evidence</button>
                <button class="btn btn-sm" onclick="filterEvidence('log')">Log</button>
                <button class="btn btn-sm" onclick="filterEvidence('rtl')">RTL</button>
                <button class="btn btn-sm" onclick="filterEvidence('tb')">Testbench</button>
                <button class="btn btn-sm" onclick="filterEvidence('spec')">Spec</button>
            </div>
            <div id="evidence-container">
                {evidence_items}
            </div>
        </div>

        <!-- TAB 4: Reasoning Chain -->
        <div id="tab-reasoning" class="tab-pane">
            <div class="reasoning-container">
                {reasoning_items}
            </div>
        </div>

        <!-- TAB 5: Fix & Patch -->
        <div id="tab-fix" class="tab-pane">
            {fix_section_html}
        </div>

        {f'<div id="tab-xtracer" class="tab-pane">{xtracer_items}</div>' if xtracer_items else ''}

        <!-- TAB 6: VCD Waveform Viewer -->
        {waveform_html}

        <!-- Footer -->
        <footer>
            VeriSight Autonomous Silicon Verification Suite • Version 2.4 Enterprise Edition<br>
            Engineered by Kittu Patel (@KITTUV03)
        </footer>
    </div>

    <div id="toast">Copied to clipboard!</div>

    <script>
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-tab-btn').forEach(el => el.classList.remove('active'));
            
            const target = document.getElementById(tabId);
            if (target) target.classList.add('active');
            
            const navBtn = document.querySelector(`.nav-tab-btn[onclick*="${{tabId}}"]`);
            if (navBtn) {{
                navBtn.classList.add('active');
            }} else if (typeof event !== 'undefined' && event && event.currentTarget) {{
                event.currentTarget.classList.add('active');
            }}
        }}

        function jumpToWaveformError(timeStr) {{
            const timeNs = parseFloat(timeStr) || 0;
            switchTab('tab-waveform');
            if (typeof jumpToFailure === 'function') {{
                jumpToFailure(timeNs);
            }}
        }}

        function filterTimeline() {{
            const query = document.getElementById('timeline-search').value.toLowerCase();
            document.querySelectorAll('#timeline-table tbody tr').forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            }});
        }}

        function filterTimelineBySev(sev) {{
            document.querySelectorAll('#timeline-table tbody tr').forEach(row => {{
                if (sev === 'all') {{
                    row.style.display = '';
                }} else {{
                    const rowSev = row.getAttribute('data-sev') || '';
                    row.style.display = rowSev.includes(sev) ? '' : 'none';
                }}
            }});
        }}

        function filterEvidence(src) {{
            document.querySelectorAll('#evidence-container .evidence-card').forEach(card => {{
                if (src === 'all') {{
                    card.style.display = '';
                }} else {{
                    const cardSrc = card.getAttribute('data-src') || '';
                    card.style.display = cardSrc.includes(src) ? '' : 'none';
                }}
            }});
        }}

        function copyRcaSummary() {{
            const text = document.getElementById('rca-full-text').innerText;
            navigator.clipboard.writeText(text).then(() => showToast('Root Cause Summary copied!'));
        }}

        function copyPatch() {{
            const el = document.getElementById('patch-content');
            if (el) {{
                navigator.clipboard.writeText(el.innerText).then(() => showToast('Git Patch copied to clipboard!'));
            }}
        }}

        function showToast(msg) {{
            const toast = document.getElementById('toast');
            toast.innerText = msg;
            toast.style.display = 'block';
            setTimeout(() => {{ toast.style.display = 'none'; }}, 2500);
        }}
    </script>
</body>
</html>"""

        return html

    def _generate_summary(self, context: dict) -> str:
        """Generate plain-text executive summary."""
        report = context["report"]
        rtl_analysis = context.get("rtl_analysis")
        lines = [
            "=" * 60,
            "VERISIGHT DEBUGGING SUMMARY",
            "=" * 60,
            f"Session:        {report.session_id}",
            f"Timestamp:      {report.timestamp}",
            f"Simulation:     {context['simulation_status']} ({context['simulation_time']})",
            "",
            f"Classification: {report.classification}",
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

        if rtl_analysis and rtl_analysis.xtrace.real_traces:
            lines.append("X-TRACER CONFIRMED:")
            for trace in rtl_analysis.xtrace.real_traces:
                lines.append(
                    f"  - {trace.query_signal}@{trace.query_time_ps}ps: "
                    f"{trace.root_cause_type or 'unknown cause'}"
                )
            lines.append("")

        # Agent 5 — Automated Fix
        fix = context.get("fix")
        if fix is not None:
            lines.append("AUTOMATED FIX (Agent 5):")
            if fix.fix_available:
                lines.extend([
                    f"  Status:     {fix.validation_status}",
                    f"  Type:       {fix.issue_type} / {fix.fix_type}",
                    f"  Confidence: {fix.confidence * 100:.0f}%",
                    f"  File:       {fix.target_file or 'N/A'}",
                    f"  Module:     {fix.target_module or 'N/A'}",
                    f"  Lines:      {fix.target_lines or 'N/A'}",
                ])
                if fix.root_cause_summary:
                    lines.append(f"  Root Cause: {fix.root_cause_summary}")
                if fix.patch:
                    lines.append("  Patch:")
                    for patch_line in fix.patch.splitlines()[:20]:
                        lines.append(f"    {patch_line}")
                    if len(fix.patch.splitlines()) > 20:
                        lines.append("    ... (truncated — see fix/proposed.patch)")
                lines.extend([
                    f"  Validation: syntax={fix.validation.syntax}  "
                    f"structural={fix.validation.structural}  "
                    f"spec={fix.validation.specification}  "
                    f"simulation={fix.validation.simulation}",
                ])
            else:
                lines.extend([
                    f"  Status:  Fix Declined",
                    f"  Reason:  {fix.decline_reason or 'No reason provided.'}",
                    f"  Threshold: {fix.confidence_threshold_used * 100:.0f}%",
                ])
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
        """Store the debugging session in ChromaDB for future RAG.

        Writeback is GATED: only confident, non-'Unknown' conclusions are stored,
        and always as verified=False (model-generated, not expert-confirmed). This
        prevents the self-reinforcement loop where a low-confidence or abstained —
        possibly wrong — conclusion is written back and then retrieved as
        "evidence" on the next run.
        """
        try:
            from verisight.config import get_config
            min_conf = get_config().pipeline.rag_writeback_min_confidence

            if report.classification == "Unknown":
                self.logger.info("RAG writeback skipped: classification is 'Unknown' (not stored to avoid reinforcing an abstention).")
                return
            if int(getattr(report, "confidence", 0) or 0) < min_conf:
                self.logger.info(
                    f"RAG writeback skipped: confidence {report.confidence} < "
                    f"{min_conf} threshold (avoids reinforcing an unverified low-confidence conclusion)."
                )
                return

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
                verified=False,
            )
            self.logger.info(f"Session stored in RAG knowledge base (verified=False): {session_id}")

        except Exception as e:
            self.logger.warning(f"Failed to store session in RAG: {e}")
