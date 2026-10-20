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
    """Generate a sleek, dark-mode interactive HTML presentation dashboard."""
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VeriSight Plan — {report.design_name}</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --primary: #38bdf8;
      --accent: #818cf8;
      --success: #34d399;
      --warning: #fbbf24;
      --danger: #f87171;
      --text: #f8fafc;
      --text-dim: #94a3b8;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 1300px;
      margin: 0 auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 24px;
    }}
    .logo {{
      font-size: 26px;
      font-weight: 800;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .metric-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 16px;
      text-align: center;
    }}
    .metric-val {{
      font-size: 32px;
      font-weight: 700;
      color: var(--primary);
    }}
    .metric-label {{
      font-size: 13px;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-top: 4px;
    }}
    .tabs {{
      display: flex;
      gap: 8px;
      margin-bottom: 20px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 12px;
    }}
    .tab-btn {{
      background: transparent;
      border: 1px solid var(--card-border);
      color: var(--text-dim);
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.2s;
    }}
    .tab-btn.active, .tab-btn:hover {{
      background: var(--primary);
      color: #000;
      border-color: var(--primary);
    }}
    .tab-content {{
      display: none;
    }}
    .tab-content.active {{
      display: block;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card-bg);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 24px;
    }}
    th, td {{
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid var(--card-border);
      font-size: 14px;
    }}
    th {{
      background: #111c2e;
      color: var(--primary);
      font-weight: 700;
    }}
    tr:hover {{
      background: rgba(56, 189, 248, 0.05);
    }}
    .badge {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
    }}
    .badge-covered {{ background: rgba(52, 211, 153, 0.2); color: var(--success); }}
    .badge-partial {{ background: rgba(251, 191, 36, 0.2); color: var(--warning); }}
    .badge-critical {{ background: rgba(248, 113, 113, 0.2); color: var(--danger); }}
    pre {{
      background: #090d16;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
      font-family: "Fira Code", Consolas, monospace;
      font-size: 13px;
      color: #38bdf8;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <div class="logo">VeriSight Plan — Verification Architecture Suite</div>
        <div style="color: var(--text-dim); margin-top: 4px;">Target DUT: <strong>{report.design_name}</strong> | Generated: {report.timestamp}</div>
      </div>
      <div>
        <span class="badge badge-covered" style="font-size: 13px;">ISO 26262 / DO-254 Ready</span>
      </div>
    </header>

    <div class="metrics">
      <div class="metric-card">
        <div class="metric-val">{report.total_features}</div>
        <div class="metric-label">Decomposed Features</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{report.total_tests}</div>
        <div class="metric-label">Test Scenarios</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{report.total_coverage_points}</div>
        <div class="metric-label">Coverage Points</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{report.total_assertions}</div>
        <div class="metric-label">SVA Assertions</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="showTab('tab-matrix')">Traceability Matrix</button>
      <button class="tab-btn" onclick="showTab('tab-features')">Feature Plan</button>
      <button class="tab-btn" onclick="showTab('tab-tests')">Test Plan</button>
      <button class="tab-btn" onclick="showTab('tab-coverage')">Coverage Model (.sv)</button>
      <button class="tab-btn" onclick="showTab('tab-assertions')">SVA Suite (.sv)</button>
    </div>

    <!-- Traceability Matrix -->
    <div id="tab-matrix" class="tab-content active">
      <table>
        <thead>
          <tr>
            <th>Feature ID</th>
            <th>Title</th>
            <th>Test IDs</th>
            <th>Coverage Points</th>
            <th>SVA Assertions</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {"".join([f'''<tr>
            <td><code>{r.feature_id}</code></td>
            <td><strong>{r.feature_title}</strong></td>
            <td>{", ".join([f"<code>{t}</code>" for t in r.test_ids]) or "—"}</td>
            <td>{", ".join([f"<code>{c}</code>" for c in r.coverage_ids]) or "—"}</td>
            <td>{", ".join([f"<code>{s}</code>" for s in r.assertion_ids]) or "—"}</td>
            <td><span class="badge badge-{'covered' if r.status == 'Covered' else 'partial'}">{r.status}</span></td>
          </tr>''' for r in report.traceability_matrix])}
        </tbody>
      </table>
    </div>

    <!-- Features -->
    <div id="tab-features" class="tab-content">
      <table>
        <thead>
          <tr>
            <th>Feature ID</th>
            <th>Category</th>
            <th>Priority</th>
            <th>RTL Cross-Check</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {"".join([f'''<tr>
            <td><code>{f.feature_id}</code></td>
            <td>{f.category}</td>
            <td><span class="badge badge-{'critical' if f.priority == 'Critical' else 'covered'}">{f.priority}</span></td>
            <td><code>{f.rtl_cross_check or 'N/A'}</code></td>
            <td>{f.description}</td>
          </tr>''' for f in report.features])}
        </tbody>
      </table>
    </div>

    <!-- Tests -->
    <div id="tab-tests" class="tab-content">
      <table>
        <thead>
          <tr>
            <th>Test ID</th>
            <th>Type</th>
            <th>Target Features</th>
            <th>Stimulus Scenario</th>
            <th>Scoreboard Response Check</th>
          </tr>
        </thead>
        <tbody>
          {"".join([f'''<tr>
            <td><code>{t.test_id}</code></td>
            <td><span class="badge badge-covered">{t.test_type}</span></td>
            <td>{", ".join([f"<code>{f}</code>" for f in t.feature_ids])}</td>
            <td><strong>{t.title}</strong><br><span style="color:var(--text-dim);">{t.stimulus}</span></td>
            <td>{t.expected_response}</td>
          </tr>''' for t in report.test_scenarios])}
        </tbody>
      </table>
    </div>

    <!-- Coverage Code -->
    <div id="tab-coverage" class="tab-content">
      <h3>SystemVerilog Functional Coverage Package (<code>coverage_model.sv</code>)</h3>
      <pre><code>{report.sv_coverage_code or "// No coverage code generated"}</code></pre>
    </div>

    <!-- SVA Code -->
    <div id="tab-assertions" class="tab-content">
      <h3>SystemVerilog Assertions Suite (<code>dut_assertions.sv</code>)</h3>
      <pre><code>{report.sv_assertion_code or "// No assertions code generated"}</code></pre>
    </div>
  </div>

  <script>
    function showTab(tabId) {{
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      event.target.classList.add('active');
    }}
  </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    logger.info(f"Saved HTML Plan Dashboard: {output_path}")
