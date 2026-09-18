"""Build WFMSprintProgress.html — sprint delivery progress (requirements + stories)."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import build_estimates_dashboard as bed

_WFM_HUB = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_DEFAULT_CSV = bed._DEFAULT_CSV
JIRA_BASE = bed.JIRA_BASE

SPRINT_COL = "Sprint (customfield_10020)"
LINKED_COL = "Linked Issues"
SP_COL = "Story Points (customfield_10038)"
SP_EST_COL = "Story point estimate (customfield_10016)"


def row_story_points(row: Dict[str, str]) -> Optional[float]:
    points = bed.parse_story_points(row.get(SP_COL, ""))
    if points is None:
        points = bed.parse_story_points(row.get(SP_EST_COL, ""))
    return points


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WFMSprintProgress.html from Jira CSV.")
    parser.add_argument("--input", default=_DEFAULT_CSV, help="Jira all-fields CSV path.")
    parser.add_argument(
        "--output",
        default=os.path.join(_WFM_HUB, "WFMSprintProgress.html"),
        help="Output HTML path.",
    )
    return parser.parse_args()


def parse_sprint_names(raw: str) -> List[str]:
    text = (raw or "").strip()
    if not text:
        return []
    names = re.findall(r'"name"\s*:\s*"([^"]+)"', text)
    if names:
        return names
    return [text]


def sprint_sort_key(name: str) -> tuple:
    match = re.search(r"(\d+)\s*$", name)
    if match:
        return (0, int(match.group(1)), name.lower())
    return (1, 0, name.lower())


def parent_requirement_key(row: Dict[str, str], by_key: Dict[str, Dict[str, str]]) -> Optional[str]:
    raw = row.get(LINKED_COL) or ""
    if not raw:
        return None
    for part in raw.split('"name": "Parent-Child"')[1:]:
        inward = re.search(
            r'"inwardIssue"\s*:\s*\{[^}]*"key"\s*:\s*"(CC11004929-\d+)"',
            part,
        )
        if inward:
            key = inward.group(1)
            if by_key.get(key, {}).get("Issue Type") == "Requirement":
                return key
        outward = re.search(
            r'"outwardIssue"\s*:\s*\{[^}]*"key"\s*:\s*"(CC11004929-\d+)"',
            part,
        )
        if outward:
            key = outward.group(1)
            if by_key.get(key, {}).get("Issue Type") == "Requirement":
                return key
    return None


def story_record(row: Dict[str, str], requirement_key: Optional[str]) -> Dict[str, Any]:
    points = row_story_points(row)
    return {
        "key": bed.clean_text(row.get("issue_key", "")),
        "summary": bed.clean_text(row.get("Summary", ""), 500),
        "status": bed.clean_text(row.get("Status", "")),
        "assignee": bed.clean_text(row.get("Assignee", "")),
        "story_points": points,
        "requirement_key": requirement_key or "",
        "sprints": parse_sprint_names(row.get(SPRINT_COL, "")),
    }


def requirement_record(row: Dict[str, str]) -> Dict[str, Any]:
    points = row_story_points(row)
    return {
        "key": bed.clean_text(row.get("issue_key", "")),
        "summary": bed.clean_text(row.get("Summary", ""), 500),
        "status": bed.clean_text(row.get("Status", "")),
        "epic_name": bed.clean_text(row.get("Epic Name (customfield_10011)", "")),
        "fix_versions": bed.clean_text(row.get("Fix versions", "")),
        "business_units": bed.clean_text(row.get("Business Unit(s) (customfield_10099)", "")),
        "assignee": bed.clean_text(row.get("Assignee", "")),
        "story_points": points,
    }


def build_sprint_payload(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    by_key = {row.get("issue_key", ""): row for row in rows if row.get("issue_key")}
    requirements: Dict[str, Dict[str, Any]] = {}
    stories: List[Dict[str, Any]] = []

    for row in rows:
        if row.get("Issue Type") == "Requirement":
            key = row.get("issue_key", "")
            if key:
                requirements[key] = requirement_record(row)

    sprint_names: set[str] = set()
    sprint_req_stories: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    sprint_orphans: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        if row.get("Issue Type") != "Story":
            continue
        req_key = parent_requirement_key(row, by_key)
        story = story_record(row, req_key)
        stories.append(story)
        for sprint in story["sprints"]:
            sprint_names.add(sprint)
            if req_key:
                sprint_req_stories[sprint][req_key].append(story)
            else:
                sprint_orphans[sprint].append(story)

    sprints_sorted = sorted(sprint_names, key=sprint_sort_key)
    sprint_blocks: List[Dict[str, Any]] = []

    for sprint in sprints_sorted:
        req_blocks: List[Dict[str, Any]] = []
        for req_key in sorted(sprint_req_stories[sprint].keys()):
            req_row = requirements.get(req_key)
            if not req_row:
                req_row = {
                    "key": req_key,
                    "summary": bed.clean_text(by_key.get(req_key, {}).get("Summary", ""), 500),
                    "status": bed.clean_text(by_key.get(req_key, {}).get("Status", "")),
                    "epic_name": "",
                    "fix_versions": "",
                    "business_units": "",
                    "assignee": bed.clean_text(by_key.get(req_key, {}).get("Assignee", "")),
                    "story_points": row_story_points(by_key.get(req_key, {})),
                }
            req_blocks.append(
                {
                    **req_row,
                    "stories": sprint_req_stories[sprint][req_key],
                }
            )
        req_blocks.sort(key=lambda item: item.get("summary", "").lower())
        sprint_blocks.append(
            {
                "name": sprint,
                "requirements": req_blocks,
                "orphan_stories": sprint_orphans[sprint],
                "story_count": sum(len(r["stories"]) for r in req_blocks) + len(sprint_orphans[sprint]),
                "requirement_count": len(req_blocks),
            }
        )

    all_statuses = sorted(
        {s["status"] for s in stories if s.get("status")}
        | {r["status"] for r in requirements.values() if r.get("status")}
    )

    return {
        "sprints": sprint_blocks,
        "statuses": all_statuses,
        "story_total": len(stories),
        "story_in_sprint": sum(1 for s in stories if s.get("sprints")),
        "requirement_total": len(requirements),
    }


def sprint_chips_html(sprints: List[Dict[str, Any]]) -> str:
    if not sprints:
        return '<span class="muted-note">No sprint assignments found in Jira export.</span>'
    buttons: List[str] = []
    for index, sprint in enumerate(sprints):
        name = sprint["name"]
        active = " active" if index == 0 else ""
        label = f'{html.escape(name)} ({sprint["story_count"]})'
        buttons.append(
            f'<button type="button" class="filter-chip{active}" data-sprint="{html.escape(name)}">{label}</button>'
        )
    return "".join(buttons)


def generate_html(payload: Dict[str, Any], source: str) -> str:
    generated = datetime.now().strftime("%b %d, %Y %H:%M")
    source_name = html.escape(os.path.basename(source))
    sprint_blocks = payload["sprints"]
    default_sprint = sprint_blocks[0]["name"] if sprint_blocks else ""
    data_json = json.dumps(payload, separators=(",", ":"))
    chips = sprint_chips_html(sprint_blocks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sprint Progress — WFM Project</title>
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
    .nav-links {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 0 0; }}
    .nav-links a {{
      font-size: 11px; font-weight: 600; color: var(--accent); text-decoration: none;
      border: 1px solid var(--border); border-radius: 999px; padding: 6px 12px; background: var(--surface);
    }}
    .filter-panel {{
      position: sticky; top: 8px; z-index: 20; margin-top: 12px;
      background: var(--surface); border: 1px solid rgba(74,158,255,.45);
      border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,.22);
    }}
    .filter-panel-title {{ font-size: 12px; font-weight: 700; margin: 0 0 10px; letter-spacing: 0.04em; text-transform: uppercase; }}
    .filter-chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .filter-chip {{
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
      border-radius: 999px; padding: 6px 14px; font-size: 11px; font-weight: 600; cursor: pointer;
    }}
    .filter-chip.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .filter-row {{
      display: flex; align-items: flex-start; gap: 12px; padding-top: 12px; margin-top: 12px;
      border-top: 1px solid var(--border);
    }}
    .filter-label {{
      font-size: 11px; font-weight: 700; color: var(--accent); min-width: 88px; flex-shrink: 0;
      padding-top: 6px; text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .muted-note {{ color: var(--muted); font-size: 12px; }}
    .summary-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }}
    .pill {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 999px;
      padding: 6px 12px; font-size: 11px; color: var(--muted);
    }}
    .pill strong {{ color: var(--text); }}
    .panel {{
      margin-top: 12px; background: var(--surface); border: 1px solid var(--border);
      border-radius: 12px; padding: 14px 16px;
    }}
    .panel-head {{
      display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap;
      margin-bottom: 8px;
    }}
    .panel-title {{ font-size: 14px; font-weight: 700; margin: 0; }}
    .sprint-totals {{
      display: flex; flex-wrap: wrap; gap: 10px; align-items: stretch;
    }}
    .sprint-total-card {{
      background: var(--surface-2); border: 1px solid rgba(74,158,255,.35); border-radius: 10px;
      padding: 8px 14px; min-width: 140px;
    }}
    .sprint-total-card .total-label {{
      display: block; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--muted); margin-bottom: 4px;
    }}
    .sprint-total-card .total-value {{
      font-size: 20px; font-weight: 800; color: #fff; line-height: 1.1;
    }}
    .sprint-total-card .total-sub {{ font-size: 10px; color: var(--muted); margin-top: 4px; }}
    .panel-sub {{ font-size: 11px; color: var(--muted); margin-bottom: 12px; line-height: 1.45; }}
    .status-legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
    .status-chip {{
      font-size: 10px; font-weight: 700; border-radius: 999px; padding: 4px 10px; border: 1px solid var(--border);
      background: var(--surface-2); color: var(--muted);
    }}
    .req-row {{
      display: flex; align-items: stretch; gap: 0;
      border: 1px solid rgba(74,158,255,.45);
      border-left: 4px solid var(--accent);
      box-shadow: 0 0 0 1px rgba(61,214,198,.1);
      border-radius: 10px; background: var(--surface-2); margin-bottom: 12px; overflow: hidden;
    }}
    .req-left {{
      flex: 0 0 34%; min-width: 240px; max-width: 420px;
      padding: 12px 14px; border-right: 1px solid var(--border);
      background: rgba(15,20,25,.25);
    }}
    .req-right {{
      flex: 1 1 auto; padding: 12px 14px;
      display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; align-content: flex-start;
    }}
    .req-headline {{
      display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;
    }}
    .req-type-tag {{
      font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em;
      padding: 3px 8px; border-radius: 999px; background: rgba(74,158,255,.15);
      border: 1px solid rgba(74,158,255,.35); color: #93c5fd; flex-shrink: 0;
    }}
    .req-id {{
      font-size: 12px; font-weight: 800; color: var(--accent); text-decoration: none; letter-spacing: 0.02em;
    }}
    .req-id:hover {{ text-decoration: underline; color: #93c5fd; }}
    .req-title {{
      font-size: 12px; font-weight: 600; color: var(--text); line-height: 1.45; margin-top: 2px;
    }}
    .req-epic {{ font-size: 11px; font-weight: 700; color: var(--teal); line-height: 1.35; margin-top: 4px; }}
    .req-meta {{
      font-size: 10px; color: var(--muted); margin-top: 6px; display: flex; flex-wrap: wrap;
      gap: 6px 10px; align-items: center; line-height: 1.4;
    }}
    .req-meta strong {{ color: #c5d0de; font-weight: 600; }}
    .sp-compare {{
      margin-top: 10px; font-size: 22px; font-weight: 800; line-height: 1.1; color: #fff;
    }}
    .sp-compare .sp-label {{ display: block; font-size: 10px; font-weight: 700; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .sp-compare .sp-sum {{ color: var(--gold); }}
    .sp-compare .sp-est {{ color: var(--muted); font-size: 16px; font-weight: 700; }}
    .sp-compare.over {{ color: #fca5a5; }}
    .sp-compare.over .sp-sum {{ color: #f87171; }}
    .req-done {{
      margin-top: 10px; font-size: 11px; color: var(--muted);
    }}
    .req-done strong {{ color: var(--text); font-size: 13px; }}
    .progress-bar {{
      height: 8px; border-radius: 999px; background: rgba(139,156,179,.25); overflow: hidden; margin-top: 8px;
    }}
    .progress-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent), var(--teal)); }}
    .story-card {{
      display: flex; flex-direction: column; gap: 6px; padding: 10px 12px;
      border: 1px solid var(--border); border-radius: 8px; background: var(--surface);
      text-decoration: none; color: inherit; min-height: 100%;
    }}
    .story-card:hover {{ border-color: var(--accent); background: rgba(74,158,255,.08); }}
    .story-card-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }}
    .story-key {{ font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.02em; }}
    .story-sp {{ font-size: 12px; font-weight: 800; color: var(--gold); white-space: nowrap; flex-shrink: 0; }}
    .story-sp.missing {{ color: var(--muted); font-weight: 600; }}
    .story-blurb {{
      font-size: 11px; line-height: 1.45; color: var(--text);
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
    }}
    .story-meta {{ font-size: 10px; color: var(--muted); line-height: 1.4; }}
    .story-meta strong {{ color: #c5d0de; font-weight: 600; }}
    .story-foot {{ display: flex; align-items: center; justify-content: flex-start; margin-top: 2px; }}
    @media (max-width: 900px) {{
      .req-row {{ flex-direction: column; }}
      .req-left {{ flex: 1 1 auto; max-width: none; border-right: none; border-bottom: 1px solid var(--border); }}
    }}
    .status-badge {{
      display: inline-block; font-size: 10px; font-weight: 700; border-radius: 999px;
      padding: 3px 8px; border: 1px solid transparent; white-space: nowrap;
    }}
    .st-draft {{ background: rgba(139,156,179,.2); color: #c5d0de; border-color: rgba(139,156,179,.35); }}
    .st-analysis {{ background: rgba(251,191,36,.15); color: #fcd34d; border-color: rgba(251,191,36,.35); }}
    .st-ready {{ background: rgba(74,158,255,.15); color: #93c5fd; border-color: rgba(74,158,255,.35); }}
    .st-build {{ background: rgba(52,211,153,.15); color: #6ee7b7; border-color: rgba(52,211,153,.35); }}
    .st-review {{ background: rgba(167,139,250,.15); color: #c4b5fd; border-color: rgba(167,139,250,.35); }}
    .st-done {{ background: rgba(34,197,94,.18); color: #86efac; border-color: rgba(34,197,94,.35); }}
    .st-default {{ background: rgba(255,255,255,.08); color: var(--text); border-color: var(--border); }}
    .empty-state {{ color: var(--muted); font-size: 12px; padding: 16px 4px; }}
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
    .gate-btn {{ width: 100%; padding: 13px; background: #e8712a; border: none; border-radius: 8px; color: #fff; font-size: 14px; font-weight: 700; cursor: pointer; }}
    .gate-error {{ font-size: 12px; color: #f4a261; margin-top: 10px; min-height: 18px; }}
  </style>
</head>
<body>
  <div id="gate">
    <div class="gate-box">
      <div class="gate-logo">Charter &times; PwC &nbsp;<span>&#9679;</span>&nbsp; WFM Global Design</div>
      <h2>Sprint Progress</h2>
      <p>Enter the project passphrase to open<br />this page.</p>
      <div class="gate-input-wrap">
        <input id="gate-input" type="password" placeholder="Enter passphrase" autocomplete="off"
          onkeydown="if (event.key === 'Enter') gateSubmit()" />
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
          <h1>Sprint Progress</h1>
          <div class="hero-sub">Development progress by sprint · requirements in flight and user story status · generated {generated}</div>
          <div class="nav-links">
            <a href="index.html">Project Hub</a>
            <a href="WFMEstimates.html">Estimates</a>
            <a href="WFMRequirementsCapabilityMap.html">Capability Map</a>
          </div>
        </div>
        <img class="hero-charter-logo"
          src="https://corporate.charter.com/static/d617519f6e8ec1333149b2e86dd914fb/58aae/Charter_Communications_Logo_Preview_0.jpg"
          alt="Charter" />
      </div>
    </section>

    <div class="filter-panel">
      <div class="filter-panel-title">Sprint</div>
      <div class="filter-chips" id="sprintChips">{chips}</div>
      <div class="filter-row">
        <div class="filter-label">Status</div>
        <div class="filter-chips" id="storyStatusFilters"></div>
      </div>
      <div class="filter-row">
        <div class="filter-label">Assigned to</div>
        <div class="filter-chips" id="storyAssigneeFilters"></div>
      </div>
    </div>

    <div class="summary-row" id="summaryRow"></div>

    <div class="panel">
      <div class="panel-head">
        <div class="panel-title" id="sprintTitle">Sprint</div>
        <div class="sprint-totals" id="sprintTotals"></div>
      </div>
      <div class="panel-sub" id="sprintSub"></div>
      <div class="status-legend" id="statusLegend"></div>
      <div id="sprintContent"></div>
    </div>
  </div>

  <script>
    const DATA = {data_json};
    const JIRA_BASE = "{JIRA_BASE}";
    const DEFAULT_SPRINT = {json.dumps(default_sprint)};
    const HUB_KEY = "wfm_estimates_auth";
    const PASSPHRASE = "wfm";

    let selectedSprint = DEFAULT_SPRINT || (DATA.sprints[0] && DATA.sprints[0].name) || "";
    let filterStatus = "";
    let filterAssignee = "";

    function gateSubmit() {{
      const input = document.getElementById("gate-input");
      const err = document.getElementById("gate-error");
      if ((input.value || "").trim() === PASSPHRASE) {{
        sessionStorage.setItem(HUB_KEY, "1");
        document.getElementById("gate").style.display = "none";
        err.textContent = "";
      }} else {{
        err.textContent = "Incorrect passphrase.";
      }}
    }}
    if (sessionStorage.getItem(HUB_KEY) === "1") {{
      document.getElementById("gate").style.display = "none";
    }}

    function escapeHtml(value) {{
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }}

    function statusClass(status) {{
      const s = String(status || "").toLowerCase();
      if (s.includes("draft")) return "st-draft";
      if (s.includes("analysis")) return "st-analysis";
      if (s.includes("ready")) return "st-ready";
      if (s.includes("build")) return "st-build";
      if (s.includes("review")) return "st-review";
      if (s.includes("done") || s.includes("complete")) return "st-done";
      return "st-default";
    }}

    function statusBadge(status) {{
      return '<span class="status-badge ' + statusClass(status) + '">' + escapeHtml(status || "—") + '</span>';
    }}

    function isStoryDone(status) {{
      const st = String(status || "").toLowerCase();
      return st.includes("done") || st.includes("complete");
    }}

    function storyProgress(stories) {{
      if (!stories.length) return {{ pct: 0, done: 0, total: 0 }};
      const done = stories.filter(function (s) {{ return isStoryDone(s.status); }}).length;
      return {{
        pct: Math.round((done / stories.length) * 100),
        done: done,
        total: stories.length,
      }};
    }}

    function sumStoryPoints(stories) {{
      return stories.reduce(function (acc, story) {{
        const value = story.story_points;
        return acc + (typeof value === "number" && !isNaN(value) ? value : 0);
      }}, 0);
    }}

    function formatSp(value) {{
      if (value === null || value === undefined || isNaN(value)) return "—";
      const rounded = Math.round(value * 10) / 10;
      return rounded.toLocaleString(undefined, {{ maximumFractionDigits: 1 }});
    }}

    function truncateBlurb(text, maxLen) {{
      const value = String(text || "").trim();
      if (!value) return "—";
      if (value.length <= maxLen) return value;
      return value.slice(0, maxLen - 1) + "…";
    }}

    function countByStatus(stories) {{
      const counts = {{}};
      stories.forEach(function (story) {{
        const key = story.status || "—";
        counts[key] = (counts[key] || 0) + 1;
      }});
      return counts;
    }}

    function getSprintBlock() {{
      return DATA.sprints.find(function (s) {{ return s.name === selectedSprint; }});
    }}

    function storyAssigneeLabel(story) {{
      const value = String(story.assignee || "").trim();
      return value || "Unassigned";
    }}

    function collectSprintStories(block) {{
      let stories = [];
      (block.requirements || []).forEach(function (req) {{
        stories = stories.concat(req.stories || []);
      }});
      return stories.concat(block.orphan_stories || []);
    }}

    function uniqueStoryValues(stories, picker) {{
      const seen = {{}};
      stories.forEach(function (story) {{
        seen[picker(story)] = true;
      }});
      return Object.keys(seen).sort(function (a, b) {{ return a.localeCompare(b); }});
    }}

    function storyMatchesFilters(story) {{
      const status = story.status || "—";
      if (filterStatus && status !== filterStatus) return false;
      if (filterAssignee && storyAssigneeLabel(story) !== filterAssignee) return false;
      return true;
    }}

    function filterSprintBlock(block) {{
      const requirements = (block.requirements || []).map(function (req) {{
        return Object.assign({{}}, req, {{
          stories: (req.stories || []).filter(storyMatchesFilters),
        }});
      }}).filter(function (req) {{ return req.stories.length > 0; }});
      const orphanStories = (block.orphan_stories || []).filter(storyMatchesFilters);
      const storyCount = requirements.reduce(function (acc, req) {{
        return acc + req.stories.length;
      }}, 0) + orphanStories.length;
      return Object.assign({{}}, block, {{
        requirements: requirements,
        orphan_stories: orphanStories,
        requirement_count: requirements.length,
        story_count: storyCount,
      }});
    }}

    function renderFilterChipGroup(containerId, options, activeValue, dataAttr) {{
      const container = document.getElementById(containerId);
      if (!container) return;
      let html = '<button type="button" class="filter-chip' + (activeValue === "" ? " active" : "") + '" data-' + dataAttr + '="">All</button>';
      options.forEach(function (option) {{
        const active = activeValue === option ? " active" : "";
        html += '<button type="button" class="filter-chip' + active + '" data-' + dataAttr + '="' + escapeHtml(option) + '">' + escapeHtml(option) + '</button>';
      }});
      container.innerHTML = html;
    }}

    function renderStoryQuickFilters(block) {{
      if (!block) {{
        document.getElementById("storyStatusFilters").innerHTML = '<span class="muted-note">—</span>';
        document.getElementById("storyAssigneeFilters").innerHTML = '<span class="muted-note">—</span>';
        return;
      }}
      const stories = collectSprintStories(block);
      const statuses = uniqueStoryValues(stories, function (story) {{ return story.status || "—"; }});
      const assignees = uniqueStoryValues(stories, storyAssigneeLabel);
      if (filterStatus && statuses.indexOf(filterStatus) === -1) filterStatus = "";
      if (filterAssignee && assignees.indexOf(filterAssignee) === -1) filterAssignee = "";
      renderFilterChipGroup("storyStatusFilters", statuses, filterStatus, "status");
      renderFilterChipGroup("storyAssigneeFilters", assignees, filterAssignee, "assignee");
    }}

    function storiesFromBlock(block) {{
      let stories = [];
      (block.requirements || []).forEach(function (req) {{
        stories = stories.concat(req.stories || []);
      }});
      return stories.concat(block.orphan_stories || []);
    }}

    function renderSummary(block) {{
      const row = document.getElementById("summaryRow");
      if (!block) {{
        row.innerHTML = "";
        return;
      }}
      row.innerHTML =
        '<div class="pill">Requirements: <strong>' + block.requirement_count + '</strong></div>' +
        '<div class="pill">User stories: <strong>' + block.story_count + '</strong></div>' +
        '<div class="pill">Orphan stories: <strong>' + block.orphan_stories.length + '</strong></div>';
    }}

    function renderSprintTotals(block) {{
      const container = document.getElementById("sprintTotals");
      if (!container) return;
      if (!block) {{
        container.innerHTML =
          '<div class="sprint-total-card"><span class="total-label">User stories listed</span>' +
          '<span class="total-value">0</span></div>' +
          '<div class="sprint-total-card"><span class="total-label">Story points (sum)</span>' +
          '<span class="total-value">0 SP</span></div>';
        return;
      }}
      const stories = storiesFromBlock(block);
      const storyCount = stories.length;
      const spSum = sumStoryPoints(stories);
      const spMissing = stories.filter(function (s) {{ return s.story_points == null; }}).length;
      const filteredNote = (filterStatus || filterAssignee) ? " · filtered view" : "";
      const missingNote = spMissing
        ? ('<div class="total-sub">' + spMissing + " stor" + (spMissing === 1 ? "y" : "ies") + " without SP</div>")
        : "";
      container.innerHTML =
        '<div class="sprint-total-card">' +
          '<span class="total-label">User stories listed' + escapeHtml(filteredNote) + '</span>' +
          '<span class="total-value">' + storyCount + '</span>' +
        '</div>' +
        '<div class="sprint-total-card">' +
          '<span class="total-label">Story points (sum)' + escapeHtml(filteredNote) + '</span>' +
          '<span class="total-value">' + formatSp(spSum) + ' SP</span>' +
          missingNote +
        '</div>';
    }}

    function renderLegend(block) {{
      const legend = document.getElementById("statusLegend");
      let allStories = [];
      block.requirements.forEach(function (req) {{ allStories = allStories.concat(req.stories); }});
      allStories = allStories.concat(block.orphan_stories || []);
      const counts = countByStatus(allStories);
      const keys = Object.keys(counts).sort();
      legend.innerHTML = keys.map(function (status) {{
        return '<span class="status-chip">' + escapeHtml(status) + ': <strong>' + counts[status] + '</strong></span>';
      }}).join("");
    }}

    function renderStoryChips(stories) {{
      if (!stories.length) {{
        return '<div class="empty-state">No user stories in this sprint for this requirement.</div>';
      }}
      return stories.map(function (story) {{
        const spClass = story.story_points == null ? " missing" : "";
        const spText = story.story_points == null ? "SP TBD" : (formatSp(story.story_points) + " SP");
        const assignee = story.assignee ? escapeHtml(story.assignee) : "Unassigned";
        const blurb = escapeHtml(truncateBlurb(story.summary, 160));
        return '<a class="story-card" href="' + JIRA_BASE + '/browse/' + encodeURIComponent(story.key) + '" target="_blank" rel="noopener noreferrer">' +
          '<div class="story-card-head">' +
            '<span class="story-key">' + escapeHtml(story.key || "—") + '</span>' +
            '<span class="story-sp' + spClass + '">' + spText + '</span>' +
          '</div>' +
          '<div class="story-blurb">' + blurb + '</div>' +
          '<div class="story-meta"><strong>Assigned to:</strong> ' + assignee + '</div>' +
          '<div class="story-foot">' + statusBadge(story.status) + '</div>' +
        '</a>';
      }}).join("");
    }}

    function renderRequirementLeft(req) {{
      const progress = storyProgress(req.stories);
      const storySpSum = sumStoryPoints(req.stories);
      const reqEstimate = req.story_points;
      const hasEstimate = typeof reqEstimate === "number" && !isNaN(reqEstimate);
      const over = hasEstimate && storySpSum > reqEstimate;
      const spCompareClass = "sp-compare" + (over ? " over" : "");
      const estimateText = hasEstimate ? formatSp(reqEstimate) : "—";
      const assignee = req.assignee ? escapeHtml(req.assignee) : "Unassigned";
      const reqTitle = escapeHtml(req.summary || "—");
      const epicHtml = req.epic_name
        ? ('<div class="req-epic">' + escapeHtml(req.epic_name) + '</div>')
        : "";
      return '<div class="req-left">' +
        '<div class="req-headline">' +
          '<span class="req-type-tag">Requirement</span>' +
          '<a class="req-id" href="' + JIRA_BASE + '/browse/' + encodeURIComponent(req.key) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(req.key || "—") + '</a>' +
        '</div>' +
        '<div class="req-title">' + reqTitle + '</div>' +
        epicHtml +
        '<div class="req-meta">' + statusBadge(req.status) +
          (req.fix_versions ? ('<span>Fix ' + escapeHtml(req.fix_versions) + '</span>') : '') +
          '<span><strong>Assigned to:</strong> ' + assignee + '</span>' +
        '</div>' +
        '<div class="' + spCompareClass + '">' +
          '<span class="sp-label">Story SP sum vs requirement estimate</span>' +
          '<span><span class="sp-sum">' + formatSp(storySpSum) + '</span> / <span class="sp-est">' + estimateText + ' SP</span></span>' +
        '</div>' +
        '<div class="req-done"><strong>' + progress.pct + '%</strong> stories done (' + progress.done + '/' + progress.total + ')</div>' +
        '<div class="progress-bar"><div class="progress-fill" style="width:' + progress.pct + '%"></div></div>' +
      '</div>';
    }}

    function renderSprint() {{
      const rawBlock = getSprintBlock();
      renderStoryQuickFilters(rawBlock);
      const block = rawBlock ? filterSprintBlock(rawBlock) : null;
      document.getElementById("sprintTitle").textContent = selectedSprint || "No sprint selected";
      const filterNote = (filterStatus || filterAssignee)
        ? " · story filters active"
        : "";
      document.getElementById("sprintSub").textContent = rawBlock
        ? ("Source: {source_name} · stories assigned via Jira Sprint field · requirements linked Parent-Child from stories" + filterNote)
        : "No sprint data in export.";
      renderSummary(block);
      renderSprintTotals(block);
      renderLegend(block || {{ requirements: [], orphan_stories: [] }});

      const container = document.getElementById("sprintContent");
      if (!rawBlock) {{
        container.innerHTML = '<div class="empty-state">No stories are assigned to a sprint in the current export.</div>';
        return;
      }}
      if (!block || (!block.requirements.length && !block.orphan_stories.length)) {{
        container.innerHTML = '<div class="empty-state">No stories match the selected Status / Assigned to filters.</div>';
        return;
      }}

      let html = "";
      block.requirements.forEach(function (req) {{
        html += '<div class="req-row">' +
          renderRequirementLeft(req) +
          '<div class="req-right">' + renderStoryChips(req.stories) + '</div>' +
        '</div>';
      }});

      if (block.orphan_stories && block.orphan_stories.length) {{
        html += '<div class="req-row">' +
          '<div class="req-left">' +
            '<div class="req-epic">Unlinked stories</div>' +
            '<div class="req-meta"><span>No requirement Parent-Child link</span></div>' +
          '</div>' +
          '<div class="req-right">' + renderStoryChips(block.orphan_stories) + '</div>' +
        '</div>';
      }}

      container.innerHTML = html || '<div class="empty-state">No requirements or stories for this sprint.</div>';
    }}

    document.getElementById("sprintChips").addEventListener("click", function (event) {{
      const btn = event.target.closest(".filter-chip");
      if (!btn) return;
      selectedSprint = btn.dataset.sprint || "";
      filterStatus = "";
      filterAssignee = "";
      document.querySelectorAll("#sprintChips .filter-chip").forEach(function (chip) {{
        chip.classList.toggle("active", chip === btn);
      }});
      renderSprint();
    }});

    document.getElementById("storyStatusFilters").addEventListener("click", function (event) {{
      const btn = event.target.closest(".filter-chip");
      if (!btn) return;
      filterStatus = btn.dataset.status || "";
      renderSprint();
    }});

    document.getElementById("storyAssigneeFilters").addEventListener("click", function (event) {{
      const btn = event.target.closest(".filter-chip");
      if (!btn) return;
      filterAssignee = btn.dataset.assignee || "";
      renderSprint();
    }});

    renderSprint();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    rows = bed.read_rows(args.input)
    payload = build_sprint_payload(rows)
    html_out = generate_html(payload, args.input)
    with open(args.output, "w", encoding="utf-8") as file_obj:
        file_obj.write(html_out)
    sprint_count = len(payload["sprints"])
    story_in_sprint = sum(s["story_count"] for s in payload["sprints"])
    print(
        f"Sprint progress page written: {args.output} "
        f"({sprint_count} sprints, {story_in_sprint} sprint-assigned stories)"
    )


if __name__ == "__main__":
    main()
