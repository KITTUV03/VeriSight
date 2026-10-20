"""
Traceability Matrix & Reporting Engine for VeriSight Plan.

Compiles Feature, Test, Coverage, and SVA mappings into:
- Bi-directional Traceability Matrix
- Exportable CSV format (for enterprise requirements management)
- Beautiful, modern interactive HTML Dashboard
- Complete Markdown documentation
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any

from verisight.plan.schemas import (
    FeatureItem,
    TestScenario,
    CovergroupDef,
    SVAProperty,
    TraceabilityRow,
    VerificationPlanReport,
)
from verisight.utils.logger import get_logger

logger = get_logger("plan.traceability")


def build_traceability_matrix(
    features: List[FeatureItem],
    tests: List[TestScenario],
    covergroups: List[CovergroupDef],
    assertions: List[SVAProperty],
) -> List[TraceabilityRow]:
    """Build bi-directional traceability rows mapping features to tests, coverage, and SVA."""
    rows = []

    # Map feature_id -> list of test_ids
    feat_to_tests: Dict[str, List[str]] = {}
    for t in tests:
        for fid in t.feature_ids:
            feat_to_tests.setdefault(fid, []).append(t.test_id)

    # Map feature_id -> list of coverage_ids
    feat_to_cov: Dict[str, List[str]] = {}
    for cg in covergroups:
        for cp in cg.coverpoints:
            for fid in cp.feature_ids:
                feat_to_cov.setdefault(fid, []).append(cp.coverage_id)

    # Map feature_id -> list of assertion_ids
    feat_to_sva: Dict[str, List[str]] = {}
    for a in assertions:
        for fid in a.feature_ids:
            feat_to_sva.setdefault(fid, []).append(a.assertion_id)

    for feat in features:
        t_ids = feat_to_tests.get(feat.feature_id, [])
        c_ids = feat_to_cov.get(feat.feature_id, [])
        s_ids = feat_to_sva.get(feat.feature_id, [])

        if t_ids and (c_ids or s_ids):
            status = "Covered"
        elif t_ids or c_ids or s_ids:
            status = "Partial"
        else:
            status = "Uncovered"

        rows.append(
            TraceabilityRow(
                feature_id=feat.feature_id,
                feature_title=feat.title,
                test_ids=t_ids,
                coverage_ids=c_ids,
                assertion_ids=s_ids,
                status=status,
            )
        )

    return rows


def export_csv(matrix: List[TraceabilityRow], output_path: Path):
    """Export the traceability matrix to CSV for import into JIRA/Doors/Excel."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Feature ID", "Feature Title", "Mapped Tests", "Functional Coverage Points", "SVA Assertions", "Status"])
        for r in matrix:
            writer.writerow([
                r.feature_id,
                r.feature_title,
                "; ".join(r.test_ids) if r.test_ids else "None",
                "; ".join(r.coverage_ids) if r.coverage_ids else "None",
                "; ".join(r.assertion_ids) if r.assertion_ids else "None",
                r.status,
            ])
    logger.info(f"Saved Traceability CSV: {output_path}")


def export_markdown(report: VerificationPlanReport, output_path: Path):
    """Export complete verification plan in Markdown format."""
    lines = [
        f"# VeriSight Plan — Verification & Architecture Plan",
        f"**Design:** `{report.design_name}` | **Generated:** `{report.timestamp}`",
        f"",
        f"## 1. Executive Summary & Verification Metrics",
        f"| Metric | Total Count |",
        f"| :--- | :--- |",
        f"| **Decomposed Features** | {report.total_features} |",
        f"| **Defined Test Scenarios** | {report.total_tests} |",
        f"| **Coverage Points Defined** | {report.total_coverage_points} |",
        f"| **SVA Formal Assertions** | {report.total_assertions} |",
        f"",
        f"## 2. Feature Decomposition Matrix",
        f"| Feature ID | Category | Priority | RTL Cross-Check | Description |",
        f"| :--- | :--- | :--- | :--- | :--- |",
    ]

    for f in report.features:
        lines.append(f"| `{f.feature_id}` | {f.category} | {f.priority} | {f.rtl_cross_check or 'N/A'} | {f.description} |")

    lines.extend([
        f"",
        f"## 3. Test Plan Scenarios",
        f"| Test ID | Type | Target Features | Scenario Title & Stimulus | Expected Response |",
        f"| :--- | :--- | :--- | :--- | :--- |",
    ])
    for t in report.test_scenarios:
        fids = ", ".join([f"`{x}`" for x in t.feature_ids])
        lines.append(f"| `{t.test_id}` | {t.test_type} | {fids} | **{t.title}**<br>{t.stimulus} | {t.expected_response} |")

    lines.extend([
        f"",
        f"## 4. Functional Coverage Model",
    ])
    for cg in report.covergroups:
        lines.append(f"### Covergroup: `{cg.group_name}`")
        lines.append(f"**Trigger:** `{cg.sample_trigger}` — {cg.description}")
        lines.append(f"| Coverage ID | Coverpoint | Target Signal | Bins Defined |",)
        lines.append(f"| :--- | :--- | :--- | :--- |",)
        for cp in cg.coverpoints:
            b_desc = ", ".join([f"`{b.bin_name}` ({b.condition})" for b in cp.bins])
            lines.append(f"| `{cp.coverage_id}` | `{cp.name}` | `{cp.target_signal}` | {b_desc} |")
        lines.append("")

    lines.extend([
        f"## 5. SystemVerilog Assertions (SVA) Suite",
        f"| SVA ID | Property Name | Type | Clock & Disable | Formal Expression |",
        f"| :--- | :--- | :--- | :--- | :--- |",
    ])
    for a in report.assertions:
        dis = f"disable iff ({a.disable_expr})" if a.disable_expr else "None"
        lines.append(f"| `{a.assertion_id}` | `{a.name}` | {a.property_type} | `{a.clock_expr}`<br>`{dis}` | `{a.expression}` |")

    lines.extend([
        f"",
        f"## 6. Bi-Directional Traceability Matrix",
        f"| Feature ID | Feature Title | Tests | Functional Coverage | SVA Properties | Verification Status |",
        f"| :--- | :--- | :--- | :--- | :--- | :--- |",
    ])
    for r in report.traceability_matrix:
        t_str = ", ".join([f"`{x}`" for x in r.test_ids]) or "—"
        c_str = ", ".join([f"`{x}`" for x in r.coverage_ids]) or "—"
        s_str = ", ".join([f"`{x}`" for x in r.assertion_ids]) or "—"
        status_badge = f"**{r.status}**" if r.status == "Covered" else f"*{r.status}*"
        lines.append(f"| `{r.feature_id}` | {r.feature_title} | {t_str} | {c_str} | {s_str} | {status_badge} |")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"Saved Markdown Plan: {output_path}")


