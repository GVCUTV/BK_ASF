# // v3
# // file: extract_assign_and_close_dates.py
import json
import csv
from pathlib import Path
from datetime import datetime

# ----------------------------------------------------------
# Configuration
# ----------------------------------------------------------
# JSON input file name (in same folder as this script)
INPUT_FILENAME = "search.json"
OUTPUT_FILENAME = "output/search_output.csv"
# Accepted names for "closed" status transitions
DONE_STATUS_NAMES = {"Closed", "Done", "Resolved"}


# ----------------------------------------------------------
# Helper functions
# ----------------------------------------------------------
def parse_iso(dt_str):
    """Parse JIRA ISO8601-like datetime string into a datetime object."""
    if not dt_str:
        return None
    try:
        # Normalize timezone format (+0000 → +00:00) for fromisoformat
        if dt_str[-5] in ["+", "-"] and dt_str[-3] != ":":
            dt_str = dt_str[:-2] + ":" + dt_str[-2:]
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


def get_assignment_date(issue):
    """Compute the assignment date per user rules."""
    created = issue.get("fields", {}).get("created")
    histories = issue.get("changelog", {}).get("histories", []) or []

    # collect all 'assignee' change timestamps
    changes = [
        h.get("created")
        for h in histories
        if any(it.get("field") == "assignee" for it in h.get("items", []))
    ]

    if not changes:
        return created  # no assignee change → use creation date

    changes.sort(key=lambda s: parse_iso(s) or s)
    return changes[-1]


def get_close_date(issue):
    """Find the close date (status → closed/done/resolved, else resolutiondate)."""
    fields = issue.get("fields", {}) or {}
    histories = issue.get("changelog", {}).get("histories", []) or []

    closed_times = []
    for h in histories:
        for it in h.get("items", []) or []:
            if it.get("field") == "status" and (it.get("toString") or "") in DONE_STATUS_NAMES:
                closed_times.append(h.get("created"))

    if closed_times:
        closed_times.sort(key=lambda s: parse_iso(s) or s)
        return closed_times[-1]

    return fields.get("resolutiondate")  # fallback


# ----------------------------------------------------------
# Main execution
# ----------------------------------------------------------
def main():
    base_path = Path(__file__).resolve().parent
    json_path = base_path / INPUT_FILENAME
    out_path = base_path / OUTPUT_FILENAME

    if not json_path.exists():
        print(f"❌ Input file not found: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    issues = data.get("issues", []) or []

    with open(out_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["issue_key", "assignment_date", "close_date"])

        for issue in issues:
            key = issue.get("key")
            assign_date = get_assignment_date(issue)
            close_date = get_close_date(issue)
            writer.writerow([key, assign_date or "", close_date or ""])

    print(f"✅ Extracted {len(issues)} issues.")
    print(f"📄 CSV written to: {out_path}")


if __name__ == "__main__":
    main()
