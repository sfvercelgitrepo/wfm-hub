"""Build the Project Audit payload from the Jira CSV.

The audit page does not embed this file. api/audit.js returns it only after
the server passphrase check.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import build_estimates_dashboard as bed
import build_sprint_progress as sprint
import refresh_ui

_WFM_HUB = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_DEFAULT_OUT = os.path.join(_WFM_HUB, "api", "audit-payload.json")

ASSIGNEE_SP_TARGET = 20
FUNNEL_STATUSES = (
    "Not Started",
    "Pending Approval",
    "Acknowledge",
    "In Progress",
    "In Review",
    "Completed",
)
FUNNEL_ALIASES = {
    "not started": "Not Started",
    "pending approval": "Pending Approval",
    "acknowledge": "Acknowledge",
    "acknowledged": "Acknowledge",
    "in progress": "In Progress",
    "in review": "In Review",
    "completed": "Completed",
    "complete": "Completed",
}
RELEASES = (
    {"id": "R1", "label": "R1", "start": "2026-09-14", "end": "2027-01-31"},
    {"id": "R2", "label": "R2", "start": "2027-01-01", "end": "2027-03-31"},
)
RELEASE_IDS = {item["id"] for item in RELEASES}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Project Audit payload.")
    parser.add_argument("--input", default=sprint._DEFAULT_CSV, help="Jira all-fields CSV path.")
    parser.add_argument("--output", default=_DEFAULT_OUT, help="Output JSON path.")
    return parser.parse_args()


def is_complete_status(status: str) -> bool:
    text = (status or "").strip().lower()
    return text in {"completed", "complete"} or "completed" in text


def fix_tokens(value: str) -> List[str]:
    return [part.strip() for part in re.split(r"[,;/|]", value or "") if part.strip()]


def release_ids(value: str) -> List[str]:
    found: List[str] = []
    for token in fix_tokens(value):
        key = token.upper()
        if key in RELEASE_IDS and key not in found:
            found.append(key)
    return found


def points_of(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def sum_points(values: List[Optional[float]]) -> float:
    return round(sum(value for value in values if value is not None), 2)


def funnel_bucket(status: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", (status or "").strip().lower())
    return FUNNEL_ALIASES.get(text)


def status_funnel(requirements: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    counts = {label: 0 for label in FUNNEL_STATUSES}
    other: Counter[str] = Counter()
    for req in requirements.values():
        bucket = funnel_bucket(req.get("status") or "")
        if bucket:
            counts[bucket] += 1
            continue
        label = (req.get("status") or "").strip() or "Blank"
        other[label] += 1
    return {
        "stages": [{"label": label, "count": counts[label]} for label in FUNNEL_STATUSES],
        "other": [{"label": label, "count": count} for label, count in other.most_common()],
    }


def person_name(value: str) -> str:
    text = (value or "").strip()
    return text or "Unassigned"


def build_payload(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    by_key = {row.get("issue_key", ""): row for row in rows if row.get("issue_key")}
    requirements: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if row.get("Issue Type") != "Requirement":
            continue
        key = row.get("issue_key", "")
        if key:
            requirements[key] = sprint.requirement_record(row)

    stories_by_req: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("Issue Type") != "Story":
            continue
        req_key = sprint.parent_requirement_key(row, by_key) or ""
        story = sprint.story_record(row, req_key or None)
        if req_key:
            stories_by_req[req_key].append(story)

    release_buckets: Dict[str, List[Dict[str, Any]]] = {item["id"]: [] for item in RELEASES}
    outside: List[Dict[str, Any]] = []
    for req in requirements.values():
        ids = release_ids(req.get("fix_versions") or "")
        if not ids:
            outside.append(req)
            continue
        for release_id in ids:
            release_buckets[release_id].append(req)

    def release_summary(release: Dict[str, str], reqs: List[Dict[str, Any]]) -> Dict[str, Any]:
        points = [points_of(req.get("story_points")) for req in reqs]
        completed = [req for req in reqs if is_complete_status(req.get("status") or "")]
        completed_points = [points_of(req.get("story_points")) for req in completed]
        missing = sum(1 for value in points if value is None)
        return {
            "id": release["id"],
            "label": release["label"],
            "start": release["start"],
            "end": release["end"],
            "requirement_count": len(reqs),
            "total_sp": sum_points(points),
            "sp_missing": missing,
            "completed_count": len(completed),
            "completed_sp": sum_points(completed_points),
        }

    shared_owners: List[Dict[str, Any]] = []
    for req_key, stories in stories_by_req.items():
        by_person: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for story in stories:
            by_person[person_name(story.get("assignee") or "")].append(story)
        if len(by_person) < 2:
            continue
        req = requirements.get(req_key) or {
            "key": req_key,
            "summary": "",
            "status": "",
            "fix_versions": "",
            "story_points": None,
        }
        people = []
        for name in sorted(by_person, key=str.lower):
            owned = by_person[name]
            people.append(
                {
                    "name": name,
                    "stories": len(owned),
                    "sp": sum_points([points_of(story.get("story_points")) for story in owned]),
                }
            )
        shared_owners.append(
            {
                "key": req.get("key") or req_key,
                "summary": req.get("summary") or "",
                "status": req.get("status") or "",
                "fix_versions": req.get("fix_versions") or "",
                "story_points": points_of(req.get("story_points")),
                "story_count": len(stories),
                "assignees": people,
            }
        )
    shared_owners.sort(key=lambda item: (-item["story_count"], item.get("summary") or ""))

    sprint_payload = sprint.build_sprint_payload(rows)
    sprint_blocks = []
    for block in sprint_payload["sprints"]:
        stories: List[Dict[str, Any]] = []
        for req in block["requirements"]:
            stories.extend(req.get("stories") or [])
        stories.extend(block.get("orphan_stories") or [])
        by_person = defaultdict(list)
        story_rows = []
        for story in stories:
            name = person_name(story.get("assignee") or "")
            by_person[name].append(story)
            story_rows.append(
                {
                    "key": story.get("key") or "",
                    "summary": story.get("summary") or "",
                    "status": story.get("status") or "",
                    "assignee": name,
                    "story_points": points_of(story.get("story_points")),
                    "complete": is_complete_status(story.get("status") or ""),
                    "requirement_key": story.get("requirement_key") or "",
                }
            )
        assignees = []
        for name in sorted(by_person, key=str.lower):
            owned = by_person[name]
            assigned_sp = sum_points([points_of(story.get("story_points")) for story in owned])
            complete = [story for story in owned if is_complete_status(story.get("status") or "")]
            assignees.append(
                {
                    "name": name,
                    "stories": len(owned),
                    "sp": assigned_sp,
                    "complete_stories": len(complete),
                    "complete_sp": sum_points([points_of(story.get("story_points")) for story in complete]),
                    "target_sp": ASSIGNEE_SP_TARGET,
                    "short_sp": round(max(0, ASSIGNEE_SP_TARGET - assigned_sp), 2),
                    "meets_target": assigned_sp >= ASSIGNEE_SP_TARGET,
                }
            )
        assignees.sort(key=lambda item: (item["meets_target"], item["sp"], item["name"].lower()))
        sprint_blocks.append(
            {
                "name": block["name"],
                "story_count": len(story_rows),
                "assigned_sp": sum_points([row["story_points"] for row in story_rows]),
                "complete_stories": sum(1 for row in story_rows if row["complete"]),
                "complete_sp": sum_points([row["story_points"] for row in story_rows if row["complete"]]),
                "assignees_under_target": sum(1 for item in assignees if not item["meets_target"]),
                "assignees": assignees,
                "stories": story_rows,
            }
        )

    outside_points = [points_of(req.get("story_points")) for req in outside]
    return {
        "generated_at": refresh_ui.generated_iso_stamp(),
        "jira_base": sprint.JIRA_BASE,
        "assignee_sp_target": ASSIGNEE_SP_TARGET,
        "completed_status": "Completed",
        "status_funnel": status_funnel(requirements),
        "releases": [release_summary(item, release_buckets[item["id"]]) for item in RELEASES],
        "outside_release": {
            "requirement_count": len(outside),
            "total_sp": sum_points(outside_points),
        },
        "shared_owner_requirements": shared_owners,
        "sprints": sprint_blocks,
    }


def main() -> None:
    args = parse_args()
    rows = bed.read_rows(args.input)
    payload = build_payload(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, separators=(",", ":"))
        file_obj.write("\n")
    print(
        f"Audit payload written: {args.output} "
        f"({len(payload['releases'])} releases, "
        f"{len(payload['shared_owner_requirements'])} shared-owner requirements, "
        f"{len(payload['sprints'])} sprints)"
    )


if __name__ == "__main__":
    main()
