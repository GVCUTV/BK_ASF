# // v1.3C-Data-List
# // file: github_explorer.py
"""Utilities to extract GitHub commit metadata relevant for analysis."""
# // DoD:
# // - Implement GitHub explorer with caching fallback and commit normalization.
# // - Detect commit references to JIRA issues via ticket identifiers.
# // - Provide CSV export compatible with downstream ETL stages.

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

import pandas as pd

try:  # pragma: no cover - dependency availability handled at runtime
    from github import Github, GithubException
except ModuleNotFoundError:  # pragma: no cover - optional dependency fallback
    Github = None  # type: ignore[assignment]

    class GithubException(Exception):
        """Fallback GithubException used when PyGithub is unavailable."""

        pass

from .config import ExplorationConfig


ISSUE_PATTERN_TEMPLATE = r"{project_key}-\d+"


@dataclass
class CommitRecord:
    """Normalized commit metadata bound to an issue key."""

    issue_key: str
    commit_sha: str
    author: Optional[str]
    commit_date: Optional[str]
    additions: int
    deletions: int
    files: str


class GitHubExplorer:
    """Handle GitHub interactions and normalization for the exploration layer."""

    def __init__(self, config: ExplorationConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self._gh = Github(config.github_token) if Github is not None else None
        self._project_key = config.jira_project_key.upper()
        self._pattern = re.compile(
            ISSUE_PATTERN_TEMPLATE.format(project_key=self._project_key),
            flags=re.IGNORECASE,
        )
        self._repo_name = self._extract_repo_name(config.github_repo_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_commits(self, refresh: bool = False) -> List[dict]:
        """Load raw commit payloads from cache or the GitHub API."""

        cache_path = self._config.github_cache_path
        if cache_path.exists() and not refresh:
            self._logger.info("Loading GitHub commits from cache: %s", cache_path)
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        if self._gh is None:
            self._logger.warning("PyGithub not available; skipping live commit fetch.")
            return []

        try:
            repo = self._gh.get_repo(self._repo_name)
        except GithubException as exc:
            self._logger.error("Unable to access repository %s: %s", self._repo_name, exc)
            return []

        commits_payload: List[dict] = []
        self._logger.info(
            "Fetching commit metadata for repo %s (max=%s)",
            self._repo_name,
            self._config.max_commits,
        )

        try:
            commits = repo.get_commits()
        except GithubException as exc:
            self._logger.error("Failed to iterate commits: %s", exc)
            return []

        for index, commit in enumerate(commits, start=1):
            if index > self._config.max_commits:
                break
            try:
                stats = commit.stats
                files = commit.files
            except GithubException as exc:
                self._logger.warning("Failed to load stats for %s: %s", commit.sha, exc)
                stats = None
                files = []

            commits_payload.append(
                {
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": (commit.commit.author.name if commit.commit.author else None),
                    "date": (
                        commit.commit.author.date.isoformat()
                        if commit.commit and commit.commit.author and commit.commit.author.date
                        else None
                    ),
                    "additions": stats.additions if stats else 0,
                    "deletions": stats.deletions if stats else 0,
                    "files": [file.filename for file in files] if files else [],
                }
            )

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(commits_payload, handle, indent=2)
        self._logger.info("Persisted GitHub cache to %s", cache_path)
        return commits_payload

    def to_dataframe(self, payloads: Iterable[dict]) -> pd.DataFrame:
        """Normalize commit payloads into a DataFrame keyed by issue."""

        rows: List[CommitRecord] = []
        for commit in payloads:
            issue_keys = sorted({key.upper() for key in self._pattern.findall(commit.get("message", ""))})
            if not issue_keys:
                continue
            files_joined = ";".join(sorted(commit.get("files", [])))
            for issue_key in issue_keys:
                rows.append(
                    CommitRecord(
                        issue_key=issue_key,
                        commit_sha=commit.get("sha"),
                        author=commit.get("author"),
                        commit_date=commit.get("date"),
                        additions=int(commit.get("additions", 0) or 0),
                        deletions=int(commit.get("deletions", 0) or 0),
                        files=files_joined,
                    )
                )

        if not rows:
            return pd.DataFrame(
                columns=[
                    "issue_key",
                    "commit_sha",
                    "author",
                    "commit_date",
                    "additions",
                    "deletions",
                    "files",
                ]
            )

        df = pd.DataFrame([row.__dict__ for row in rows])
        df.sort_values(["issue_key", "commit_date", "commit_sha"], inplace=True, na_position="last")
        df.reset_index(drop=True, inplace=True)
        return df

    def export_csv(self, df: pd.DataFrame, path: Path) -> None:
        """Persist the normalized commit table."""

        path.parent.mkdir(parents=True, exist_ok=True)
        self._logger.info("Writing GitHub exploration CSV: %s", path)
        with path.open("w", encoding="utf-8") as handle:
            handle.write("// v1.3C-Data-List\n")
            handle.write("// file: data/exploration/github_commits.csv\n")
            handle.write("// DoD: normalized commit metadata linked to issues.\n")
            df.to_csv(handle, index=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_repo_name(repo_url: str) -> str:
        """Turn a repository URL into the ``owner/name`` slug."""

        cleaned = repo_url.rstrip("/")
        parts = cleaned.split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid repository URL: {repo_url}")
        return "/".join(parts[-2:])


__all__ = ["GitHubExplorer", "CommitRecord"]
