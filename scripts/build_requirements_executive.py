"""Build WFMRequirementsCapabilityMap.html — capability tree map view."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import build_estimates_dashboard as bed

_WFM_HUB = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_DEFAULT_CSV = bed._DEFAULT_CSV
JIRA_BASE = bed.JIRA_BASE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WFMRequirementsCapabilityMap.html from Jira CSV.")
    parser.add_argument("--input", default=_DEFAULT_CSV, help="Jira all-fields CSV path.")
    parser.add_argument(
        "--output",
        default=os.path.join(_WFM_HUB, "WFMRequirementsCapabilityMap.html"),
        help="Output HTML path.",
    )
    return parser.parse_args()


def filter_chips_html(options: List[tuple[str, str]], active: str = "") -> str:
    buttons: List[str] = []
    for value, label in options:
        active_class = " active" if value == active else ""
        buttons.append(
            f'<button type="button" class="filter-chip{active_class}" data-value="{html.escape(value)}">'
            f"{html.escape(label)}</button>"
        )
    return "".join(buttons)


def generate_html(
    issues: List[Dict[str, Any]],
    capability_tree: List[Dict[str, Any]],
    capability_parent: Dict[str, str],
    source: str,
) -> str:
    generated = datetime.now().strftime("%b %d, %Y %H:%M")
    source_name = html.escape(os.path.basename(source))
    fix_version_options = bed.field_value_options(issues, "fix_versions")
    bu_options = bed.field_value_options(issues, "business_units")
    scope_chip_options = [("", "All"), ("salesforce", "Salesforce"), ("mulesoft", "Mulesoft")]
    capability_chip_options = [("", "All")] + [
        (str(cap.get("key") or ""), str(cap.get("summary") or cap.get("key") or ""))
        for cap in capability_tree
    ]
    fix_version_chip_options = [("", "All")] + [(value, value) for value in fix_version_options]
    scope_chips = filter_chips_html(scope_chip_options)
    capability_chips = filter_chips_html(capability_chip_options)
    fix_version_chips = filter_chips_html(fix_version_chip_options)
    bu_chip_options = [("", "All")] + [(value, value) for value in bu_options]
    modal_bu_chips = filter_chips_html(bu_chip_options)
    data_json = json.dumps(
        {
            "issues": issues,
            "capabilityTree": capability_tree,
            "capabilityParent": capability_parent,
            "fixVersionOptions": fix_version_options,
            "buOptions": bu_options,
        },
        separators=(",", ":"),
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Requirements Capability Map — WFM Project</title>
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
    .hero-scope-bar {{
      margin-top: 8px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
      width: fit-content; max-width: 100%;
    }}
    .scope-badge {{
      display: inline-block; flex-shrink: 0; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2);
      border-radius: 999px; padding: 4px 10px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .nav-links {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 0 0; }}
    .nav-links a {{
      font-size: 11px; font-weight: 600; color: var(--accent); text-decoration: none;
      border: 1px solid var(--border); border-radius: 999px; padding: 6px 12px; background: var(--surface);
    }}
    .nav-links a:hover {{ border-color: var(--accent); }}
    .filter-panel {{
      position: sticky; top: 8px; z-index: 20;
      margin-top: 12px; background: var(--surface); border: 1px solid rgba(74,158,255,.45);
      border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,.22);
    }}
    .filter-panel-title {{
      font-size: 12px; font-weight: 700; color: var(--text); margin: 0 0 10px;
      letter-spacing: 0.04em; text-transform: uppercase;
    }}
    .filter-row {{
      display: flex; align-items: flex-start; gap: 12px; padding: 10px 0;
      border-top: 1px solid var(--border);
    }}
    .filter-row:first-of-type {{ border-top: none; padding-top: 0; }}
    .filter-row-duo {{
      display: flex; align-items: flex-start; gap: 24px; flex-wrap: wrap;
    }}
    .filter-group {{
      display: flex; align-items: flex-start; gap: 12px; flex: 1 1 300px; min-width: 0;
    }}
    .filter-row-duo .filter-label {{ min-width: 76px; }}
    .filter-label {{
      font-size: 11px; font-weight: 700; color: var(--accent); min-width: 88px; flex-shrink: 0;
      padding-top: 6px; text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .filter-chips {{ display: flex; flex-wrap: wrap; gap: 8px; flex: 1; min-height: 28px; }}
    .filter-chip {{
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
      border-radius: 999px; padding: 6px 14px; font-size: 11px; font-weight: 600; cursor: pointer;
    }}
    .filter-chip:hover {{ border-color: var(--accent); background: rgba(74,158,255,.12); }}
    .filter-chip.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .exec-panel {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; margin-top: 12px;
    }}
    .exec-head {{ margin-bottom: 12px; }}
    .exec-title {{ font-size: 14px; font-weight: 700; color: var(--text); }}
    .exec-sub {{ font-size: 11px; color: var(--muted); margin-top: 4px; line-height: 1.45; max-width: 860px; }}
    .exec-summary {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }}
    .exec-pill {{
      background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px;
      padding: 6px 12px; font-size: 11px; color: var(--muted);
    }}
    .exec-pill strong {{ color: var(--text); }}
    .exec-legend-feature {{ border-color: rgba(61,214,198,.45); color: #9aeae0; }}
    .exec-legend-epic {{ border-color: rgba(167,139,250,.45); color: #c4b5fd; }}
    .cap-map-wrap {{
      width: 100%; overflow-x: auto; padding: 12px 8px 16px;
      background: linear-gradient(180deg, rgba(15,20,25,.35) 0%, rgba(26,35,50,.55) 100%);
      border: 1px solid var(--border); border-radius: 10px;
    }}
    .cap-map {{ width: 100%; }}
    .cap-map-row {{ display: flex; width: 100%; align-items: flex-start; }}
    .cap-map-seg {{
      flex: 1 1 0; min-width: 0; padding: 0 6px;
      border-right: 1px solid rgba(74,93,120,.35);
    }}
    .cap-map-seg:last-child {{ border-right: none; }}
    .cap-tree {{
      display: flex; flex-direction: column; align-items: center; width: 100%;
    }}
    .cap-tree > .cap-map-card {{ width: 100%; max-width: 220px; }}
    .cap-tree-vline {{
      width: 2px; height: 20px; background: #5a7190; flex-shrink: 0;
    }}
    .cap-tree-branches {{
      display: flex; width: 100%; gap: 8px; position: relative; padding-top: 20px;
    }}
    .cap-tree-branches::before {{
      content: ""; position: absolute; top: 0; height: 2px; background: #5a7190;
      left: calc(100% / var(--branch-count) / 2);
      right: calc(100% / var(--branch-count) / 2);
    }}
    .cap-tree-branches.single {{ padding-top: 0; }}
    .cap-tree-branches.single::before {{ display: none; }}
    .cap-tree-branch {{
      flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; align-items: center;
      position: relative;
    }}
    .cap-tree-vline-in {{
      position: absolute; top: -20px; left: 50%; transform: translateX(-50%);
      width: 2px; height: 20px; background: #5a7190;
    }}
    .cap-tree-branches.single .cap-tree-vline-in {{ display: none; }}
    .cap-tree-branch > .cap-map-card {{ width: 100%; }}
    .cap-tree-epics {{
      display: flex; flex-direction: column; gap: 6px; width: 100%; align-items: stretch;
    }}
    .cap-map-layer-label {{
      font-size: 9px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase;
      color: var(--muted); text-align: center; margin: 0 0 10px;
    }}
    .cap-map-legend-row {{
      display: flex; justify-content: center; gap: 18px; flex-wrap: wrap;
      font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--muted); margin-bottom: 12px;
    }}
    .cap-map-legend-row span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .cap-map-legend-row i {{
      display: inline-block; width: 10px; height: 10px; border-radius: 2px; font-style: normal;
    }}
    .cap-map-legend-row .leg-cap {{ background: rgba(74,158,255,.45); }}
    .cap-map-legend-row .leg-feat {{ background: rgba(61,214,198,.45); }}
    .cap-map-legend-row .leg-epic {{ background: rgba(167,139,250,.45); }}
    .cap-map-card {{
      width: 100%; padding: 8px 8px 10px; background: var(--surface-2);
      border: 2px solid var(--border); border-radius: 8px; box-shadow: 0 3px 10px rgba(0,0,0,.18);
      text-align: center;
    }}
    .cap-map-card:hover {{ border-color: var(--accent); }}
    .cap-map-card.capability {{
      border-color: rgba(74,158,255,.55);
      background: linear-gradient(180deg, rgba(74,158,255,.14) 0%, var(--surface-2) 100%);
      min-height: 78px;
    }}
    .cap-map-card.feature {{
      border-color: rgba(61,214,198,.45);
      background: linear-gradient(180deg, rgba(61,214,198,.1) 0%, var(--surface-2) 100%);
      min-height: 68px;
    }}
    .cap-map-card.epic {{
      border-color: rgba(167,139,250,.45);
      background: linear-gradient(180deg, rgba(167,139,250,.1) 0%, var(--surface-2) 100%);
      min-height: 56px; padding: 6px 6px 8px;
    }}
    .cap-map-type {{
      font-size: 7px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase;
      color: var(--muted); margin-bottom: 4px;
    }}
    .cap-map-title {{
      font-size: 10px; font-weight: 600; line-height: 1.3; color: var(--text);
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
    }}
    .cap-map-card.epic .cap-map-title {{ font-size: 9px; -webkit-line-clamp: 2; }}
    .cap-map-title a {{ color: inherit; text-decoration: none; }}
    .cap-map-title a:hover {{ color: var(--accent); }}
    .cap-map-count {{
      display: inline-block; margin-top: 6px; font-size: 10px; font-weight: 800; color: #fff;
      background: var(--accent); border-radius: 999px; padding: 2px 8px; border: none;
      font-family: inherit; cursor: pointer;
    }}
    .cap-map-count:hover {{ filter: brightness(1.12); box-shadow: 0 0 0 2px rgba(74,158,255,.35); }}
    .cap-map-count.zero {{
      background: #3a4658; color: var(--muted); cursor: default; box-shadow: none;
    }}
    .cap-map-count.zero:hover {{ filter: none; box-shadow: none; }}
    .req-modal {{
      position: fixed; inset: 0; z-index: 10000; display: none; align-items: center; justify-content: center;
      padding: 20px;
    }}
    .req-modal.open {{ display: flex; }}
    .req-modal-backdrop {{
      position: absolute; inset: 0; background: rgba(8,12,18,.72); backdrop-filter: blur(2px);
    }}
    .req-modal-dialog {{
      position: relative; width: min(920px, 100%); max-height: min(80vh, 720px);
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
      box-shadow: 0 16px 48px rgba(0,0,0,.45); display: flex; flex-direction: column; overflow: hidden;
    }}
    .req-modal-head {{
      display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
      padding: 14px 16px; border-bottom: 1px solid var(--border); background: var(--surface-2);
    }}
    .req-modal-eyebrow {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
    .req-modal-title {{ font-size: 14px; font-weight: 700; color: var(--text); margin-top: 4px; line-height: 1.35; }}
    .req-modal-close {{
      border: 1px solid var(--border); background: var(--surface); color: var(--muted);
      border-radius: 8px; width: 32px; height: 32px; font-size: 20px; line-height: 1; cursor: pointer; flex-shrink: 0;
    }}
    .req-modal-close:hover {{ color: var(--text); border-color: var(--accent); }}
    .req-modal-meta {{ padding: 8px 16px; font-size: 11px; color: var(--muted); border-bottom: 1px solid var(--border); }}
    .req-modal-filters {{
      display: flex; align-items: flex-start; gap: 12px; padding: 10px 16px;
      border-bottom: 1px solid var(--border); background: rgba(15,20,25,.35);
    }}
    .req-modal-filter-label {{
      font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--accent); min-width: 88px; padding-top: 6px; flex-shrink: 0;
    }}
    .req-modal-filters .filter-chips {{ flex: 1; }}
    .req-modal-body {{ overflow: auto; padding: 0; flex: 1; min-height: 0; }}
    .req-modal-table {{ width: 100%; border-collapse: collapse; }}
    .req-modal-table th {{
      position: sticky; top: 0; background: #252f3f; padding: 8px 10px; text-align: left;
      font-size: 10px; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border);
    }}
    .req-modal-table td {{ padding: 8px 10px; font-size: 11px; border-bottom: 1px solid rgba(42,53,68,.7); vertical-align: top; }}
    .req-modal-table tr:hover {{ background: rgba(74,158,255,.06); }}
    .req-modal-table .mono {{ font-family: Consolas, monospace; font-size: 10px; }}
    .req-modal-table .mono a {{ color: var(--accent); text-decoration: none; }}
    .req-modal-empty {{ padding: 24px 16px; text-align: center; color: var(--muted); font-size: 12px; }}
    .cap-map-empty {{ padding: 14px; color: var(--muted); font-size: 12px; text-align: center; }}
    .meta-line {{ font-size: 11px; color: var(--muted); margin-top: 10px; }}
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
      <h2>Requirements Capability Map</h2>
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
          <h1>Requirements Capability Map</h1>
          <div class="hero-sub">Capability → Feature → Epic tree · requirement counts roll up · {len(issues)} requirements · generated {generated}</div>
          <div class="hero-scope-bar">
            <span class="scope-badge">Issue Type = Requirement</span>
          </div>
        </div>
        <img class="hero-charter-logo"
          src="https://corporate.charter.com/static/d617519f6e8ec1333149b2e86dd914fb/58aae/Charter_Communications_Logo_Preview_0.jpg"
          alt="Charter" />
      </div>
    </section>

    <div class="nav-links">
      <a href="index.html">&#8592; Project Hub</a>
      <a href="WFMEstimates.html">Estimates dashboard</a>
    </div>

    <section class="filter-panel" aria-label="Filters">
      <div class="filter-panel-title">Filters</div>
      <div class="filter-row filter-row-duo">
        <div class="filter-group">
          <div class="filter-label">Scope</div>
          <div class="filter-chips" id="scopeQuickFilters">{scope_chips}</div>
        </div>
        <div class="filter-group">
          <div class="filter-label">Fix version</div>
          <div class="filter-chips" id="fixVersionQuickFilters">{fix_version_chips}</div>
        </div>
      </div>
      <div class="filter-row">
        <div class="filter-label">Capability</div>
        <div class="filter-chips" id="capabilityQuickFilters">{capability_chips}</div>
      </div>
    </section>

    <div class="exec-panel">
      <div class="exec-head">
        <div class="exec-title">Capability map</div>
        <div class="exec-sub">Each capability column flows Capability → Features → Epics with connected lines · fit to width</div>
      </div>
      <div class="exec-summary">
        <div class="exec-pill">Filtered requirements: <strong id="execReqTotal">0</strong></div>
        <div class="exec-pill">Capability areas: <strong id="execCapTotal">0</strong></div>
        <div class="exec-pill">Capability</div>
        <div class="exec-pill exec-legend-feature">Feature</div>
        <div class="exec-pill exec-legend-epic">Epic / Decision</div>
      </div>
      <div class="cap-map-wrap" id="capabilityTree"></div>
      <div class="meta-line" id="metaLine"></div>
    </div>
  </div>

  <div id="reqModal" class="req-modal" aria-hidden="true">
    <div class="req-modal-backdrop" id="reqModalBackdrop"></div>
    <div class="req-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="reqModalTitle">
      <div class="req-modal-head">
        <div>
          <div class="req-modal-eyebrow">Requirements</div>
          <div class="req-modal-title" id="reqModalTitle"></div>
        </div>
        <button type="button" class="req-modal-close" id="reqModalClose" aria-label="Close">&times;</button>
      </div>
      <div class="req-modal-meta" id="reqModalMeta"></div>
      <div class="req-modal-filters">
        <div class="req-modal-filter-label">Business unit</div>
        <div class="filter-chips" id="reqModalBuFilters">{modal_bu_chips}</div>
      </div>
      <div class="req-modal-body" id="reqModalBody"></div>
    </div>
  </div>

  <script>
    const JIRA_BASE = {json.dumps(JIRA_BASE)};
    const DATA = {data_json};
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
      var val = document.getElementById("gate-input").value.trim().toLowerCase();
      if (val === HUB_PASS) {{
        sessionStorage.setItem(HUB_KEY, "1");
        var g = document.getElementById("gate");
        g.style.transition = "opacity .4s";
        g.style.opacity = "0";
        setTimeout(function () {{ g.style.display = "none"; }}, 400);
      }} else {{
        var err = document.getElementById("gate-error");
        var wrap = document.getElementById("gate-input").parentElement;
        err.textContent = "Incorrect passphrase";
        wrap.classList.remove("gate-shake");
        void wrap.offsetWidth;
        wrap.classList.add("gate-shake");
        document.getElementById("gate-input").value = "";
        document.getElementById("gate-input").focus();
      }}
    }}

    function gateToggleEye() {{
      var inp = document.getElementById("gate-input");
      inp.type = inp.type === "password" ? "text" : "password";
    }}

    function escapeHtml(text) {{
      return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }}

    let scopeFilter = "";
    let capabilityFilter = "";
    let fixVersionFilter = "";
    let lastFilteredRows = [];
    let modalNodeKey = "";
    let modalNodeTitle = "";
    let modalBuFilter = "";
    let modalBaseRows = [];

    function syncFilterActiveStates() {{
      document.querySelectorAll("#scopeQuickFilters .filter-chip").forEach(function (btn) {{
        btn.classList.toggle("active", (btn.dataset.value || "") === scopeFilter);
      }});
      document.querySelectorAll("#capabilityQuickFilters .filter-chip").forEach(function (btn) {{
        btn.classList.toggle("active", (btn.dataset.value || "") === capabilityFilter);
      }});
      document.querySelectorAll("#fixVersionQuickFilters .filter-chip").forEach(function (btn) {{
        btn.classList.toggle("active", (btn.dataset.value || "") === fixVersionFilter);
      }});
    }}

    document.querySelector(".filter-panel").addEventListener("click", function (event) {{
      const btn = event.target.closest(".filter-chip");
      if (!btn) return;
      const container = btn.closest(".filter-chips");
      if (!container) return;
      const value = btn.dataset.value || "";
      if (container.id === "scopeQuickFilters") scopeFilter = value;
      else if (container.id === "capabilityQuickFilters") capabilityFilter = value;
      else if (container.id === "fixVersionQuickFilters") fixVersionFilter = value;
      syncFilterActiveStates();
      render();
    }});

    function matchesScopeFilter(issue) {{
      const epic = String(issue.epic_name || "").trim();
      if (scopeFilter === "mulesoft") return epic === "Integrations";
      if (scopeFilter === "salesforce") return epic !== "Integrations";
      return true;
    }}

    const nodeToCapabilityRoot = {{}};
    (function indexCapabilityTree(nodes) {{
      function walk(node, rootKey) {{
        nodeToCapabilityRoot[node.key] = rootKey;
        (node.children || []).forEach(function (child) {{ walk(child, rootKey); }});
      }}
      (nodes || []).forEach(function (cap) {{ walk(cap, cap.key); }});
    }})(DATA.capabilityTree || []);

    function capabilityRootForIssue(issue) {{
      const parentOf = DATA.capabilityParent || {{}};
      let key = issue.issue_key;
      const seen = new Set();
      while (key && !seen.has(key)) {{
        seen.add(key);
        if (nodeToCapabilityRoot[key]) return nodeToCapabilityRoot[key];
        const next = parentOf[key] || (key === issue.issue_key ? (issue.wbs_parent || "") : "");
        if (!next || next === key) break;
        key = next;
      }}
      return "";
    }}

    function matchesCapabilityFilter(issue) {{
      if (!capabilityFilter) return true;
      return capabilityRootForIssue(issue) === capabilityFilter;
    }}

    function matchesFixVersionFilter(issue) {{
      if (!fixVersionFilter) return true;
      const fixVersion = String(issue.fix_versions || "").trim() || "(Blank)";
      return fixVersion === fixVersionFilter;
    }}

    const capabilityNodeKeys = new Set();
    (function collectCapabilityNodes(nodes) {{
      (nodes || []).forEach(function (node) {{
        capabilityNodeKeys.add(node.key);
        collectCapabilityNodes(node.children);
      }});
    }})(DATA.capabilityTree || []);

    function computeCapabilityCounts(filteredRows) {{
      const counts = {{}};
      capabilityNodeKeys.forEach(function (key) {{ counts[key] = 0; }});
      const parentOf = DATA.capabilityParent || {{}};
      filteredRows.forEach(function (issue) {{
        let key = issue.issue_key;
        const seen = new Set();
        while (key && !seen.has(key)) {{
          seen.add(key);
          if (capabilityNodeKeys.has(key)) counts[key] = (counts[key] || 0) + 1;
          const next = parentOf[key] || (key === issue.issue_key ? (issue.wbs_parent || "") : "");
          if (!next || next === key) break;
          key = next;
        }}
      }});
      return counts;
    }}

    function capabilityTypeClass(issueType) {{
      const t = String(issueType || "").toLowerCase();
      if (t === "capability") return "capability";
      if (t === "feature") return "feature";
      if (t === "epic") return "epic";
      return "";
    }}

    function renderCapCard(node, counts, sizeClass) {{
      const count = counts[node.key] || 0;
      const typeClass = capabilityTypeClass(node.issue_type) || sizeClass || "";
      const label = '<a href="' + JIRA_BASE + '/browse/' + encodeURIComponent(node.key) + '" target="_blank" rel="noopener noreferrer" title="' + escapeHtml(node.summary || "") + '">' +
        escapeHtml(node.summary || node.key) + '</a>';
      const countEl = count
        ? '<button type="button" class="cap-map-count" data-node-key="' + escapeHtml(node.key) + '" data-node-title="' + escapeHtml(node.summary || node.key) + '" title="View requirements">' + count + '</button>'
        : '<span class="cap-map-count zero">' + count + '</span>';
      return '<div class="cap-map-card ' + typeClass + '">' +
        '<div class="cap-map-type">' + escapeHtml(node.issue_type || "") + '</div>' +
        '<div class="cap-map-title">' + label + '</div>' +
        countEl +
      '</div>';
    }}

    function epicLevelNodes(feature) {{
      const children = feature.children || [];
      if (!children.length) return [feature];
      return children;
    }}

    function renderExecutive(filteredRows) {{
      const counts = computeCapabilityCounts(filteredRows);
      document.getElementById("execReqTotal").textContent = filteredRows.length;
      const allRoots = DATA.capabilityTree || [];
      const roots = capabilityFilter
        ? allRoots.filter(function (cap) {{ return cap.key === capabilityFilter; }})
        : allRoots;
      document.getElementById("execCapTotal").textContent = roots.length;
      document.getElementById("metaLine").textContent =
        "Source: {source_name} · showing " + filteredRows.length + " of " + DATA.issues.length + " requirements";

      if (!roots.length) {{
        document.getElementById("capabilityTree").innerHTML = '<div class="cap-map-empty">No capability tree found</div>';
        return;
      }}

      let html = '<div class="cap-map">';
      html += '<div class="cap-map-legend-row">' +
        '<span><i class="leg-cap"></i> Capability</span>' +
        '<span><i class="leg-feat"></i> Feature</span>' +
        '<span><i class="leg-epic"></i> Epic</span>' +
      '</div>';
      html += '<div class="cap-map-row">';
      roots.forEach(function (cap) {{
        const features = cap.children || [];
        html += '<div class="cap-map-seg"><div class="cap-tree">';
        html += renderCapCard(cap, counts, "capability");
        if (features.length) {{
          html += '<div class="cap-tree-vline"></div>';
          const branchClass = features.length === 1 ? "cap-tree-branches single" : "cap-tree-branches";
          html += '<div class="' + branchClass + '" style="--branch-count:' + features.length + '">';
          features.forEach(function (feat) {{
            html += '<div class="cap-tree-branch">';
            html += '<div class="cap-tree-vline-in"></div>';
            html += renderCapCard(feat, counts, "feature");
            const epics = epicLevelNodes(feat);
            if (epics.length) {{
              html += '<div class="cap-tree-vline"></div>';
              html += '<div class="cap-tree-epics">';
              epics.forEach(function (epic) {{
                html += renderCapCard(epic, counts, "epic");
              }});
              html += '</div>';
            }}
            html += '</div>';
          }});
          html += '</div>';
        }}
        html += '</div></div>';
      }});
      html += '</div></div>';
      document.getElementById("capabilityTree").innerHTML = html;
    }}

    function issueRollsUpToNode(issue, nodeKey) {{
      const parentOf = DATA.capabilityParent || {{}};
      let key = issue.issue_key;
      const seen = new Set();
      while (key && !seen.has(key)) {{
        seen.add(key);
        if (key === nodeKey) return true;
        const next = parentOf[key] || (key === issue.issue_key ? (issue.wbs_parent || "") : "");
        if (!next || next === key) break;
        key = next;
      }}
      return false;
    }}

    function requirementsForNode(nodeKey, rows) {{
      return rows.filter(function (issue) {{ return issueRollsUpToNode(issue, nodeKey); }});
    }}

    function closeReqModal() {{
      const modal = document.getElementById("reqModal");
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      modalNodeKey = "";
      modalNodeTitle = "";
      modalBuFilter = "";
      modalBaseRows = [];
    }}

    function syncModalBuFilterStates() {{
      document.querySelectorAll("#reqModalBuFilters .filter-chip").forEach(function (btn) {{
        btn.classList.toggle("active", (btn.dataset.value || "") === modalBuFilter);
      }});
    }}

    function matchesModalBuFilter(issue) {{
      if (!modalBuFilter) return true;
      const bu = String(issue.business_units || "").trim() || "(Blank)";
      return bu === modalBuFilter;
    }}

    function renderModalContent() {{
      document.getElementById("reqModalTitle").textContent = modalNodeTitle || modalNodeKey;
      const body = document.getElementById("reqModalBody");
      if (!modalBaseRows.length) {{
        document.getElementById("reqModalMeta").textContent = "0 requirements (page filters applied)";
        body.innerHTML = '<div class="req-modal-empty">No requirements roll up to this node for the current filters.</div>';
        return;
      }}
      const rows = modalBaseRows.filter(matchesModalBuFilter);
      const buLabel = modalBuFilter ? (" · " + modalBuFilter) : "";
      document.getElementById("reqModalMeta").textContent =
        rows.length + " of " + modalBaseRows.length + " requirement" + (modalBaseRows.length === 1 ? "" : "s") +
        buLabel + " (page filters applied)";
      if (!rows.length) {{
        body.innerHTML = '<div class="req-modal-empty">No requirements match the selected business unit.</div>';
        return;
      }}
      body.innerHTML =
        '<table class="req-modal-table"><thead><tr>' +
        '<th>Key</th><th>Summary</th><th>Business unit</th><th>Status</th><th>Fix version</th>' +
        '</tr></thead><tbody>' +
        rows.map(function (issue) {{
          const keyLink = '<a href="' + JIRA_BASE + '/browse/' + encodeURIComponent(issue.issue_key) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(issue.issue_key) + '</a>';
          const bu = String(issue.business_units || "").trim() || "—";
          return '<tr>' +
            '<td class="mono">' + keyLink + '</td>' +
            '<td title="' + escapeHtml(issue.summary) + '">' + escapeHtml(issue.summary) + '</td>' +
            '<td>' + escapeHtml(bu) + '</td>' +
            '<td>' + escapeHtml(issue.status || "—") + '</td>' +
            '<td>' + escapeHtml(issue.fix_versions || "—") + '</td>' +
          '</tr>';
        }}).join("") +
        '</tbody></table>';
    }}

    function openReqModal(nodeKey, nodeTitle) {{
      modalNodeKey = nodeKey;
      modalNodeTitle = nodeTitle || nodeKey;
      modalBuFilter = "";
      modalBaseRows = requirementsForNode(nodeKey, lastFilteredRows);
      syncModalBuFilterStates();
      renderModalContent();
      const modal = document.getElementById("reqModal");
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
    }}

    document.getElementById("reqModal").addEventListener("click", function (event) {{
      const buBtn = event.target.closest("#reqModalBuFilters .filter-chip");
      if (buBtn) {{
        modalBuFilter = buBtn.dataset.value || "";
        syncModalBuFilterStates();
        renderModalContent();
      }}
    }});

    document.getElementById("capabilityTree").addEventListener("click", function (event) {{
      const btn = event.target.closest(".cap-map-count[data-node-key]");
      if (!btn) return;
      event.preventDefault();
      openReqModal(btn.dataset.nodeKey, btn.dataset.nodeTitle);
    }});
    document.getElementById("reqModalClose").addEventListener("click", closeReqModal);
    document.getElementById("reqModalBackdrop").addEventListener("click", closeReqModal);
    document.addEventListener("keydown", function (event) {{
      if (event.key === "Escape") closeReqModal();
    }});

    function render() {{
      lastFilteredRows = DATA.issues.filter(function (issue) {{
        return matchesScopeFilter(issue) && matchesCapabilityFilter(issue) && matchesFixVersionFilter(issue);
      }});
      renderExecutive(lastFilteredRows);
    }}

    syncFilterActiveStates();
    render();
  </script>
</body>
</html>"""


def main() -> None:
    args = parse_args()
    rows = bed.read_rows(args.input)
    issues = [
        bed.build_issue(row)
        for row in rows
        if (row.get("Issue Type") or "").strip() == "Requirement"
    ]
    bed.enrich_epic_names(issues, rows)
    bed.apply_sp_rules(issues)
    bed.apply_build_type_rules(issues)
    capability_tree, capability_parent = bed.build_capability_tree(rows)
    bed.enrich_wbs_parent(issues, capability_parent)
    html_out = generate_html(issues, capability_tree, capability_parent, args.input)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as file_obj:
        file_obj.write(html_out)
    print(
        f"Requirements capability map written: {os.path.abspath(args.output)} "
        f"({len(issues)} requirements, {len(capability_tree)} capability areas)"
    )


if __name__ == "__main__":
    main()
