# // v1.3C-Data-List
# // file: validation.py
"""Cross-source validation and reporting utilities."""
# // DoD:
# // - Compute dataset health metrics for JIRA and GitHub exploration outputs.
# // - Emit deterministic JSON reports consumed by documentation generation.
# // - Provide helper functions reused by the CLI entrypoint.

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

import pandas as pd


def summarize_datasets(
    jira_df: pd.DataFrame, github_df: pd.DataFrame, developers_df: pd.DataFrame
) -> Dict[str, int]:
    """Compute summary metrics describing cross-source consistency."""

    total_issues = int(len(jira_df))
    total_commits = int(len(github_df))
    total_developers = int(len(developers_df))

    issue_keys = set(jira_df["issue_key"]) if not jira_df.empty else set()
    commit_issue_keys = set(github_df["issue_key"]) if not github_df.empty else set()

    matched_commits = len(issue_keys & commit_issue_keys)
    issues_without_commits = total_issues - matched_commits
    issues_without_assignee = int(jira_df["assignee"].isna().sum()) if not jira_df.empty else 0

    summary = {
        "total_issues": total_issues,
        "total_commits": total_commits,
        "total_developers": total_developers,
        "issues_with_commits": matched_commits,
        "issues_without_commits": issues_without_commits,
        "issues_without_assignee": issues_without_assignee,
    }

    if not github_df.empty:
        summary["commits_with_multiple_issues"] = int(
            github_df.groupby("commit_sha")["issue_key"].nunique().gt(1).sum()
        )
    else:
        summary["commits_with_multiple_issues"] = 0

    return summary


def write_report(summary: Dict[str, int], path: Path, logger: logging.Logger) -> None:
    """Persist the summary report to disk as JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("// v1.3C-Data-List\n")
        handle.write("// file: data/exploration/report.json\n")
        handle.write("// DoD: cross-source validation metrics for exploration outputs.\n")
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    logger.info("Wrote exploration report: %s", path)


__all__ = ["summarize_datasets", "write_report"]