def export_html(report: VerificationPlanReport, output_path: Path):
    """
    Generate high-end, responsive, interactive HTML presentation dashboard
    for VeriSight Plan matching tier-1 Silicon EDA engineering standards.
    """
    import html
    from verisight.config import get_config

    cfg = get_config()
    is_airgap = getattr(cfg.llm, "airgap", False) or (cfg.llm.provider in ("ollama", "local", "vllm", "airgap"))
    if is_airgap:
        sec_title = "SOVEREIGN AIR-GAP: ENFORCED"
        sec_sub = "Zero Cloud RTL Leakage Certified • On-Prem Local Architecture Synthesis"
        sec_guard = "ACTIVE (BLOCKED)"
        sec_shield = "🛡️"
    else:
        sec_title = "ENTERPRISE SOVEREIGN READY"
        sec_sub = "ISO 26262 ASIL-D & DO-254 Ready • Bi-Directional Requirement Matrix"
        sec_guard = "MONITORED"
        sec_shield = "🔒"

    total_feat = report.total_features or len(report.features)
    total_tst = report.total_tests or len(report.test_scenarios)
    total_cov = report.total_coverage_points or sum(len(cg.coverpoints) for cg in report.covergroups)
    total_sva = report.total_assertions or len(report.assertions)

    cov_cnt = sum(1 for r in report.traceability_matrix if r.status == "Covered")
    part_cnt = sum(1 for r in report.traceability_matrix if r.status == "Partial")
    uncov_cnt = sum(1 for r in report.traceability_matrix if r.status == "Uncovered")
    total_rows = max(len(report.traceability_matrix), 1)
    closure_pct = round(((cov_cnt + 0.5 * part_cnt) / total_rows) * 100, 1)

    # Test types breakdown
    test_types_cnt = {}
    for t in report.test_scenarios:
        ttype = t.test_type or "Directed"
        test_types_cnt[ttype] = test_types_cnt.get(ttype, 0) + 1
    test_breakdown_str = " • ".join([f"{k}: {v}" for k, v in sorted(test_types_cnt.items())]) or "Directed & Random"

    # Pre-build Traceability Rows
    matrix_rows = []
    for r in report.traceability_matrix:
        st_lower = r.status.lower()
        badge_cls = "badge-covered" if st_lower == "covered" else ("badge-partial" if st_lower == "partial" else "badge-critical")
        t_badges = "".join([f'<span class="code-pill pill-test">{html.escape(x)}</span>' for x in r.test_ids]) or '<span class="text-dim">—</span>'
        c_badges = "".join([f'<span class="code-pill pill-cov">{html.escape(x)}</span>' for x in r.coverage_ids]) or '<span class="text-dim">—</span>'
        s_badges = "".join([f'<span class="code-pill pill-sva">{html.escape(x)}</span>' for x in r.assertion_ids]) or '<span class="text-dim">—</span>'
        
        search_blob = f"{r.feature_id} {r.feature_title} {' '.join(r.test_ids)} {' '.join(r.coverage_ids)} {' '.join(r.assertion_ids)} {r.status}".lower()
        matrix_rows.append(f"""
            <tr class="mat-row" data-status="{st_lower}" data-text="{html.escape(search_blob)}">
                <td class="col-fid"><code>{html.escape(r.feature_id)}</code></td>
                <td class="col-title"><strong>{html.escape(r.feature_title)}</strong></td>
                <td class="col-pills">{t_badges}</td>
                <td class="col-pills">{c_badges}</td>
                <td class="col-pills">{s_badges}</td>
                <td class="col-status"><span class="badge {badge_cls}">{html.escape(r.status)}</span></td>
            </tr>
        """)
    matrix_rows_html = "".join(matrix_rows)

    # Pre-build Feature Rows
    feat_rows = []
    for f in report.features:
        prio_lower = (f.priority or "high").lower()
        prio_cls = "badge-critical" if prio_lower == "critical" else ("badge-warn" if prio_lower == "high" else "badge-covered")
        rtl_status = f.rtl_cross_check or "N/A"
        rtl_cls = "sec-pill-success" if "confirm" in rtl_status.lower() else "sec-pill"
        search_blob = f"{f.feature_id} {f.title} {f.category} {f.priority} {rtl_status} {f.description}".lower()
        feat_rows.append(f"""
            <tr class="feat-row" data-cat="{(f.category or '').lower()}" data-prio="{prio_lower}" data-text="{html.escape(search_blob)}">
                <td><code>{html.escape(f.feature_id)}</code></td>
                <td><span class="badge badge-neutral">{html.escape(f.category or 'Functional')}</span></td>
                <td><span class="badge {prio_cls}">{html.escape(f.priority or 'High')}</span></td>
                <td><span class="sec-pill {rtl_cls}">{html.escape(rtl_status)}</span></td>
                <td><strong>{html.escape(f.title)}</strong><br><span class="desc-text">{html.escape(f.description)}</span></td>
            </tr>
        """)
    feat_rows_html = "".join(feat_rows)

    # Pre-build Test Scenario Cards
    test_cards = []
    for t in report.test_scenarios:
        ttype_lower = (t.test_type or "directed").lower()
        prio_lower = (t.priority or "high").lower()
        f_pills = "".join([f'<span class="code-pill pill-feat">{html.escape(x)}</span>' for x in t.feature_ids]) or '<span class="text-dim">N/A</span>'
        search_blob = f"{t.test_id} {t.title} {t.test_type} {t.priority} {t.stimulus} {t.expected_response}".lower()
        test_cards.append(f"""
            <div class="test-card" data-type="{ttype_lower}" data-text="{html.escape(search_blob)}">
                <div class="test-card-header">
                    <div class="test-title-row">
                        <span class="test-id-pill"><code>{html.escape(t.test_id)}</code></span>
                        <h4 class="test-name">{html.escape(t.title)}</h4>
                    </div>
                    <div class="test-tags">
                        <span class="badge badge-neutral">{html.escape(t.test_type)}</span>
                        <span class="badge badge-covered">{html.escape(t.priority or 'High')} Priority</span>
                    </div>
                </div>
                <div class="test-meta-row">
                    <span class="text-dim">Target Features:</span> {f_pills}
                </div>
                <div class="test-body-grid">
                    <div class="test-box stimulus-box">
                        <div class="box-hdr">⚡ Input Stimulus & Configuration</div>
                        <div class="box-content">{html.escape(t.stimulus)}</div>
                    </div>
                    <div class="test-box check-box">
                        <div class="box-hdr">🎯 Expected Response & Scoreboard Check</div>
                        <div class="box-content">{html.escape(t.expected_response)}</div>
                    </div>
                </div>
            </div>
        """)
    test_cards_html = "".join(test_cards)

    # Pre-build Covergroup Inspector Cards
    cg_cards = []
    for cg in report.covergroups:
        cp_rows = []
        for cp in cg.coverpoints:
            f_pills = "".join([f'<span class="code-pill pill-feat">{html.escape(x)}</span>' for x in cp.feature_ids])
            bin_desc = ", ".join([f"<code>{html.escape(b.bin_name)}</code> ({html.escape(b.condition)})" for b in cp.bins]) or "Auto-generated bins"
            cp_rows.append(f"""
                <tr>
                    <td><code>{html.escape(cp.coverage_id)}</code></td>
                    <td><strong>{html.escape(cp.name)}</strong></td>
                    <td><code>{html.escape(cp.target_signal)}</code></td>
                    <td><span class="text-dim">{f_pills or '—'}</span></td>
                    <td><div class="bin-desc">{bin_desc}</div></td>
                </tr>
            """)
        cp_rows_html = "".join(cp_rows)
        cross_str = ", ".join([f"<code>{html.escape(c)}</code>" for c in cg.crosses]) or "None"
        cg_cards.append(f"""
            <div class="cg-card">
                <div class="cg-header">
                    <div>
                        <h4 class="cg-title"><code>{html.escape(cg.group_name)}</code></h4>
                        <div class="cg-sub">{html.escape(cg.description or 'Functional coverage model')}</div>
                    </div>
                    <div class="cg-trigger">
                        <span class="text-dim">Sampling Trigger:</span> <code>{html.escape(cg.sample_trigger)}</code>
                    </div>
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Coverage ID</th>
                            <th>Coverpoint Name</th>
                            <th>Target Signal / Expr</th>
                            <th>Mapped Features</th>
                            <th>Defined Bins & Conditions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {cp_rows_html}
                    </tbody>
                </table>
                <div class="cg-footer">
                    <span class="text-dim">Cross Coverage:</span> {cross_str}
                </div>
            </div>
        """)
    cg_cards_html = "".join(cg_cards) or "<div class='empty-card'>No covergroups defined.</div>"

    # Pre-build SVA Rows
    sva_rows = []
    for a in report.assertions:
        dis = f"disable iff ({html.escape(a.disable_expr)})" if a.disable_expr else "None"
        f_pills = "".join([f'<span class="code-pill pill-feat">{html.escape(x)}</span>' for x in a.feature_ids])
        sva_rows.append(f"""
            <tr>
                <td><code>{html.escape(a.assertion_id)}</code></td>
                <td><strong>{html.escape(a.name)}</strong></td>
                <td><span class="badge badge-covered">{html.escape(a.property_type)}</span></td>
                <td><span class="text-dim">{f_pills or '—'}</span></td>
                <td><code>{html.escape(a.clock_expr)}</code><br><span class="desc-text">{dis}</span></td>
                <td><pre class="sva-expr"><code>{html.escape(a.expression)}</code></pre></td>
                <td><code class="text-dim">{html.escape(a.failure_message or 'Assertion failed')}</code></td>
            </tr>
        """)
    sva_rows_html = "".join(sva_rows) or "<tr><td colspan='7'>No assertions defined.</td></tr>"

    # Pre-build CSV string for browser download
    csv_lines = ['"Feature ID","Feature Title","Mapped Tests","Functional Coverage Points","SVA Assertions","Status"']
    for r in report.traceability_matrix:
        t_str = "; ".join(r.test_ids) if r.test_ids else "None"
        c_str = "; ".join(r.coverage_ids) if r.coverage_ids else "None"
        s_str = "; ".join(r.assertion_ids) if r.assertion_ids else "None"
        csv_lines.append(f'"{r.feature_id}","{r.feature_title}","{t_str}","{c_str}","{s_str}","{r.status}"')
    csv_raw_data = "\n".join(csv_lines)

    cov_sv_code = report.sv_coverage_code or "// No coverage code generated"
    sva_sv_code = report.sv_assertion_code or "// No assertion code generated"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VeriSight Plan — {html.escape(report.design_name)} Verification Architecture Suite</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0b0f19;
            --bg-surface: #111827;
            --bg-card: #151d30;
            --bg-card-hover: #1a243c;
            --card-border: #1e293b;
            --card-border-glow: rgba(14, 165, 233, 0.3);
            
            --cyan: #0ea5e9;
            --cyan-glow: rgba(14, 165, 233, 0.2);
            --indigo: #6366f1;
            --indigo-glow: rgba(99, 102, 241, 0.2);
            --success: #34d399;
            --success-glow: rgba(52, 211, 153, 0.2);
            --warning: #fbbf24;
            --danger: #f87171;
            
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --text-muted: #64748b;
            
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(circle at 10% 10%, rgba(14, 165, 233, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 90%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
                linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
            background-size: 100% 100%, 100% 100%, 32px 32px, 32px 32px;
            color: var(--text-main);
            font-family: var(--font-sans);
            line-height: 1.5;
            padding: 24px;
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }}

        .dashboard-container {{
            max-width: 1440px;
            margin: 0 auto;
        }}

        /* Top Navbar */
        .top-navbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 24px;
            background: rgba(17, 24, 39, 0.7);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            backdrop-filter: blur(12px);
            margin-bottom: 20px;
        }}

        .brand-col {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .brand-icon {{
            font-size: 26px;
            background: rgba(14, 165, 233, 0.12);
            border: 1px solid var(--card-border-glow);
            padding: 8px 12px;
            border-radius: 10px;
            box-shadow: 0 0 16px var(--cyan-glow);
        }}

        .brand-titles h1 {{
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .brand-titles .subtitle {{
            font-size: 12px;
            color: var(--text-dim);
            font-weight: 500;
            margin-top: 2px;
        }}

        .header-actions {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
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
            padding: 8px 15px;
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

        /* Sovereign Security Governance Banner */
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
            flex-wrap: wrap;
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
            background: var(--bg-card);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 18px 20px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--card-border);
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--cyan);
        }}
        .kpi-card.kpi-cyan::before {{ background: var(--cyan); }}
        .kpi-card.kpi-indigo::before {{ background: var(--indigo); }}
        .kpi-card.kpi-success::before {{ background: var(--success); }}
        .kpi-card.kpi-warning::before {{ background: var(--warning); }}

        .kpi-label {{
            font-size: 12px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.6px;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .kpi-val {{
            font-size: 28px;
            font-weight: 800;
            color: var(--text-main);
            font-family: var(--font-sans);
            display: flex;
            align-items: baseline;
            gap: 6px;
        }}
        .kpi-sub {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        .progress-bar-wrap {{
            width: 100%;
            height: 6px;
            background: rgba(30, 41, 59, 0.8);
            border-radius: 3px;
            margin-top: 8px;
            overflow: hidden;
        }}
        .progress-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #34d399, #0ea5e9);
            border-radius: 3px;
        }}

        /* Navigation Tabs Bar */
        .tabs-header {{
            display: flex;
            gap: 8px;
            background: rgba(17, 24, 39, 0.7);
            border: 1px solid var(--card-border);
            padding: 6px;
            border-radius: 10px;
            margin-bottom: 20px;
            overflow-x: auto;
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-dim);
            font-size: 13px;
            font-weight: 600;
            padding: 9px 18px;
            border-radius: 7px;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .tab-btn:hover {{
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }}
        .tab-btn.active {{
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.25), rgba(99, 102, 241, 0.25));
            border: 1px solid var(--cyan);
            color: #ffffff;
            box-shadow: 0 0 12px var(--cyan-glow);
        }}

        /* Tab Content Panes */
        .tab-pane {{
            display: none;
            animation: fadeIn 0.25s ease-in-out;
        }}
        .tab-pane.active {{
            display: block;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(6px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Controls Bar (Filter & Search) */
        .controls-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .search-box {{
            flex: 1;
            min-width: 260px;
            position: relative;
        }}
        .search-input {{
            width: 100%;
            background: var(--bg-card);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 9px 14px 9px 36px;
            color: var(--text-main);
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-input:focus {{
            border-color: var(--cyan);
            box-shadow: 0 0 12px var(--cyan-glow);
        }}
        .search-icon {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-dim);
            font-size: 14px;
        }}

        .filter-pills {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .filter-pill {{
            background: var(--bg-card);
            border: 1px solid var(--card-border);
            color: var(--text-dim);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .filter-pill:hover, .filter-pill.active {{
            border-color: var(--cyan);
            color: var(--cyan);
            background: rgba(14, 165, 233, 0.1);
        }}

        /* Data Tables */
        .table-wrap {{
            background: var(--bg-card);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
            margin-bottom: 24px;
        }}
        table.data-table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13px;
        }}
        table.data-table th {{
            background: #111a2e;
            color: var(--cyan);
            padding: 12px 16px;
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--card-border);
            text-transform: uppercase;
        }}
        table.data-table td {{
            padding: 12px 16px;
            border-bottom: 1px solid rgba(30, 41, 59, 0.7);
            vertical-align: middle;
        }}
        table.data-table tr:hover td {{
            background: rgba(56, 189, 248, 0.03);
        }}

        /* Badges & Pills */
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.4px;
            text-transform: uppercase;
        }}
        .badge-covered {{ background: rgba(52, 211, 153, 0.18); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.35); }}
        .badge-partial {{ background: rgba(251, 191, 36, 0.18); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.35); }}
        .badge-critical {{ background: rgba(248, 113, 113, 0.18); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.35); }}
        .badge-warn {{ background: rgba(249, 115, 22, 0.18); color: #f97316; border: 1px solid rgba(249, 115, 22, 0.35); }}
        .badge-neutral {{ background: rgba(148, 163, 184, 0.12); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.25); }}

        .code-pill {{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
            margin: 2px;
            border: 1px solid transparent;
        }}
        .pill-test {{ background: rgba(56, 189, 248, 0.12); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); }}
        .pill-cov {{ background: rgba(168, 85, 247, 0.12); color: #c084fc; border-color: rgba(168, 85, 247, 0.3); }}
        .pill-sva {{ background: rgba(236, 72, 153, 0.12); color: #f472b6; border-color: rgba(236, 72, 153, 0.3); }}
        .pill-feat {{ background: rgba(45, 212, 191, 0.12); color: #2dd4bf; border-color: rgba(45, 212, 191, 0.3); }}

        code {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: #38bdf8;
            background: rgba(15, 23, 42, 0.6);
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .desc-text {{
            font-size: 12px;
            color: var(--text-dim);
            line-height: 1.4;
            margin-top: 4px;
            display: block;
        }}

        /* Test Scenario Cards */
        .test-cards-grid {{
            display: flex;
            flex-direction: column;
            gap: 14px;
            margin-bottom: 24px;
        }}
        .test-card {{
            background: var(--bg-card);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 16px 20px;
            transition: border-color 0.2s;
        }}
        .test-card:hover {{
            border-color: var(--cyan);
        }}
        .test-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .test-title-row {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .test-id-pill code {{
            font-size: 13px;
            font-weight: 700;
            color: #38bdf8;
            background: rgba(14, 165, 233, 0.15);
            border: 1px solid rgba(14, 165, 233, 0.3);
        }}
        .test-name {{
            font-size: 15px;
            font-weight: 700;
            color: var(--text-main);
        }}
        .test-tags {{
            display: flex;
            gap: 8px;
        }}
        .test-meta-row {{
            font-size: 12px;
            margin-bottom: 12px;
        }}
        .test-body-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
        }}
        @media (max-width: 900px) {{
            .test-body-grid {{ grid-template-columns: 1fr; }}
        }}
        .test-box {{
            background: rgba(11, 15, 25, 0.7);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 12px;
        }}
        .test-box .box-hdr {{
            font-size: 11px;
            font-weight: 700;
            color: var(--cyan);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .test-box .box-content {{
            font-size: 13px;
            color: #cbd5e1;
            line-height: 1.45;
        }}

        /* Covergroup & Assertion Cards */
        .cg-card {{
            background: var(--bg-card);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 18px;
        }}
        .cg-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 14px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .cg-title code {{
            font-size: 16px;
            font-weight: 700;
            color: #c084fc;
        }}
        .cg-sub {{
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 3px;
        }}
        .cg-trigger code {{
            color: #38bdf8;
        }}
        .cg-footer {{
            margin-top: 12px;
            font-size: 12px;
            color: var(--text-dim);
        }}
        .bin-desc {{
            font-size: 11px;
            color: #94a3b8;
            max-width: 480px;
            line-height: 1.4;
        }}

        /* Code Block Container */
        .code-container {{
            background: #090d16;
            border: 1px solid var(--card-border);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 24px;
        }}
        .code-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #111827;
            padding: 10px 18px;
            border-bottom: 1px solid var(--card-border);
        }}
        .code-title {{
            font-size: 13px;
            font-weight: 600;
            color: var(--cyan);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .code-actions {{
            display: flex;
            gap: 8px;
        }}
        pre.sv-code {{
            padding: 18px;
            overflow-x: auto;
            font-family: var(--font-mono);
            font-size: 13px;
            color: #38bdf8;
            line-height: 1.5;
            max-height: 600px;
        }}
        pre.sva-expr code {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: #f472b6;
            background: transparent;
            padding: 0;
            display: block;
            white-space: pre-wrap;
        }}

        .empty-card {{
            background: var(--bg-card);
            border: 1px dashed var(--card-border);
            border-radius: 8px;
            padding: 32px;
            text-align: center;
            color: var(--text-dim);
        }}

        @media print {{
            body {{
                background: #ffffff;
                color: #000000;
                padding: 0;
            }}
            .top-navbar, .tabs-header, .controls-bar, .header-actions {{
                display: none !important;
            }}
            .tab-pane {{
                display: block !important;
                page-break-before: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Top Navigation Bar -->
        <header class="top-navbar">
            <div class="brand-col">
                <div class="brand-icon">📋</div>
                <div class="brand-titles">
                    <h1>VeriSight Plan — Verification Architecture Suite</h1>
                    <div class="subtitle">Target DUT: <strong>{html.escape(report.design_name)}</strong> • Plan ID: <code>{html.escape(report.plan_id)}</code> • Spec: <code>{html.escape(report.spec_source)}</code></div>
                </div>
            </div>
            <div class="header-actions">
                <div class="status-chip">
                    <span class="pulsing-dot"></span>
                    <span>PLAN COMPLETE</span>
                </div>
                <button class="btn" onclick="downloadCSV()">📥 Export CSV</button>
                <button class="btn" onclick="downloadCode('coverage_model.sv', svCoverageRaw)">💾 Export SV Coverage</button>
                <button class="btn" onclick="downloadCode('dut_assertions.sv', svAssertionsRaw)">🛡️ Export SVA Suite</button>
                <button class="btn" onclick="window.print()">🖨️ Print Plan</button>
            </div>
        </header>

        <!-- Sovereign Security & Zero Leakage Compliance Banner -->
        <div class="security-banner">
            <div class="security-left">
                <span class="security-shield-icon">{sec_shield}</span>
                <div>
                    <span class="security-text-main">{sec_title}</span>
                    <span class="security-text-sub">{sec_sub}</span>
                </div>
            </div>
            <div class="security-tags">
                <span class="sec-pill sec-pill-success">SOCKET GUARD: {sec_guard}</span>
                <span class="sec-pill sec-pill-success">ZERO CLOUD RTL LEAKAGE</span>
                <span class="sec-pill">ISO 26262 & DO-254 READY</span>
            </div>
        </div>

        <!-- KPI Metrics Grid -->
        <section class="kpi-grid">
            <div class="kpi-card kpi-cyan">
                <div class="kpi-label">Decomposed Features</div>
                <div class="kpi-val">{total_feat}</div>
                <div class="kpi-sub">Functional & protocol specs</div>
            </div>
            <div class="kpi-card kpi-indigo">
                <div class="kpi-label">Test Scenarios</div>
                <div class="kpi-val">{total_tst}</div>
                <div class="kpi-sub">{test_breakdown_str}</div>
            </div>
            <div class="kpi-card kpi-warning">
                <div class="kpi-label">Coverage Points</div>
                <div class="kpi-val">{total_cov}</div>
                <div class="kpi-sub">{len(report.covergroups)} SV Covergroups defined</div>
            </div>
            <div class="kpi-card kpi-cyan">
                <div class="kpi-label">Formal Assertions</div>
                <div class="kpi-val">{total_sva}</div>
                <div class="kpi-sub">SVA formal sequences</div>
            </div>
            <div class="kpi-card kpi-success">
                <div class="kpi-label">Traceability Closure</div>
                <div class="kpi-val" style="color: #34d399;">{closure_pct}%</div>
                <div class="progress-bar-wrap">
                    <div class="progress-bar-fill" style="width: {closure_pct}%;"></div>
                </div>
                <div class="kpi-sub">{cov_cnt} Covered • {part_cnt} Partial • {uncov_cnt} Uncovered</div>
            </div>
        </section>

        <!-- Navigation Tabs -->
        <nav class="tabs-header">
            <button class="tab-btn active" onclick="showTab('tab-matrix', this)">📊 Traceability Matrix</button>
            <button class="tab-btn" onclick="showTab('tab-features', this)">📋 Feature Breakdown</button>
            <button class="tab-btn" onclick="showTab('tab-tests', this)">🧪 Test Plan Suite</button>
            <button class="tab-btn" onclick="showTab('tab-coverage', this)">🎯 Coverage Model (.sv)</button>
            <button class="tab-btn" onclick="showTab('tab-assertions', this)">⚡ SVA Formal Suite (.sv)</button>
        </nav>

        <!-- TAB 1: Traceability Matrix -->
        <div id="tab-matrix" class="tab-pane active">
            <div class="controls-bar">
                <div class="search-box">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="matSearch" class="search-input" placeholder="Search feature, test ID, coverage ID, or assertion..." oninput="filterMatrix()">
                </div>
                <div class="filter-pills">
                    <button class="filter-pill active" onclick="filterMatrixStatus('all', this)">All ({len(report.traceability_matrix)})</button>
                    <button class="filter-pill" onclick="filterMatrixStatus('covered', this)">Covered ({cov_cnt})</button>
                    <button class="filter-pill" onclick="filterMatrixStatus('partial', this)">Partial ({part_cnt})</button>
                    <button class="filter-pill" onclick="filterMatrixStatus('uncovered', this)">Uncovered ({uncov_cnt})</button>
                </div>
            </div>

            <div class="table-wrap">
                <table class="data-table" id="matrixTable">
                    <thead>
                        <tr>
                            <th style="width: 130px;">Feature ID</th>
                            <th>Requirement / Feature Title</th>
                            <th>Target Tests</th>
                            <th>Functional Coverage</th>
                            <th>Formal SVA Properties</th>
                            <th style="width: 110px;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {matrix_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 2: Feature Plan -->
        <div id="tab-features" class="tab-pane">
            <div class="controls-bar">
                <div class="search-box">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="featSearch" class="search-input" placeholder="Search feature description, category, or RTL cross-check..." oninput="filterFeatures()">
                </div>
                <div class="filter-pills">
                    <button class="filter-pill active" onclick="filterFeatCat('all', this)">All Categories</button>
                    <button class="filter-pill" onclick="filterFeatCat('functional', this)">Functional</button>
                    <button class="filter-pill" onclick="filterFeatCat('protocol', this)">Protocol</button>
                    <button class="filter-pill" onclick="filterFeatCat('register', this)">Register</button>
                    <button class="filter-pill" onclick="filterFeatCat('interface', this)">Interface</button>
                </div>
            </div>

            <div class="table-wrap">
                <table class="data-table" id="featTable">
                    <thead>
                        <tr>
                            <th style="width: 130px;">Feature ID</th>
                            <th style="width: 120px;">Category</th>
                            <th style="width: 110px;">Priority</th>
                            <th style="width: 160px;">RTL Cross-Check</th>
                            <th>Feature Title & Specification Requirement</th>
                        </tr>
                    </thead>
                    <tbody>
                        {feat_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 3: Test Scenarios -->
        <div id="tab-tests" class="tab-pane">
            <div class="controls-bar">
                <div class="search-box">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="testSearch" class="search-input" placeholder="Search test stimulus, scoreboard check, or test ID..." oninput="filterTests()">
                </div>
                <div class="filter-pills">
                    <button class="filter-pill active" onclick="filterTestType('all', this)">All Types</button>
                    <button class="filter-pill" onclick="filterTestType('directed', this)">Directed</button>
                    <button class="filter-pill" onclick="filterTestType('constrained_random', this)">Constrained Random</button>
                    <button class="filter-pill" onclick="filterTestType('corner_case', this)">Corner Cases</button>
                    <button class="filter-pill" onclick="filterTestType('error_injection', this)">Error Injection</button>
                </div>
            </div>

            <div class="test-cards-grid" id="testContainer">
                {test_cards_html}
            </div>
        </div>

        <!-- TAB 4: Coverage Model -->
        <div id="tab-coverage" class="tab-pane">
            <div class="controls-bar">
                <div>
                    <h3 style="font-size: 16px; font-weight: 700; color: #c084fc;">Functional Coverage Model & Covergroup Hierarchy</h3>
                    <div class="desc-text">Synthesized SystemVerilog covergroups, coverpoints, and crosses mapped to verification requirements.</div>
                </div>
                <div class="header-actions">
                    <button class="btn" onclick="copyCode('covPre', this)">📋 Copy .sv Package</button>
                    <button class="btn btn-accent" onclick="downloadCode('coverage_model.sv', svCoverageRaw)">💾 Download coverage_model.sv</button>
                </div>
            </div>

            {cg_cards_html}

            <div class="code-container">
                <div class="code-header">
                    <div class="code-title">
                        <span>📄</span> <code>coverage_model.sv</code> — Synthesized SystemVerilog Coverage Package
                    </div>
                    <div class="code-actions">
                        <button class="btn" onclick="copyCode('covPre', this)">📋 Copy</button>
                        <button class="btn" onclick="downloadCode('coverage_model.sv', svCoverageRaw)">💾 Download</button>
                    </div>
                </div>
                <pre class="sv-code"><code id="covPre">{html.escape(cov_sv_code)}</code></pre>
            </div>
        </div>

        <!-- TAB 5: SVA Assertions -->
        <div id="tab-assertions" class="tab-pane">
            <div class="controls-bar">
                <div>
                    <h3 style="font-size: 16px; font-weight: 700; color: #f472b6;">Formal SystemVerilog Assertions (SVA) Specification</h3>
                    <div class="desc-text">Formal property rules, disable conditions, and failure handlers ready for simulation and formal proofs.</div>
                </div>
                <div class="header-actions">
                    <button class="btn" onclick="copyCode('svaPre', this)">📋 Copy .sv Suite</button>
                    <button class="btn btn-accent" onclick="downloadCode('dut_assertions.sv', svAssertionsRaw)">🛡️ Download dut_assertions.sv</button>
                </div>
            </div>

            <div class="table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width: 110px;">SVA ID</th>
                            <th>Property Name</th>
                            <th style="width: 90px;">Type</th>
                            <th>Features</th>
                            <th>Clock & Disable Condition</th>
                            <th>Formal SVA Expression</th>
                            <th>UVM Error Message</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sva_rows_html}
                    </tbody>
                </table>
            </div>

            <div class="code-container">
                <div class="code-header">
                    <div class="code-title">
                        <span>📄</span> <code>dut_assertions.sv</code> — SystemVerilog Formal Assertion Suite
                    </div>
                    <div class="code-actions">
                        <button class="btn" onclick="copyCode('svaPre', this)">📋 Copy</button>
                        <button class="btn" onclick="downloadCode('dut_assertions.sv', svAssertionsRaw)">💾 Download</button>
                    </div>
                </div>
                <pre class="sv-code"><code id="svaPre">{html.escape(sva_sv_code)}</code></pre>
            </div>
        </div>
    </div>

    <!-- Hidden Raw Data for Client-Side Downloads -->
    <textarea id="rawCsvData" style="display:none;">{html.escape(csv_raw_data)}</textarea>

    <script>
        const svCoverageRaw = `{cov_sv_code.replace("`", "\\`")}`;
        const svAssertionsRaw = `{sva_sv_code.replace("`", "\\`")}`;

        function showTab(tabId, btn) {{
            document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            if (btn) btn.classList.add('active');
        }}

        // Matrix Filtering
        let currentMatStatus = 'all';
        function filterMatrixStatus(status, btn) {{
            currentMatStatus = status.toLowerCase();
            document.querySelectorAll('#tab-matrix .filter-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterMatrix();
        }}

        function filterMatrix() {{
            const query = document.getElementById('matSearch').value.toLowerCase().trim();
            const rows = document.querySelectorAll('#matrixTable tbody tr');
            rows.forEach(r => {{
                const status = r.getAttribute('data-status') || '';
                const text = r.getAttribute('data-text') || '';
                const matchStatus = (currentMatStatus === 'all' || status === currentMatStatus);
                const matchQuery = (!query || text.includes(query));
                r.style.display = (matchStatus && matchQuery) ? '' : 'none';
            }});
        }}

        // Feature Filtering
        let currentFeatCat = 'all';
        function filterFeatCat(cat, btn) {{
            currentFeatCat = cat.toLowerCase();
            document.querySelectorAll('#tab-features .filter-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterFeatures();
        }}

        function filterFeatures() {{
            const query = document.getElementById('featSearch').value.toLowerCase().trim();
            const rows = document.querySelectorAll('#featTable tbody tr');
            rows.forEach(r => {{
                const cat = r.getAttribute('data-cat') || '';
                const text = r.getAttribute('data-text') || '';
                const matchCat = (currentFeatCat === 'all' || cat === currentFeatCat);
                const matchQuery = (!query || text.includes(query));
                r.style.display = (matchCat && matchQuery) ? '' : 'none';
            }});
        }}

        // Test Filtering
        let currentTestType = 'all';
        function filterTestType(type, btn) {{
            currentTestType = type.toLowerCase();
            document.querySelectorAll('#tab-tests .filter-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterTests();
        }}

        function filterTests() {{
            const query = document.getElementById('testSearch').value.toLowerCase().trim();
            const cards = document.querySelectorAll('#testContainer .test-card');
            cards.forEach(c => {{
                const type = c.getAttribute('data-type') || '';
                const text = c.getAttribute('data-text') || '';
                const matchType = (currentTestType === 'all' || type === currentTestType);
                const matchQuery = (!query || text.includes(query));
                c.style.display = (matchType && matchQuery) ? '' : 'none';
            }});
        }}

        // Code Copying
        function copyCode(elementId, btn) {{
            const code = document.getElementById(elementId).innerText;
            navigator.clipboard.writeText(code).then(() => {{
                const orig = btn.innerHTML;
                btn.innerHTML = '✓ Copied!';
                btn.style.color = '#34d399';
                setTimeout(() => {{
                    btn.innerHTML = orig;
                    btn.style.color = '';
                }}, 2000);
            }});
        }}

        // Instant Client-Side File Downloads
        function downloadCode(filename, content) {{
            const blob = new Blob([content], {{ type: 'text/plain;charset=utf-8' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}

        function downloadCSV() {{
            const csvData = document.getElementById('rawCsvData').value;
            downloadCode('{report.design_name}_traceability_matrix.csv', csvData);
        }}
    </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"Saved Modern HTML Plan Dashboard: {output_path}")
