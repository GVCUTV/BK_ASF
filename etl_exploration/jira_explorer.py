# // v1.3C-Data-List
# // file: jira_explorer.py
"""Utilities to collect and normalize JIRA issue metadata."""
# // DoD:
# // - Provide a `JiraExplorer` capable of loading data from cache or remote API.
# // - Compute assignment/close timestamps per Section 3.2 A business rules.
# // - Export normalized issue metadata as a :class:`pandas.DataFrame`.

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import requests

from .config import ExplorationConfig


ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
)


@dataclass
class JiraIssueRecord:
    """Normalized representation of a JIRA issue."""

    issue_key: str
    assignee: Optional[str]
    assignment_date: Optional[str]
    close_date: Optional[str]
    status: Optional[str]
    changelog_count: int


class JiraExplorer:
    """Encapsulates JIRA API access, caching, and normalization."""

    def __init__(self, config: ExplorationConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self._session = requests.Session()
        if config.jira_user and config.jira_token:
            self._session.auth = (config.jira_user, config.jira_token)
        self._session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_issues(self, refresh: bool = False) -> List[dict]:
        """Load raw JIRA payloads from cache or API."""

        cache_path = self._config.jira_cache_path
        if cache_path.exists() and not refresh:
            self._logger.info("Loading JIRA issues from cache: %s", cache_path)
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        if not self._config.jira_user or not self._config.jira_token:
            self._logger.warning(
                "JIRA credentials missing; returning cached data if available."
            )
            return []

        payloads: List[dict] = []
        start_at = 0
        total = None
        self._logger.info("Fetching JIRA issues via REST API")

        while True:
            params = {
                "jql": f"project={self._config.jira_project_key}",
                "expand": "changelog",
                "startAt": start_at,
                "maxResults": min(100, self._config.max_issues - start_at),
            }
            if params["maxResults"] <= 0:
                break
            try:
                response = self._session.get(
                    f"{self._config.jira_base_url}/rest/api/3/search",
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                self._logger.error("Failed to fetch JIRA issues: %s", exc)
                break

            data = response.json()
            issues = data.get("issues", [])
            payloads.extend(issues)
            total = data.get("total", len(payloads))
            start_at += len(issues)
            self._logger.info(
                "Retrieved %s JIRA issues (startAt=%s)", len(issues), start_at
            )
            if not issues or start_at >= min(total, self._config.max_issues):
                break

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payloads, handle, indent=2)
        self._logger.info("Persisted JIRA cache to %s", cache_path)
        return payloads

    def to_dataframe(self, payloads: Iterable[dict]) -> pd.DataFrame:
        """Transform raw payloads into a normalized DataFrame."""

        records = [self._normalize_issue(issue) for issue in payloads]
        df = pd.DataFrame([record.__dict__ for record in records])
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "issue_key",
                    "assignee",
                    "assignment_date",
                    "close_date",
                    "status",
                    "changelog_count",
                ]
            )

        df.sort_values("issue_key", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def export_csv(self, df: pd.DataFrame, path: Path) -> None:
        """Persist the normalized DataFrame to a CSV path."""

        path.parent.mkdir(parents=True, exist_ok=True)
        self._logger.info("Writing JIRA exploration CSV: %s", path)
        with path.open("w", encoding="utf-8") as handle:
            handle.write("// v1.3C-Data-List\n")
            handle.write("// file: data/exploration/jira_issues.csv\n")
            handle.write("// DoD: normalized JIRA issue export.\n")
            df.to_csv(handle, index=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _normalize_issue(self, issue: dict) -> JiraIssueRecord:
        fields = issue.get("fields", {})
        issue_key = issue.get("key")
        assignee_info = fields.get("assignee") or {}
        assignee = assignee_info.get("displayName") or assignee_info.get("name")
        changelog_entries = (issue.get("changelog") or {}).get("histories", []) or []

        assignment_date = self._extract_assignment(changelog_entries, fields)
        close_date = self._extract_close(changelog_entries, fields)
        status_info = fields.get("status") or {}
        status = status_info.get("name") or status_info.get("statusCategory", {}).get("name")

        return JiraIssueRecord(
            issue_key=issue_key,
            assignee=assignee,
            assignment_date=assignment_date,
            close_date=close_date,
            status=status,
            changelog_count=len(changelog_entries),
        )

    def _extract_assignment(self, histories: Iterable[dict], fields: dict) -> Optional[str]:
        timestamps: List[datetime] = []
        for history in histories:
            for item in history.get("items", []) or []:
                if (item.get("field") or "").lower() == "assignee":
                    ts = parse_datetime(history.get("created"))
                    if ts is not None:
                        timestamps.append(ts)
        if timestamps:
            return max(timestamps).isoformat()
        created = parse_datetime(fields.get("created"))
        return created.isoformat() if created else None

    def _extract_close(self, histories: Iterable[dict], fields: dict) -> Optional[str]:
        resolution_date = parse_datetime(fields.get("resolutiondate"))
        if resolution_date is not None:
            return resolution_date.isoformat()

        terminal_statuses = {status.lower() for status in self._config.terminal_statuses}
        close_times: List[datetime] = []
        for history in histories:
            created = parse_datetime(history.get("created"))
            if created is None:
                continue
            for item in history.get("items", []) or []:
                if (item.get("field") or "").lower() == "status":
                    to_state = (item.get("toString") or "").lower()
                    if to_state in terminal_statuses:
                        close_times.append(created)
        if close_times:
            return max(close_times).isoformat()
        return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO-like strings returned by JIRA into aware datetimes."""

    if not value:
        return None
    for fmt in ISO_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    # Attempt a fallback using fromisoformat after tidying timezone
    try:
        if value[-5] in "+-" and value[-3] != ":":
            value = value[:-2] + ":" + value[-2:]
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:  # noqa: BLE001 - defensive parse fallback
        return None


__all__ = ["JiraExplorer", "parse_datetime", "JiraIssueRecord"]
