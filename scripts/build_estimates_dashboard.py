"""Build WFMEstimates.html from Jira all-fields CSV export."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Tuple

_WFM_HUB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT_CSV = os.path.abspath(
    os.path.join(_WFM_HUB, "..", "jira_csv_export", "output", "created_since_2025-01-01_all_fields.csv")
)

FIELDS: List[Dict[str, str]] = [
    {"key": "issue_key", "label": "Issue Key", "csv": "issue_key"},
    {"key": "issue_id", "label": "Issue ID", "csv": "issue_id"},
    {"key": "summary", "label": "Summary", "csv": "Summary"},
    {"key": "description", "label": "Description", "csv": "Description"},
    {"key": "project", "label": "Project", "csv": "Project"},
    {"key": "issue_type", "label": "Issue Type", "csv": "Issue Type"},
    {"key": "status", "label": "Status", "csv": "Status"},
    {"key": "priority", "label": "Priority", "csv": "Priority"},
    {"key": "assignee", "label": "Assignee", "csv": "Assignee"},
    {"key": "reporter", "label": "Reporter", "csv": "Reporter"},
    {"key": "creator", "label": "Creator", "csv": "Creator"},
    {"key": "created", "label": "Created", "csv": "Created"},
    {"key": "updated", "label": "Updated", "csv": "Updated"},
    {"key": "due_date", "label": "Due Date", "csv": "Due date"},
    {"key": "labels", "label": "Labels", "csv": "Labels"},
    {"key": "parent", "label": "Parent", "csv": "Parent"},
    {"key": "components", "label": "Components", "csv": "Components"},
    {"key": "fix_versions", "label": "Fix Versions", "csv": "Fix versions"},
    {"key": "build_type", "label": "Build Type", "csv": "Build Type (customfield_10577)"},
    {"key": "business_units", "label": "Business Unit(s)", "csv": "Business Unit(s) (customfield_10099)"},
    {"key": "decision_category", "label": "Decision Category", "csv": "Decision Category (customfield_10150)"},
    {"key": "decision_type", "label": "Decision Type", "csv": "Decision Type (customfield_10151)"},
    {"key": "epic_link", "label": "Epic Link", "csv": "Epic Link (customfield_10014)"},
    {"key": "epic_name", "label": "Epic Name", "csv": "Epic Name (customfield_10011)"},
    {"key": "story_points", "label": "Story Points", "csv": "Story Points (customfield_10038)"},
]

DROPDOWN_MAX = 80
TEXT_SEARCH_KEYS = {"issue_key", "issue_id", "summary", "description"}
FILTER_EXCLUDE_KEYS = {
    "issue_type", "issue_key", "issue_id", "summary", "description",
    "decision_category", "decision_type", "business_units", "fix_versions", "priority",
    "creator", "reporter", "created", "updated", "due_date", "parent", "components",
}
DATE_KEYS = {"created", "updated", "due_date"}
JIRA_BASE = "https://pwc-us-adv-cc-9cf57793.atlassian.net"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WFMEstimates.html from Jira CSV.")
    parser.add_argument("--input", default=_DEFAULT_CSV, help="Jira all-fields CSV path.")
    parser.add_argument(
        "--output",
        default=os.path.join(_WFM_HUB, "WFMEstimates.html"),
        help="Output HTML path.",
    )
    return parser.parse_args()


def read_rows(path: str) -> List[Dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with open(path, newline="", encoding="utf-8") as file_obj:
        return list(csv.DictReader(file_obj))


def clean_text(value: str, max_len: int = 0) -> str:
    text = (value or "").strip()
    if max_len and len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def month_key(iso_value: str) -> str:
    if not iso_value:
        return ""
    match = re.match(r"(\d{4}-\d{2})", iso_value)
    return match.group(1) if match else ""


def parse_story_points(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def classify_field(key: str, values: List[str]) -> str:
    non_empty = [v for v in values if v]
    distinct = len(set(non_empty))
    if not non_empty:
        return "empty"
    if key == "story_points":
        return "number"
    if key in TEXT_SEARCH_KEYS:
        return "search"
    if key in DATE_KEYS:
        return "date"
    if distinct <= DROPDOWN_MAX:
        return "dropdown"
    return "search"


def build_issue(row: Dict[str, str]) -> Dict[str, Any]:
    issue: Dict[str, Any] = {}
    for field in FIELDS:
        key = field["key"]
        raw = clean_text(row.get(field["csv"], ""))
        if key == "description":
            issue[key] = clean_text(raw, 400)
        elif key == "story_points":
            issue[key] = parse_story_points(raw)
        elif key in DATE_KEYS:
            issue[key] = raw[:10] if raw else ""
            issue[f"{key}_month"] = month_key(raw)
        else:
            issue[key] = raw
    return issue


def field_options(issues: List[Dict[str, Any]], key: str, ui_type: str) -> List[str]:
    if ui_type == "empty":
        return []
    if ui_type == "number":
        opts = sorted({str(i[key]) for i in issues if i.get(key) is not None})
        return opts
    if ui_type == "date":
        month_vals = sorted({i.get(f"{key}_month", "") for i in issues if i.get(f"{key}_month")})
        return month_vals
    counter: Counter[str] = Counter()
    for issue in issues:
        value = str(issue.get(key) or "").strip()
        if value:
            counter[value] += 1
    return [value for value, _ in counter.most_common()]


def analyze_fields(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    meta: List[Dict[str, Any]] = []
    for field in FIELDS:
        key = field["key"]
        if key in FILTER_EXCLUDE_KEYS:
            continue
        values = [str(issue.get(key) or "") for issue in issues]
        if key == "story_points":
            values = [str(issue[key]) for issue in issues if issue.get(key) is not None]
        ui_type = classify_field(key, values)
        meta.append(
            {
                "key": key,
                "label": field["label"],
                "ui": ui_type,
                "options": field_options(issues, key, ui_type),
                "filled": sum(1 for issue in issues if _has_value(issue, key)),
            }
        )
    return meta


def _has_value(issue: Dict[str, Any], key: str) -> bool:
    if key == "story_points":
        return issue.get(key) is not None
    return bool(str(issue.get(key) or "").strip())


CHART_COLORS = [
    "#4a9eff", "#3dd6c6", "#a78bfa", "#fbbf24", "#fb923c",
    "#f87171", "#34d399", "#818cf8", "#f472b6", "#94a3b8",
    "#1a6fbf", "#0a8f7c",
]


def field_value_options(issues: List[Dict[str, Any]], field_key: str) -> List[str]:
    counter: Counter[str] = Counter()
    for issue in issues:
        value = str(issue.get(field_key) or "").strip() or "(Blank)"
        counter[value] += 1
    return [value for value, _ in counter.most_common()]


def enrich_epic_names(issues: List[Dict[str, Any]], all_rows: List[Dict[str, str]]) -> None:
    key_to_summary = {
        clean_text(row.get("issue_key", "")): clean_text(row.get("Summary", ""))
        for row in all_rows
        if clean_text(row.get("issue_key", ""))
    }
    for issue in issues:
        epic_link = str(issue.get("epic_link") or "").strip()
        resolved = key_to_summary.get(epic_link, "")
        issue["epic_name"] = resolved or clean_text(str(issue.get("epic_name") or "")) or epic_link


def apply_build_type_rules(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    """Dashboard mapping rules (not written back to Jira)."""
    counts = {"integrations_mulesoft": 0, "ootb_rename": 0}
    for issue in issues:
        epic_name = str(issue.get("epic_name") or "").strip()
        build_type = str(issue.get("build_type") or "").strip()
        if epic_name == "Integrations":
            if issue.get("build_type") != "Custom:Mulesoft":
                counts["integrations_mulesoft"] += 1
            issue["build_type"] = "Custom:Mulesoft"
        elif build_type == "OOTB Config":
            issue["build_type"] = "Salesforce : OOTB Config"
            counts["ootb_rename"] += 1
    return counts


def apply_sp_rules(issues: List[Dict[str, Any]]) -> int:
    """Show External/ISV story points as TBD (excluded from SP totals/charts)."""
    updated = 0
    for issue in issues:
        if str(issue.get("build_type") or "").strip() == "External/ISV":
            issue["sp_tbd"] = True
            if issue.get("story_points") is not None:
                updated += 1
        else:
            issue["sp_tbd"] = False
    return updated


def generate_html(issues: List[Dict[str, Any]], field_meta: List[Dict[str, Any]], source: str) -> str:
    generated = datetime.now().strftime("%b %d, %Y %H:%M")
    bu_options = field_value_options(issues, "business_units")
    fix_version_options = field_value_options(issues, "fix_versions")
    data_json = json.dumps(
        {
            "issues": issues,
            "fields": field_meta,
            "buOptions": bu_options,
            "fixVersionOptions": fix_version_options,
        },
        separators=(",", ":"),
    )
    source_name = html.escape(os.path.basename(source))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Estimates — WFM Project</title>
  <style>
    :root {{
      --bg: #0f1419; --surface: #1a2332; --surface-2: #212d3d; --border: #2a3544;
      --text: #e8edf4; --muted: #8b9cb3; --accent: #4a9eff; --teal: #3dd6c6;
      --green: #34d399; --gold: #fbbf24; --hero-shadow: 0 6px 18px rgba(0,0,0,.25);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: "Segoe UI", Inter, Arial, sans-serif; font-size: 13px; }}
    .page {{ max-width: 1680px; margin: 0 auto; padding: 14px 16px 28px; }}
    .hero {{
      background: linear-gradient(135deg, #1f3a5f 0%, #274d78 100%);
      color: white; border-radius: 14px; padding: 14px 16px 12px; box-shadow: var(--hero-shadow);
    }}
    .hero-layout {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }}
    .eyebrow {{ font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.8; margin-bottom: 4px; }}
    h1 {{ margin: 0; font-size: 22px; line-height: 1.2; }}
    .hero-sub {{ margin-top: 6px; font-size: 12px; color: rgba(255,255,255,0.88); max-width: 760px; line-height: 1.45; }}
    .hero-charter-logo {{ height: 40px; object-fit: contain; background: white; padding: 4px 8px; border-radius: 6px; flex-shrink: 0; }}
    .scope-badge {{
      display: inline-block; margin-top: 8px; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2);
      border-radius: 999px; padding: 4px 10px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .layout {{ display: grid; grid-template-columns: 260px 1fr; gap: 12px; margin-top: 12px; align-items: start; }}
    .sidebar {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
      padding: 12px; position: sticky; top: 12px; max-height: calc(100vh - 120px); overflow: auto;
    }}
    .sidebar h2 {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 0 0 10px; }}
    .filter {{ margin-bottom: 9px; }}
    .filter label {{ display: block; font-size: 9px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 3px; }}
    .filter select, .filter input {{
      width: 100%; border: 1px solid var(--border); border-radius: 8px; padding: 6px 8px;
      font-size: 11px; background: var(--surface-2); color: var(--text);
    }}
    .filter .hint {{ font-size: 9px; color: var(--muted); margin-top: 2px; }}
    .filter-actions {{ display: flex; gap: 6px; margin-top: 8px; }}
    .btn {{
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
      border-radius: 8px; padding: 6px 9px; font-size: 10px; font-weight: 700; cursor: pointer;
    }}
    .btn-primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .dash {{ min-width: 0; }}
    .kpi-grid {{
      display: grid; grid-template-columns: 1.4fr repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px;
    }}
    .kpi-card {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px;
    }}
    .kpi-card.hero-kpi {{ background: linear-gradient(135deg, #1e3a5f, #274d78); border-color: #3a5a80; }}
    .kpi-label {{ font-size: 10px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }}
    .hero-kpi .kpi-label {{ color: rgba(255,255,255,0.65); }}
    .kpi-value {{ margin-top: 6px; font-size: 32px; font-weight: 800; color: #fff; line-height: 1; }}
    .kpi-card:not(.hero-kpi) .kpi-value {{ font-size: 26px; color: var(--accent); }}
    .kpi-sub {{ margin-top: 6px; font-size: 10px; color: var(--muted); }}
    .hero-kpi .kpi-sub {{ color: rgba(255,255,255,0.7); }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 10px; }}
    .chart-card {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px;
    }}
    .chart-title {{ font-size: 11px; font-weight: 600; color: var(--muted); margin-bottom: 12px; }}
    .span-4 {{ grid-column: span 4; }}
    .span-6 {{ grid-column: span 6; }}
    .span-8 {{ grid-column: span 8; }}
    .span-12 {{ grid-column: span 12; }}
    .chart-row {{ display: flex; align-items: center; gap: 14px; }}
    .donut {{ border-radius: 50%; position: relative; flex-shrink: 0; }}
    .donut-hole {{
      position: absolute; inset: 22%; background: var(--surface); border-radius: 50%;
      display: flex; align-items: center; justify-content: center; flex-direction: column;
    }}
    .donut-total {{ font-size: 20px; font-weight: 800; color: #fff; }}
    .donut-label {{ font-size: 9px; color: var(--muted); text-transform: uppercase; }}
    .legend {{ flex: 1; min-width: 0; }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 11px; color: var(--muted); }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }}
    .legend-label {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-val {{ font-weight: 700; color: #fff; white-space: nowrap; }}
    .hbar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
    .hbar-row:last-child {{ margin-bottom: 0; }}
    .hbar-label {{ width: 110px; flex-shrink: 0; font-size: 10px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .hbar-track {{ flex: 1; height: 22px; background: var(--surface-2); border-radius: 6px; overflow: hidden; }}
    .hbar-fill {{ height: 100%; border-radius: 6px; display: flex; align-items: center; padding: 0 8px; min-width: 36px; }}
    .hbar-val {{ font-size: 10px; font-weight: 700; color: #fff; white-space: nowrap; }}
    .meta-line {{ font-size: 11px; color: var(--muted); margin-bottom: 10px; }}
    .quick-filters {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
      padding: 12px 14px; margin-bottom: 12px;
      display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;
    }}
    .quick-row {{
      flex: 1 1 280px; min-width: 0;
      border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px;
      background: var(--surface-2);
    }}
    .quick-label {{
      font-size: 10px; font-weight: 700; color: var(--muted); text-transform: uppercase;
      letter-spacing: 0.06em; margin-bottom: 8px;
    }}
    .quick-chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .quick-chip {{
      border: 1px solid var(--border); background: var(--surface-2); color: var(--muted);
      border-radius: 999px; padding: 7px 12px; font-size: 11px; font-weight: 700; cursor: pointer;
    }}
    .quick-chip:hover {{ color: var(--text); border-color: var(--accent); }}
    .quick-chip.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .capacity-kpi-grid {{
      display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px;
    }}
    .capacity-kpi-grid .kpi-value.over {{ color: #f87171; }}
    .capacity-kpi-grid .kpi-value.ok {{ color: var(--green); }}
    .capacity-alert {{
      background: rgba(251, 191, 36, 0.12); border: 1px solid rgba(251, 191, 36, 0.45);
      border-radius: 10px; padding: 10px 14px; margin-bottom: 12px;
      font-size: 12px; color: #fbbf24; line-height: 1.5;
    }}
    .capacity-alert strong {{ color: #fcd34d; }}
    .capacity-chart-card {{ margin-bottom: 12px; }}
    .capacity-note {{ font-size: 11px; color: var(--muted); margin: -4px 0 14px; line-height: 1.45; }}
    .burndown-wrap {{ width: 100%; overflow-x: auto; }}
    .burndown-svg {{ width: 100%; min-width: 640px; height: 300px; display: block; }}
    .capacity-legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 10px; font-size: 11px; color: var(--muted); }}
    .capacity-legend-item {{ display: flex; align-items: center; gap: 6px; }}
    .capacity-legend-line {{ width: 22px; height: 3px; border-radius: 2px; }}
    .capacity-legend-line.dashed {{
      background: repeating-linear-gradient(90deg, #8b9cb3 0 5px, transparent 5px 8px);
    }}
    @media (max-width: 1100px) {{
      .capacity-kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    .view-tabs {{
      display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
    }}
    .view-tab {{
      border: 1px solid var(--border); background: var(--surface-2); color: var(--muted);
      border-radius: 999px; padding: 8px 14px; font-size: 11px; font-weight: 700; cursor: pointer;
    }}
    .view-tab:hover {{ color: var(--text); border-color: var(--accent); }}
    .view-tab.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .view-panel {{ display: none; }}
    .view-panel.active {{ display: block; }}
    .list-panel {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px;
    }}
    .list-head {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }}
    .list-title {{ font-size: 13px; font-weight: 700; color: var(--text); }}
    .list-sub {{ font-size: 11px; color: var(--muted); }}
    .table-wrap {{ overflow: auto; max-height: calc(100vh - 260px); border: 1px solid var(--border); border-radius: 10px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1000px; }}
    thead th {{
      position: sticky; top: 0; background: #252f3f; border-bottom: 1px solid var(--border);
      padding: 8px 10px; text-align: left; font-size: 10px; text-transform: uppercase; color: var(--muted);
    }}
    tbody td {{ border-bottom: 1px solid rgba(42,53,68,.7); padding: 7px 10px; font-size: 11px; }}
    tbody tr:hover {{ background: rgba(74,158,255,.06); }}
    .mono {{ font-family: Consolas, monospace; font-size: 10px; }}
    .mono a {{ color: var(--accent); text-decoration: none; }}
    .sp {{ font-weight: 800; color: var(--green); }}
    .sp-tbd {{ font-weight: 700; color: var(--gold); }}
    @media (max-width: 1100px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; max-height: none; }}
      .kpi-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
      .span-4, .span-6, .span-8, .span-12 {{ grid-column: span 12; }}
      .chart-row {{ flex-direction: column; align-items: stretch; }}
    }}
    #gate {{
      position: fixed; inset: 0; z-index: 9999; background: #0d1b2e;
      display: flex; align-items: center; justify-content: center;
    }}
    .gate-box {{ text-align: center; width: 340px; }}
    .gate-logo {{ font-size: 13px; font-weight: 700; letter-spacing: 2px; color: rgba(255,255,255,0.4); text-transform: uppercase; margin-bottom: 32px; }}
    .gate-logo span {{ color: #e8712a; }}
    .gate-box h2 {{ font-size: 22px; font-weight: 700; color: #fff; margin: 0 0 6px; }}
    .gate-box p {{ font-size: 13px; color: rgba(255,255,255,0.5); margin: 0 0 28px; line-height: 1.5; }}
    .gate-input-wrap {{ position: relative; margin-bottom: 14px; }}
    .gate-input-wrap input {{
      width: 100%; padding: 13px 46px 13px 16px; background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.18); border-radius: 8px; color: #fff; font-size: 15px; outline: none;
    }}
    .gate-input-wrap input:focus {{ border-color: #e8712a; }}
    .gate-eye {{ position: absolute; right: 14px; top: 50%; transform: translateY(-50%); cursor: pointer; color: rgba(255,255,255,0.4); }}
    .gate-btn {{ width: 100%; padding: 13px; background: #e8712a; border: none; border-radius: 8px; color: #fff; font-size: 14px; font-weight: 700; cursor: pointer; }}
    .gate-error {{ font-size: 12px; color: #f4a261; margin-top: 10px; min-height: 18px; }}
    .gate-shake {{ animation: gshake 0.35s ease; }}
    @keyframes gshake {{
      0%, 100% {{ transform: translateX(0); }}
      20% {{ transform: translateX(-8px); }}
      40% {{ transform: translateX(8px); }}
      60% {{ transform: translateX(-6px); }}
      80% {{ transform: translateX(6px); }}
    }}
  </style>
</head>
<body>
  <div id="gate">
    <div class="gate-box">
      <div class="gate-logo">Charter &times; PwC &nbsp;<span>&#9679;</span>&nbsp; WFM Global Design</div>
      <h2>Estimates</h2>
      <p>Enter the project passphrase to open<br />this page.</p>
      <div class="gate-input-wrap">
        <input id="gate-input" type="password" placeholder="Enter passphrase" autocomplete="off"
          onkeydown="if (event.key === 'Enter') gateSubmit()" />
        <span class="gate-eye" id="gate-eye" onclick="gateToggleEye()">&#128065;</span>
      </div>
      <button type="button" class="gate-btn" onclick="gateSubmit()">Enter</button>
      <div class="gate-error" id="gate-error"></div>
    </div>
  </div>

  <div class="page">
    <section class="hero">
      <div class="hero-layout">
        <div>
          <div class="eyebrow">WFM Project</div>
          <h1>Estimates</h1>
          <div class="hero-sub">Requirement effort dashboard · story points as estimate units · {len(issues)} requirements · generated {generated}</div>
          <span class="scope-badge">Issue Type = Requirement</span>
        </div>
        <img class="hero-charter-logo"
          src="https://corporate.charter.com/static/d617519f6e8ec1333149b2e86dd914fb/58aae/Charter_Communications_Logo_Preview_0.jpg"
          alt="Charter" />
      </div>
    </section>

    <div class="layout">
      <aside class="sidebar">
        <h2>Filters</h2>
        <div id="filters"></div>
        <div class="filter-actions">
          <button type="button" class="btn" id="clearBtn">Clear all</button>
        </div>
      </aside>

      <div class="dash">
        <div class="view-tabs" role="tablist" aria-label="Estimates views">
          <button type="button" class="view-tab active" data-tab="dashboard" role="tab" aria-selected="true">Dashboard</button>
          <button type="button" class="view-tab" data-tab="requirements" role="tab" aria-selected="false">Requirements (<span id="tabReqCount">0</span>)</button>
          <button type="button" class="view-tab" data-tab="capacity" role="tab" aria-selected="false">Capacity to Load</button>
        </div>

        <div id="panelDashboard" class="view-panel active" role="tabpanel">
          <div class="kpi-grid">
            <div class="kpi-card hero-kpi">
              <div class="kpi-label">Total effort</div>
              <div class="kpi-value" id="kpiTotalSp">0</div>
              <div class="kpi-sub">Story points (filtered requirements)</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Requirements</div>
              <div class="kpi-value" id="kpiCount">0</div>
              <div class="kpi-sub">Matching filters</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Estimated</div>
              <div class="kpi-value" id="kpiWithSp">0</div>
              <div class="kpi-sub">With story points</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Unestimated</div>
              <div class="kpi-value" id="kpiNoSp">0</div>
              <div class="kpi-sub">Missing story points</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Avg SP</div>
              <div class="kpi-value" id="kpiAvg">—</div>
              <div class="kpi-sub">Estimated only</div>
            </div>
          </div>

          <div class="meta-line" id="metaLine"></div>

          <div class="quick-filters">
            <div class="quick-row">
              <div class="quick-label">Business unit</div>
              <div class="quick-chips" id="buQuickFilters"></div>
            </div>
            <div class="quick-row">
              <div class="quick-label">Fix version</div>
              <div class="quick-chips" id="fixVersionQuickFilters"></div>
            </div>
          </div>

          <div class="chart-grid">
            <div class="chart-card span-6" id="chartBu"></div>
            <div class="chart-card span-6" id="chartEpic"></div>
            <div class="chart-card span-6" id="chartBuildCount"></div>
            <div class="chart-card span-6" id="chartStatus"></div>
            <div class="chart-card span-6" id="chartBuild"></div>
          </div>
        </div>

        <div id="panelRequirements" class="view-panel" role="tabpanel">
          <div class="list-panel">
            <div class="list-head">
              <div>
                <div class="list-title">Requirements</div>
                <div class="list-sub"><span id="tableCount">0</span> matching current filters</div>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Key</th><th>Summary</th><th>Status</th><th>Priority</th>
                    <th>Assignee</th><th>BU</th><th>Build Type</th><th>Epic</th><th>SP</th>
                  </tr>
                </thead>
                <tbody id="issueBody"></tbody>
              </table>
            </div>
          </div>
        </div>

        <div id="panelCapacity" class="view-panel" role="tabpanel">
          <div class="capacity-alert">
            <strong>Tight plan</strong> — Zero buffer. Includes 2 weeks shutdown: 1 week during year-end and 1 week for Thanksgiving.
          </div>
          <div class="capacity-kpi-grid">
            <div class="kpi-card hero-kpi">
              <div class="kpi-label">Available capacity</div>
              <div class="kpi-value" id="capTotal">2,250 SP</div>
              <div class="kpi-sub">9 sprints · 2 weeks each · 250 SP / sprint</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Filtered load</div>
              <div class="kpi-value" id="capLoad">0 SP</div>
              <div class="kpi-sub">Estimated story points</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Remaining capacity</div>
              <div class="kpi-value" id="capRemaining">2,250 SP</div>
              <div class="kpi-sub" id="capRemainingSub">After full load</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Utilization</div>
              <div class="kpi-value" id="capUtil">0%</div>
              <div class="kpi-sub" id="capUtilSub">Load vs 2,250 SP capacity</div>
            </div>
          </div>
          <div class="chart-card capacity-chart-card">
            <div class="chart-title">Capacity burn up</div>
            <div class="capacity-note" id="capNote"></div>
            <div class="burndown-wrap" id="capacityBurndown"></div>
            <div class="capacity-legend">
              <div class="capacity-legend-item"><span class="capacity-legend-line" style="background:#4a9eff"></span>Filtered load (cumulative SP)</div>
              <div class="capacity-legend-item"><span class="capacity-legend-line dashed"></span>Planned capacity (250 SP / sprint)</div>
              <div class="capacity-legend-item"><span class="capacity-legend-line" style="background:#fbbf24;height:2px"></span>Capacity ceiling (2,250 SP)</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const JIRA_BASE = {json.dumps(JIRA_BASE)};
    const DATA = {data_json};
    const COLORS = {json.dumps(CHART_COLORS)};
    const HUB_PASS = "wfm";
    const HUB_KEY = "wfm_estimates_auth";

    (function gateInit() {{
      if (sessionStorage.getItem(HUB_KEY) === "1") {{
        document.getElementById("gate").style.display = "none";
        return;
      }}
      setTimeout(function () {{ document.getElementById("gate-input").focus(); }}, 0);
    }})();

    function gateSubmit() {{
      var val = document.getElementById("gate-input").value;
      if (val === HUB_PASS) {{
        sessionStorage.setItem(HUB_KEY, "1");
        var g = document.getElementById("gate");
        g.style.transition = "opacity .4s";
        g.style.opacity = "0";
        setTimeout(function () {{ g.style.display = "none"; }}, 400);
      }} else {{
        var err = document.getElementById("gate-error");
        var wrap = document.getElementById("gate-input").parentElement;
        err.textContent = "Incorrect passphrase. Please try again.";
        wrap.classList.remove("gate-shake");
        void wrap.offsetWidth;
        wrap.classList.add("gate-shake");
        document.getElementById("gate-input").value = "";
        document.getElementById("gate-input").focus();
      }}
    }}

    function gateToggleEye() {{
      var inp = document.getElementById("gate-input");
      var eye = document.getElementById("gate-eye");
      if (inp.type === "password") {{ inp.type = "text"; eye.textContent = "\\uD83D\\uDD76"; }}
      else {{ inp.type = "password"; eye.textContent = "\\uD83D\\uDC41"; }}
    }}

    const filtersEl = document.getElementById("filters");
    const quickFilterSelections = {{
      business_units: new Set(),
      fix_versions: new Set(),
    }};

    function escapeHtml(v) {{
      return String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    }}

    function buildFilters() {{
      filtersEl.innerHTML = DATA.fields.map(function (field) {{
        const id = "f-" + field.key;
        if (field.ui === "empty") {{
          return '<div class="filter"><label>' + escapeHtml(field.label) + '</label>' +
            '<select id="' + id + '" disabled><option>No values</option></select></div>';
        }}
        if (field.ui === "search") {{
          return '<div class="filter"><label>' + escapeHtml(field.label) + '</label>' +
            '<input type="search" id="' + id + '" placeholder="Contains…" data-ui="search" /></div>';
        }}
        if (field.ui === "number") {{
          let opts = '<option value="">All</option><option value="__has__">Has SP</option><option value="__none__">No SP</option>';
          field.options.forEach(function (o) {{ opts += '<option value="' + escapeHtml(o) + '">' + escapeHtml(o) + '</option>'; }});
          return '<div class="filter"><label>' + escapeHtml(field.label) + '</label>' +
            '<select id="' + id + '" data-ui="number">' + opts + '</select></div>';
        }}
        if (field.ui === "date") {{
          let opts = '<option value="">All months</option>';
          field.options.forEach(function (o) {{ opts += '<option value="' + escapeHtml(o) + '">' + escapeHtml(o) + '</option>'; }});
          return '<div class="filter"><label>' + escapeHtml(field.label) + '</label>' +
            '<select id="' + id + '" data-ui="date" data-key="' + field.key + '">' + opts + '</select></div>';
        }}
        let opts = '<option value="">All</option><option value="__blank__">(Blank)</option>';
        field.options.forEach(function (o) {{ opts += '<option value="' + escapeHtml(o) + '">' + escapeHtml(o) + '</option>'; }});
        return '<div class="filter"><label>' + escapeHtml(field.label) + '</label>' +
          '<select id="' + id + '" data-ui="dropdown" data-key="' + field.key + '">' + opts + '</select></div>';
      }}).join("");
    }}

    function buildQuickFilterGroup(containerId, fieldKey, options) {{
      const el = document.getElementById(containerId);
      const chips = ['<button type="button" class="quick-chip active" data-value="">All</button>'];
      (options || []).forEach(function (option) {{
        chips.push(
          '<button type="button" class="quick-chip" data-value="' + escapeHtml(option) + '">' +
          escapeHtml(option) + '</button>'
        );
      }});
      el.innerHTML = chips.join("");
      el.querySelectorAll(".quick-chip").forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          const value = btn.dataset.value || "";
          const selected = quickFilterSelections[fieldKey];
          if (!value) {{
            selected.clear();
          }} else if (selected.has(value)) {{
            selected.delete(value);
          }} else {{
            selected.add(value);
          }}
          syncQuickFilterGroup(containerId, fieldKey);
          render();
        }});
      }});
    }}

    function syncQuickFilterGroup(containerId, fieldKey) {{
      const selected = quickFilterSelections[fieldKey];
      document.querySelectorAll("#" + containerId + " .quick-chip").forEach(function (btn) {{
        const value = btn.dataset.value || "";
        if (!value) {{
          btn.classList.toggle("active", selected.size === 0);
        }} else {{
          btn.classList.toggle("active", selected.has(value));
        }}
      }});
    }}

    function syncQuickFilters() {{
      syncQuickFilterGroup("buQuickFilters", "business_units");
      syncQuickFilterGroup("fixVersionQuickFilters", "fix_versions");
    }}

    function buildQuickFilters() {{
      buildQuickFilterGroup("buQuickFilters", "business_units", DATA.buOptions);
      buildQuickFilterGroup("fixVersionQuickFilters", "fix_versions", DATA.fixVersionOptions);
    }}

    function matchesQuickFilters(issue) {{
      if (quickFilterSelections.business_units.size) {{
        const bu = String(issue.business_units || "").trim() || "(Blank)";
        if (!quickFilterSelections.business_units.has(bu)) return false;
      }}
      if (quickFilterSelections.fix_versions.size) {{
        const fixVersion = String(issue.fix_versions || "").trim() || "(Blank)";
        if (!quickFilterSelections.fix_versions.has(fixVersion)) return false;
      }}
      return true;
    }}

    function readFilters() {{
      const result = {{}};
      DATA.fields.forEach(function (field) {{
        const el = document.getElementById("f-" + field.key);
        if (!el || el.disabled) return;
        result[field.key] = {{ ui: field.ui, value: (el.value || "").trim() }};
      }});
      return result;
    }}

    function matchIssue(issue, filters) {{
      for (const key in filters) {{
        const f = filters[key];
        const val = f.value;
        if (!val) continue;
        if (f.ui === "search") {{
          if (!String(issue[key] || "").toLowerCase().includes(val.toLowerCase())) return false;
          continue;
        }}
        if (f.ui === "number") {{
          if (val === "__has__" && (issue.sp_tbd || issue.story_points == null)) return false;
          if (val === "__none__" && !issue.sp_tbd && issue.story_points != null) return false;
          if (val !== "__has__" && val !== "__none__" && String(issue.story_points) !== val) return false;
          continue;
        }}
        if (f.ui === "date") {{
          if ((issue[key + "_month"] || "") !== val) return false;
          continue;
        }}
        const cell = String(issue[key] || "");
        if (val === "__blank__") {{ if (cell) return false; continue; }}
        if (cell !== val) return false;
      }}
      return true;
    }}

    function aggregate(rows, field, mode, limit) {{
      const map = {{}};
      rows.forEach(function (r) {{
        const key = String(r[field] || "").trim() || "(Blank)";
        if (!map[key]) map[key] = {{ label: key, sp: 0, count: 0 }};
        map[key].count += 1;
        if (r.story_points != null && !r.sp_tbd) map[key].sp += r.story_points;
      }});
      let items = Object.values(map);
      if (mode === "sp") items.sort(function (a, b) {{ return b.sp - a.sp; }});
      else items.sort(function (a, b) {{ return b.count - a.count; }});
      if (limit) items = items.slice(0, limit);
      return items;
    }}

    function conicDonut(items, mode, size) {{
      const metric = mode === "sp"
        ? items.map(function (i) {{ return i.sp; }})
        : items.map(function (i) {{ return i.count; }});
      const total = metric.reduce(function (s, v) {{ return s + v; }}, 0);
      if (!total) return '<div class="chart-row"><div style="color:var(--muted);font-size:12px">No data</div></div>';
      let offset = 0;
      const parts = items.map(function (item, idx) {{
        const val = mode === "sp" ? item.sp : item.count;
        const pct = val / total * 100;
        const color = COLORS[idx % COLORS.length];
        const seg = color + " " + offset.toFixed(2) + "% " + (offset + pct).toFixed(2) + "%";
        offset += pct;
        return seg;
      }});
      const legend = items.map(function (item, idx) {{
        const val = mode === "sp" ? item.sp : item.count;
        const color = COLORS[idx % COLORS.length];
        return '<div class="legend-item"><span class="legend-swatch" style="background:' + color + '"></span>' +
          '<span class="legend-label">' + escapeHtml(item.label) + '</span>' +
          '<span class="legend-val">' + (mode === "sp" ? val + " SP" : val) + '</span></div>';
      }}).join("");
      return '<div class="chart-row">' +
        '<div class="donut" style="width:' + size + 'px;height:' + size + 'px;background:conic-gradient(' + parts.join(", ") + ')">' +
        '<div class="donut-hole"><span class="donut-total">' + Math.round(total * 10) / 10 + '</span><span class="donut-label">' + (mode === "sp" ? "SP" : "Count") + '</span></div></div>' +
        '<div class="legend">' + legend + '</div></div>';
    }}

    function salesforceMixDonut(rows, size) {{
      const specs = [
        {{ buildType: "Salesforce : OOTB Config", label: "Salesforce OOTB" }},
        {{ buildType: "Custom: Salesforce", label: "Salesforce Custom" }},
      ];
      const items = specs.map(function (spec) {{
        const count = rows.filter(function (r) {{ return r.build_type === spec.buildType; }}).length;
        return {{ label: spec.label, count: count }};
      }}).filter(function (item) {{ return item.count > 0; }});
      const total = items.reduce(function (sum, item) {{ return sum + item.count; }}, 0);
      if (!total) {{
        return '<div style="color:var(--muted);font-size:12px">No Salesforce OOTB or Custom requirements</div>';
      }}
      let offset = 0;
      const parts = items.map(function (item, idx) {{
        const pct = item.count / total * 100;
        const color = COLORS[idx % COLORS.length];
        const seg = color + " " + offset.toFixed(2) + "% " + (offset + pct).toFixed(2) + "%";
        offset += pct;
        return seg;
      }});
      const legend = items.map(function (item, idx) {{
        const pct = Math.round(item.count / total * 1000) / 10;
        const color = COLORS[idx % COLORS.length];
        return '<div class="legend-item"><span class="legend-swatch" style="background:' + color + '"></span>' +
          '<span class="legend-label">' + escapeHtml(item.label) + '</span>' +
          '<span class="legend-val">' + pct + '% · ' + item.count + '</span></div>';
      }}).join("");
      return '<div class="chart-row">' +
        '<div class="donut" style="width:' + size + 'px;height:' + size + 'px;background:conic-gradient(' + parts.join(", ") + ')">' +
        '<div class="donut-hole"><span class="donut-total">100%</span><span class="donut-label">' + total + ' reqs</span></div></div>' +
        '<div class="legend">' + legend + '</div></div>';
    }}

    function hbarChart(items, mode) {{
      if (!items.length) return '<div style="color:var(--muted);font-size:12px">No data</div>';
      const vals = items.map(function (i) {{ return mode === "sp" ? i.sp : i.count; }});
      const max = Math.max.apply(null, vals) || 1;
      return items.map(function (item, idx) {{
        const val = mode === "sp" ? item.sp : item.count;
        const width = Math.max(4, Math.round(val / max * 100));
        const color = COLORS[idx % COLORS.length];
        const label = item.label.length > 16 ? item.label.slice(0, 15) + "…" : item.label;
        return '<div class="hbar-row"><div class="hbar-label" title="' + escapeHtml(item.label) + '">' + escapeHtml(label) + '</div>' +
          '<div class="hbar-track"><div class="hbar-fill" style="width:' + width + '%;background:' + color + '">' +
          '<span class="hbar-val">' + (mode === "sp" ? val + " SP" : val) + '</span></div></div></div>';
      }}).join("");
    }}

    const TOTAL_CAPACITY = 2250;
    const SPRINT_COUNT = 9;
    const CAPACITY_PER_SPRINT = 250;

    function formatSp(value) {{
      const rounded = Math.round(value * 10) / 10;
      return rounded.toLocaleString(undefined, {{ maximumFractionDigits: 1 }});
    }}

    function formatSpLabel(value) {{
      return formatSp(value) + " SP";
    }}

    function renderCapacity(totalSp) {{
      const remainingAfterLoad = TOTAL_CAPACITY - totalSp;
      const utilization = TOTAL_CAPACITY ? (totalSp / TOTAL_CAPACITY) * 100 : 0;
      const over = remainingAfterLoad < 0;
      const completionSprint = totalSp > 0 ? Math.ceil(totalSp / CAPACITY_PER_SPRINT) : 0;
      const maxSprint = Math.max(SPRINT_COUNT, completionSprint);

      document.getElementById("capTotal").textContent = formatSpLabel(TOTAL_CAPACITY);
      document.getElementById("capLoad").textContent = formatSpLabel(totalSp);
      const remEl = document.getElementById("capRemaining");
      remEl.textContent = formatSpLabel(remainingAfterLoad);
      remEl.className = "kpi-value" + (over ? " over" : " ok");
      document.getElementById("capRemainingSub").textContent = over
        ? ("Over capacity by " + formatSpLabel(Math.abs(remainingAfterLoad)))
        : "After full load";
      const utilEl = document.getElementById("capUtil");
      utilEl.textContent = Math.round(utilization) + "%";
      utilEl.className = "kpi-value" + (utilization > 100 ? " over" : "");
      document.getElementById("capUtilSub").textContent = utilization > 100
        ? ("Exceeds " + formatSpLabel(TOTAL_CAPACITY) + " capacity")
        : ("Load vs " + formatSpLabel(TOTAL_CAPACITY) + " capacity");

      let note = "Delivery rate " + CAPACITY_PER_SPRINT + " SP / sprint · Plan horizon sprint " + SPRINT_COUNT +
        " (" + formatSpLabel(TOTAL_CAPACITY) + " capacity) · Zero buffer";
      if (totalSp > 0) {{
        note += " · Projected completion sprint " + completionSprint + " (" + formatSpLabel(totalSp) + ")";
        if (completionSprint > SPRINT_COUNT) {{
          note += " · " + (completionSprint - SPRINT_COUNT) + " sprints beyond plan";
        }}
      }}
      document.getElementById("capNote").textContent = note;

      const loadSeries = [];
      const capacitySeries = [];
      for (let s = 0; s <= maxSprint; s++) {{
        loadSeries.push(Math.min(s * CAPACITY_PER_SPRINT, totalSp));
        capacitySeries.push(Math.min(s * CAPACITY_PER_SPRINT, TOTAL_CAPACITY));
      }}

      const peak = Math.max(TOTAL_CAPACITY, totalSp, 200);
      const maxY = Math.ceil(peak / 200) * 200;
      const width = Math.max(920, 80 + maxSprint * 72);
      const height = 300;
      const pad = {{ top: 28, right: 28, bottom: 48, left: 62 }};
      const plotW = width - pad.left - pad.right;
      const plotH = height - pad.top - pad.bottom;

      function xAt(sprint) {{ return pad.left + (sprint / maxSprint) * plotW; }}
      function yAt(v) {{ return pad.top + (1 - v / maxY) * plotH; }}
      function linePath(vals) {{
        return vals.map(function (v, i) {{
          return (i === 0 ? "M" : "L") + xAt(i).toFixed(1) + "," + yAt(v).toFixed(1);
        }}).join(" ");
      }}

      let grid = "";
      for (let v = 0; v <= maxY; v += 200) {{
        const y = yAt(v).toFixed(1);
        const isZero = v === 0;
        grid += '<line x1="' + pad.left + '" y1="' + y + '" x2="' + (width - pad.right) + '" y2="' + y +
          '" stroke="' + (isZero ? "#8b9cb3" : "#2a3544") + '" stroke-width="' + (isZero ? "1.5" : "1") + '"/>';
        grid += '<text x="' + (pad.left - 8) + '" y="' + y + '" fill="#8b9cb3" font-size="10" text-anchor="end" dominant-baseline="middle">' +
          formatSp(v) + '</text>';
      }}

      const yCap = yAt(TOTAL_CAPACITY).toFixed(1);
      grid += '<line x1="' + pad.left + '" y1="' + yCap + '" x2="' + (width - pad.right) + '" y2="' + yCap +
        '" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5 4"/>';
      grid += '<text x="' + (width - pad.right + 4) + '" y="' + yCap +
        '" fill="#fbbf24" font-size="9" dominant-baseline="middle">' + formatSpLabel(TOTAL_CAPACITY) + '</text>';

      if (maxSprint > SPRINT_COUNT) {{
        const xPlan = xAt(SPRINT_COUNT).toFixed(1);
        grid += '<line x1="' + xPlan + '" y1="' + pad.top + '" x2="' + xPlan + '" y2="' + (height - pad.bottom) +
          '" stroke="#5f7388" stroke-width="1" stroke-dasharray="4 4"/>';
        grid += '<text x="' + xPlan + '" y="' + (pad.top - 8) +
          '" fill="#8b9cb3" font-size="9" text-anchor="middle">S' + SPRINT_COUNT + " plan</text>";
      }}

      let xLabels = "";
      for (let s = 0; s <= maxSprint; s++) {{
        const label = s === 0 ? "0" : "S" + s;
        const anchor = s === 0 ? "start" : (s === maxSprint ? "end" : "middle");
        const highlight = s === completionSprint && totalSp > 0;
        xLabels += '<text x="' + xAt(s).toFixed(1) + '" y="' + (height - 16) +
          '" fill="' + (highlight ? "#4a9eff" : "#8b9cb3") + '" font-size="10" text-anchor="' + anchor +
          '" font-weight="' + (highlight ? "700" : "400") + '">' + label +
          (highlight ? "*" : "") + '</text>';
      }}

      let points = "";
      loadSeries.forEach(function (v, i) {{
        if (i > completionSprint) return;
        const color = v > TOTAL_CAPACITY ? "#f87171" : "#4a9eff";
        points += '<circle cx="' + xAt(i).toFixed(1) + '" cy="' + yAt(v).toFixed(1) +
          '" r="3.5" fill="' + color + '"/>';
      }});

      const loadPath = linePath(loadSeries.slice(0, completionSprint + 1));

      document.getElementById("capacityBurndown").innerHTML =
        '<svg class="burndown-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Capacity burn up chart">' +
        grid +
        '<path d="' + linePath(capacitySeries) + '" fill="none" stroke="#8b9cb3" stroke-width="2" stroke-dasharray="6 5"/>' +
        '<path d="' + loadPath + '" fill="none" stroke="#4a9eff" stroke-width="2.5"/>' +
        points +
        xLabels +
        '<text x="' + (pad.left + plotW / 2) + '" y="' + (height - 4) +
          '" fill="#8b9cb3" font-size="10" text-anchor="middle">Sprint (2 weeks each) · * projected completion</text>' +
        '</svg>';
    }}

    function renderCharts(rows) {{
      document.getElementById("chartBu").innerHTML =
        '<div class="chart-title">Story points by business unit</div>' +
        hbarChart(aggregate(rows, "business_units", "sp", 8), "sp");
      document.getElementById("chartEpic").innerHTML =
        '<div class="chart-title">Story points by epic (top 10)</div>' +
        hbarChart(aggregate(rows, "epic_name", "sp", 10), "sp");
      document.getElementById("chartBuildCount").innerHTML =
        '<div class="chart-title">Salesforce OOTB vs Custom (% requirements)</div>' +
        salesforceMixDonut(rows, 140);
      document.getElementById("chartStatus").innerHTML =
        '<div class="chart-title">Requirements by status</div>' +
        conicDonut(aggregate(rows, "status", "count", 8), "count", 120);
      document.getElementById("chartBuild").innerHTML =
        '<div class="chart-title">Story points by build type</div>' +
        conicDonut(aggregate(rows, "build_type", "sp", 6), "sp", 120);
    }}

    function render() {{
      const rows = DATA.issues.filter(function (issue) {{
        return matchIssue(issue, readFilters()) && matchesQuickFilters(issue);
      }});
      const withSp = rows.filter(function (r) {{ return !r.sp_tbd && r.story_points != null; }});
      const tbdSp = rows.filter(function (r) {{ return r.sp_tbd; }});
      const totalSp = withSp.reduce(function (s, r) {{ return s + r.story_points; }}, 0);

      document.getElementById("kpiTotalSp").textContent = Math.round(totalSp * 10) / 10;
      document.getElementById("kpiCount").textContent = rows.length;
      document.getElementById("kpiWithSp").textContent = withSp.length;
      document.getElementById("kpiNoSp").textContent = rows.length - withSp.length - tbdSp.length;
      document.getElementById("kpiAvg").textContent = withSp.length ? (Math.round((totalSp / withSp.length) * 10) / 10) : "—";
      document.getElementById("metaLine").textContent = "Source: {source_name} · Requirements only · showing " + rows.length + " of " + DATA.issues.length;
      document.getElementById("tableCount").textContent = rows.length;
      document.getElementById("tabReqCount").textContent = rows.length;

      renderCharts(rows);
      renderCapacity(totalSp);

      document.getElementById("issueBody").innerHTML = rows.map(function (r) {{
        const keyLink = '<a href="' + JIRA_BASE + '/browse/' + encodeURIComponent(r.issue_key) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(r.issue_key) + '</a>';
        const sp = r.sp_tbd
          ? '<span class="sp-tbd">TBD</span>'
          : (r.story_points != null ? '<span class="sp">' + r.story_points + '</span>' : "—");
        const epic = r.epic_name || r.epic_link || "—";
        return "<tr>" +
          '<td class="mono">' + keyLink + "</td>" +
          '<td title="' + escapeHtml(r.summary) + '">' + escapeHtml(r.summary) + "</td>" +
          "<td>" + escapeHtml(r.status) + "</td>" +
          "<td>" + escapeHtml(r.priority) + "</td>" +
          "<td>" + escapeHtml(r.assignee || "—") + "</td>" +
          "<td>" + escapeHtml(r.business_units || "—") + "</td>" +
          "<td>" + escapeHtml(r.build_type || "—") + "</td>" +
          '<td title="' + escapeHtml(r.epic_link || "") + '">' + escapeHtml(epic) + '</td>' +
          "<td>" + sp + "</td></tr>";
      }}).join("");
    }}

    function setActiveTab(tabId) {{
      document.querySelectorAll(".view-tab").forEach(function (btn) {{
        const active = btn.dataset.tab === tabId;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      }});
      document.getElementById("panelDashboard").classList.toggle("active", tabId === "dashboard");
      document.getElementById("panelRequirements").classList.toggle("active", tabId === "requirements");
      document.getElementById("panelCapacity").classList.toggle("active", tabId === "capacity");
    }}

    document.querySelectorAll(".view-tab").forEach(function (btn) {{
      btn.addEventListener("click", function () {{ setActiveTab(btn.dataset.tab); }});
    }});

    buildFilters();
    buildQuickFilters();
    document.getElementById("clearBtn").addEventListener("click", function () {{
      DATA.fields.forEach(function (field) {{
        const el = document.getElementById("f-" + field.key);
        if (el && !el.disabled) el.value = "";
      }});
      quickFilterSelections.business_units.clear();
      quickFilterSelections.fix_versions.clear();
      syncQuickFilters();
      render();
    }});
    filtersEl.addEventListener("change", render);
    filtersEl.addEventListener("input", function (e) {{
      if (e.target && e.target.type === "search") render();
    }});
    render();
  </script>
</body>
</html>"""


def main() -> None:
    args = parse_args()
    rows = read_rows(args.input)
    issues = [
        build_issue(row)
        for row in rows
        if (row.get("Issue Type") or "").strip() == "Requirement"
    ]
    enrich_epic_names(issues, rows)
    remapped = apply_build_type_rules(issues)
    sp_tbd = apply_sp_rules(issues)
    field_meta = analyze_fields(issues)
    html_out = generate_html(issues, field_meta, args.input)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as file_obj:
        file_obj.write(html_out)
    print(
        f"Estimates dashboard written: {os.path.abspath(args.output)} "
        f"({len(issues)} requirements, {remapped['integrations_mulesoft']} Integrations → Custom:Mulesoft, "
        f"{remapped['ootb_rename']} OOTB Config → Salesforce : OOTB Config, "
        f"{sp_tbd} External/ISV → SP TBD)"
    )


if __name__ == "__main__":
    main()
