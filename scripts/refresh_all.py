"""Export latest Jira data and rebuild all WFM hub dashboards."""

from __future__ import annotations

import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WFM_HUB = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_CSV = os.path.join(_WFM_HUB, "data", "created_since_2025-01-01_all_fields.csv")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=_WFM_HUB)


def main() -> None:
    python = sys.executable
    run([python, os.path.join(_SCRIPT_DIR, "export_jira_csv.py"), "--output", _CSV])
    run([python, os.path.join(_SCRIPT_DIR, "build_estimates_dashboard.py"), "--input", _CSV])
    run([python, os.path.join(_SCRIPT_DIR, "build_requirements_executive.py"), "--input", _CSV])
    run([python, os.path.join(_SCRIPT_DIR, "build_sprint_progress.py"), "--input", _CSV])
    print("Refresh complete.", flush=True)


if __name__ == "__main__":
    main()
