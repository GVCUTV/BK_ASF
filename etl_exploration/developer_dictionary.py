# // v1.3C-Data-List
# // file: developer_dictionary.py
"""Developer reference builder merging JIRA and GitHub identities."""
# // DoD:
# // - Aggregate developers across sources with activity statistics.
# // - Provide deterministic identifiers for downstream analytics.
# // - Offer CSV export utility used by the CLI entrypoint.

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class DeveloperRecord:
    """Tabular representation of a developer across data sources."""

    developer_id: str
    jira_user: Optional[str]
    github_user: Optional[str]
    first_activity: Optional[str]
    last_activity: Optional[str]
    issue_count: int
    commit_count: int


class DeveloperDictionaryBuilder:
    """Combine developer information from JIRA and GitHub exports."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def build(self, jira_df: pd.DataFrame, github_df: pd.DataFrame) -> pd.DataFrame:
        """Return the unified developer reference table."""

        registry: Dict[str, DeveloperRecord] = {}

        def key_for(name: Optional[str]) -> Optional[str]:
            if name is None:
                return None
            normalized = name.strip().lower()
            return normalized or None

        def ensure_record(identifier: str) -> DeveloperRecord:
            if identifier not in registry:
                developer_id = f"DEV{len(registry) + 1:04d}"
                registry[identifier] = DeveloperRecord(
                    developer_id=developer_id,
                    jira_user=None,
                    github_user=None,
                    first_activity=None,
                    last_activity=None,
                    issue_count=0,
                    commit_count=0,
                )
            return registry[identifier]

        # Populate from JIRA assignments
        if not jira_df.empty:
            self._logger.info("Aggregating JIRA developers from %s issues", len(jira_df))
            for _, row in jira_df.iterrows():
                assignee = _normalize_optional(row.get("assignee"))
                if assignee is None:
                    continue
                identifier = key_for(assignee) or f"jira::{assignee}"
                record = ensure_record(identifier)
                record.jira_user = record.jira_user or assignee
                assignment_date = _normalize_optional(row.get("assignment_date"))
                close_date = _normalize_optional(row.get("close_date"))
                record.first_activity = _min_non_null(record.first_activity, assignment_date)
                record.last_activity = _max_non_null(record.last_activity, close_date or assignment_date)
                record.issue_count += 1

        # Populate from GitHub commits
        if not github_df.empty:
            self._logger.info("Aggregating GitHub developers from %s commits", len(github_df))
            for _, row in github_df.iterrows():
                author = _normalize_optional(row.get("author"))
                if author is None:
                    continue
                identifier = key_for(author) or f"github::{author}"
                record = registry.get(identifier)
                if record is None:
                    record = ensure_record(identifier)
                record.github_user = record.github_user or author
                commit_date = _normalize_optional(row.get("commit_date"))
                record.first_activity = _min_non_null(record.first_activity, commit_date)
                record.last_activity = _max_non_null(record.last_activity, commit_date)
                record.commit_count += 1

        if not registry:
            return pd.DataFrame(
                columns=[
                    "developer_id",
                    "jira_user",
                    "github_user",
                    "first_activity",
                    "last_activity",
                    "issue_count",
                    "commit_count",
                ]
            )

        records: List[DeveloperRecord] = sorted(
            registry.values(), key=lambda entry: entry.developer_id
        )
        df = pd.DataFrame([record.__dict__ for record in records])
        df.sort_values("developer_id", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    @staticmethod
    def export_csv(df: pd.DataFrame, path: str) -> None:
        """Persist the developer dictionary as CSV."""

        dataframe = pd.DataFrame(df)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open("w", encoding="utf-8") as handle:
            handle.write("// v1.3C-Data-List\n")
            handle.write("// file: data/exploration/developers.csv\n")
            handle.write("// DoD: merged developer identities across sources.\n")
            dataframe.to_csv(handle, index=False)


def _min_non_null(current: Optional[str], candidate: Optional[str]) -> Optional[str]:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return candidate if candidate < current else current


def _max_non_null(current: Optional[str], candidate: Optional[str]) -> Optional[str]:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return candidate if candidate > current else current


def _normalize_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


__all__ = ["DeveloperDictionaryBuilder", "DeveloperRecord"]
