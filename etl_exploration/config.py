# // v1.3C-Data-List
# // file: config.py
"""Configuration helpers for the data exploration layer."""
# // DoD:
# // - Define the configuration dataclass consumed by explorers.
# // - Load environment-driven defaults while ensuring deterministic paths.
# // - Provide utility helpers for downstream modules.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os


@dataclass(frozen=True)
class ExplorationConfig:
    """Central configuration shared across explorers."""

    jira_base_url: str
    jira_project_key: str
    jira_user: Optional[str]
    jira_token: Optional[str]
    github_repo_url: str
    github_token: Optional[str]
    data_dir: Path
    log_file: Path
    cache_dir: Path
    max_issues: int
    max_commits: int
    terminal_statuses: tuple[str, ...]

    @property
    def jira_cache_path(self) -> Path:
        """Return the path used to cache raw JIRA payloads."""
        return self.cache_dir / "jira_issues.json"

    @property
    def github_cache_path(self) -> Path:
        """Return the path used to cache raw GitHub payloads."""
        return self.cache_dir / "github_commits.json"


DEFAULT_TERMINAL_STATUSES: tuple[str, ...] = ("Closed", "Done", "Resolved")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read environment variables while trimming whitespace."""
    value = os.getenv(name, default)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else default


def load_config() -> ExplorationConfig:
    """Instantiate :class:`ExplorationConfig` using environment variables."""

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "exploration"
    cache_dir = data_dir / "cache"
    log_file = project_root / "logs" / "exploration.log"

    jira_base_url = _get_env("JIRA_BASE_URL", "https://issues.apache.org/jira")
    jira_project_key = _get_env("JIRA_PROJECT_KEY", "BOOKKEEPER")
    jira_user = _get_env("JIRA_USER")
    jira_token = _get_env("JIRA_TOKEN")

    github_repo_url = _get_env(
        "GITHUB_REPO_URL", "https://github.com/apache/bookkeeper"
    )
    github_token = _get_env("GITHUB_TOKEN")

    max_issues = int(_get_env("EXPLORATION_MAX_ISSUES", "500"))
    max_commits = int(_get_env("EXPLORATION_MAX_COMMITS", "500"))

    terminal_statuses_env = _get_env("JIRA_TERMINAL_STATUSES")
    if terminal_statuses_env:
        terminal_statuses = tuple(
            status.strip() for status in terminal_statuses_env.split(",") if status.strip()
        )
    else:
        terminal_statuses = DEFAULT_TERMINAL_STATUSES

    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    return ExplorationConfig(
        jira_base_url=jira_base_url,
        jira_project_key=jira_project_key,
        jira_user=jira_user,
        jira_token=jira_token,
        github_repo_url=github_repo_url,
        github_token=github_token,
        data_dir=data_dir,
        log_file=log_file,
        cache_dir=cache_dir,
        max_issues=max_issues,
        max_commits=max_commits,
        terminal_statuses=terminal_statuses,
    )


__all__ = ["ExplorationConfig", "load_config", "DEFAULT_TERMINAL_STATUSES"]
