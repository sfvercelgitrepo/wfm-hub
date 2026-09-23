import csv
import os
from datetime import datetime
from typing import Dict, Iterable, List


def resolve_output_path(output_path: str, timestamp_output: bool) -> str:
    if not timestamp_output:
        return output_path

    root, ext = os.path.splitext(output_path)
    ext = ext or ".csv"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{root}_{stamp}{ext}"


def write_csv(output_path: str, rows: Iterable[Dict[str, object]], columns: List[str]) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {key: "" if value is None else value for key, value in row.items()}
            writer.writerow(normalized)
    return output_path
