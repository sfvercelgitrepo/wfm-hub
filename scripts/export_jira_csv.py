"""Export Jira issues to all-fields CSV for dashboard rebuilds."""

from __future__ import annotations

import argparse
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from jira_lib.csv_writer import write_csv
from jira_lib.jira_client import ALL_JIRA_FIELDS, JiraClient
from jira_lib.transform import issues_to_all_field_rows

_WFM_HUB = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_DEFAULT_OUTPUT = os.path.join(_WFM_HUB, "data", "created_since_2025-01-01_all_fields.csv")
_DEFAULT_JQL = "createdDate >= 2025-01-01 ORDER BY created DESC"


def _ssl_verify_from_env():
    bundle = os.getenv("JIRA_CA_BUNDLE", "").strip()
    if bundle:
        return bundle
    flag = os.getenv("JIRA_SSL_VERIFY", "true").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def read_env() -> dict:
    required_vars = ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
    values = {key: os.getenv(key, "").strip() for key in required_vars}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError("Missing required environment variables: " + ", ".join(missing))
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Jira issues to all-fields CSV.")
    parser.add_argument("--jql", default=_DEFAULT_JQL, help="Jira JQL query.")
    parser.add_argument("--output", default=_DEFAULT_OUTPUT, help="CSV output path.")
    parser.add_argument("--page-size", type=int, default=100, help="Jira page size.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = read_env()
    client = JiraClient(
        base_url=env["JIRA_BASE_URL"],
        email=env["JIRA_EMAIL"],
        api_token=env["JIRA_API_TOKEN"],
        ssl_verify=_ssl_verify_from_env(),
    )
    issues = client.search_issues(
        jql=args.jql,
        page_size=args.page_size,
        fields=ALL_JIRA_FIELDS,
    )
    field_defs = client.list_fields()
    output_columns, mapped_rows = issues_to_all_field_rows(issues, field_defs)
    write_csv(args.output, mapped_rows, output_columns)
    print(f"Export complete: {args.output} ({len(mapped_rows)} issues)")


if __name__ == "__main__":
    main()
