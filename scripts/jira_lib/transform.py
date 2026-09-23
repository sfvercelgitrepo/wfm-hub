from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

import yaml

PRIORITY_FIELD_IDS = (
    "issue_key",
    "issue_id",
    "summary",
    "description",
    "project",
    "issuetype",
    "status",
    "priority",
    "assignee",
    "reporter",
    "creator",
    "created",
    "updated",
    "duedate",
    "labels",
    "parent",
    "components",
    "fixVersions",
    "versions",
    "resolution",
    "resolutiondate",
    "timespent",
    "timeestimate",
    "timeoriginalestimate",
    "aggregatetimespent",
    "aggregatetimeestimate",
    "aggregatetimeoriginalestimate",
    "workratio",
    "watches",
    "comment",
    "attachment",
    "subtasks",
    "issuelinks",
)


def _sanitize_column(name: str) -> str:
    cleaned = re.sub(r"[\r\n\t]", " ", name).strip()
    return cleaned or "field"


def build_field_column_map(field_defs: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map Jira field id -> CSV column header."""
    labels: Dict[str, int] = {}
    column_map: Dict[str, str] = {}

    for field_def in field_defs:
        field_id = str(field_def.get("id", "")).strip()
        if not field_id:
            continue
        label = _sanitize_column(str(field_def.get("name", field_id)))
        count = labels.get(label, 0) + 1
        labels[label] = count
        if field_id.startswith("customfield_") or count > 1:
            column_map[field_id] = f"{label} ({field_id})"
        else:
            column_map[field_id] = label
    return column_map


def serialize_jira_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [serialize_jira_value(item) for item in value]
        return "; ".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("displayName", "name", "value", "key", "emailAddress"):
            if key in value and value[key] not in (None, ""):
                return str(value[key])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def flatten_issue_fields(
    issue: Dict[str, Any],
    field_columns: Dict[str, str],
) -> Dict[str, str]:
    row: Dict[str, str] = {
        "issue_key": str(issue.get("key", "") or ""),
        "issue_id": str(issue.get("id", "") or ""),
    }
    fields = issue.get("fields", {})
    if not isinstance(fields, dict):
        return row

    for field_id, value in fields.items():
        column = field_columns.get(field_id, field_id)
        row[column] = serialize_jira_value(value)
    return row


def collect_all_field_columns(
    issues: Iterable[Dict[str, Any]],
    field_columns: Dict[str, str],
) -> List[str]:
    seen: Dict[str, None] = {"issue_key": None, "issue_id": None}
    priority = {field_id: index for index, field_id in enumerate(PRIORITY_FIELD_IDS)}

    for issue in issues:
        fields = issue.get("fields", {})
        if not isinstance(fields, dict):
            continue
        for field_id in fields:
            column = field_columns.get(field_id, field_id)
            seen[column] = None

    def sort_key(column: str) -> tuple:
        if column == "issue_key":
            return (0, 0)
        if column == "issue_id":
            return (0, 1)
        field_id = next((fid for fid, col in field_columns.items() if col == column), column)
        if field_id in priority:
            return (1, priority[field_id])
        return (2, column.lower())

    return sorted(seen.keys(), key=sort_key)


def issues_to_all_field_rows(
    issues: List[Dict[str, Any]],
    field_defs: List[Dict[str, Any]],
) -> tuple[List[str], List[Dict[str, str]]]:
    field_columns = build_field_column_map(field_defs)
    columns = collect_all_field_columns(issues, field_columns)
    rows = [flatten_issue_fields(issue, field_columns) for issue in issues]
    return columns, rows


def _safe_get(data: Dict[str, Any], path: str, default: str = "") -> Any:
    if not path:
        return default

    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return default

    if current is None:
        return default
    return current


def _extract_story_points(fields: Dict[str, Any]) -> Any:
    # Common Jira custom field ids for story points vary by project.
    for key in ("customfield_10016", "customfield_10026"):
        if fields.get(key) is not None:
            return fields.get(key)
    return ""


def _extract_sprint(fields: Dict[str, Any]) -> str:
    for key in ("customfield_10020", "customfield_10010"):
        sprint_value = fields.get(key)
        if sprint_value:
            if isinstance(sprint_value, list):
                names = [item.get("name", "") for item in sprint_value if isinstance(item, dict)]
                return ", ".join([name for name in names if name])
            if isinstance(sprint_value, dict):
                return sprint_value.get("name", "")
            return str(sprint_value)
    return ""


def _extract_epic_key(fields: Dict[str, Any]) -> str:
    for key in ("customfield_10014", "customfield_10008"):
        value = fields.get(key)
        if value:
            return str(value)
    parent = fields.get("parent", {})
    if isinstance(parent, dict):
        return parent.get("key", "")
    return ""


def normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    fields = issue.get("fields", {})

    labels = fields.get("labels", [])
    labels_str = ", ".join(labels) if isinstance(labels, list) else str(labels or "")

    normalized = {
        "issue_key": issue.get("key", ""),
        "summary": fields.get("summary", ""),
        "project_key": _safe_get(fields, "project.key", ""),
        "issue_type": _safe_get(fields, "issuetype.name", ""),
        "status": _safe_get(fields, "status.name", ""),
        "priority": _safe_get(fields, "priority.name", ""),
        "assignee": _safe_get(fields, "assignee.displayName", ""),
        "reporter": _safe_get(fields, "reporter.displayName", ""),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "due_date": fields.get("duedate", ""),
        "story_points": _extract_story_points(fields),
        "labels": labels_str,
        "sprint": _extract_sprint(fields),
        "epic_key": _extract_epic_key(fields),
    }
    return normalized


def load_mapping(mapping_path: str) -> List[Dict[str, Any]]:
    with open(mapping_path, "r", encoding="utf-8") as file_obj:
        payload = yaml.safe_load(file_obj) or {}

    columns = payload.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("Mapping file must define a non-empty 'columns' list.")

    for column in columns:
        if not isinstance(column, dict) or "name" not in column:
            raise ValueError("Each mapping column must include at least a 'name' key.")
        column.setdefault("source", column["name"])
        column.setdefault("default", "")
    return columns


def map_record(record: Dict[str, Any], columns: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for column in columns:
        name = column["name"]
        source = column.get("source", name)
        default = column.get("default", "")
        value = _safe_get(record, source, default)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        output[name] = value if value is not None else default
    return output
