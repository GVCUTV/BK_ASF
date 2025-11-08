# // v1.3C-Data-List
# // file: main.py
"""CLI entrypoint for the PMCSN ASF exploration exports."""
# // DoD:
# // - Provide ``python etl_exploration/main.py --export all`` command.
# // - Log to stdout and ``logs/exploration.log`` with deterministic formatting.
# // - Generate CSV, JSON, and Markdown artefacts required by Section 1.3C.

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

try:
    from .config import ExplorationConfig, load_config
    from .developer_dictionary import DeveloperDictionaryBuilder
    from .documentation import write_document
    from .github_explorer import GitHubExplorer
    from .jira_explorer import JiraExplorer
    from .validation import summarize_datasets, write_report
except ImportError:  # pragma: no cover - fallback for direct script execution
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from etl_exploration.config import ExplorationConfig, load_config
    from etl_exploration.developer_dictionary import DeveloperDictionaryBuilder
    from etl_exploration.documentation import write_document
    from etl_exploration.github_explorer import GitHubExplorer
    from etl_exploration.jira_explorer import JiraExplorer
    from etl_exploration.validation import summarize_datasets, write_report


LOGGER_NAME = "etl_exploration"
LOG_HEADER = "// v1.3C-Data-List\n// file: exploration.log\n// DoD: capture exploration ETL activity.\n"


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def setup_logging(log_path: Path) -> logging.Logger:
    """Configure logging to stdout and the provided logfile."""

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        _initialize_log_file(log_path)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def _initialize_log_file(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists() or log_path.stat().st_size == 0:
        log_path.write_text(LOG_HEADER, encoding="utf-8")


# ---------------------------------------------------------------------------
# Export orchestration
# ---------------------------------------------------------------------------

def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PMCSN ASF exploration exporter")
    parser.add_argument(
        "--export",
        choices=["all", "jira", "github", "developers", "report"],
        default="all",
        help="Select which artefact to generate.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force refresh of remote caches before exporting.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    config: ExplorationConfig = load_config()
    logger = setup_logging(config.log_file)
    logger.info("Starting exploration export", extra={"export": args.export})

    jira_df = pd.DataFrame()
    github_df = pd.DataFrame()

    export_all = args.export == "all"
    export_jira = export_all or args.export == "jira"
    export_github = export_all or args.export == "github"
    export_developers = export_all or args.export == "developers"
    export_report = export_all or args.export == "report"

    jira_explorer = JiraExplorer(config, logger)
    github_explorer = GitHubExplorer(config, logger)
    developer_builder = DeveloperDictionaryBuilder(logger)

    jira_payload = jira_explorer.load_issues(refresh=args.refresh_cache)
    if not jira_payload and config.jira_cache_path.exists():
        logger.info("Using previously cached JIRA payloads")
        jira_payload = jira_explorer.load_issues(refresh=False)
    jira_df = jira_explorer.to_dataframe(jira_payload)
    if export_jira:
        jira_explorer.export_csv(jira_df, config.data_dir / "jira_issues.csv")

    github_payload = github_explorer.load_commits(refresh=args.refresh_cache)
    if not github_payload and config.github_cache_path.exists():
        logger.info("Using previously cached GitHub payloads")
        github_payload = github_explorer.load_commits(refresh=False)
    github_df = github_explorer.to_dataframe(github_payload)
    if export_github:
        github_explorer.export_csv(github_df, config.data_dir / "github_commits.csv")

    developers_df = developer_builder.build(jira_df, github_df)
    if export_developers:
        developer_csv = config.data_dir / "developers.csv"
        developer_builder.export_csv(developers_df, str(developer_csv))
        logger.info("Wrote developer dictionary: %s", developer_csv)

    summary = summarize_datasets(jira_df, github_df, developers_df)
    if export_report:
        report_path = config.data_dir / "report.json"
        write_report(summary, report_path, logger)

    if export_all:
        doc_path = Path(__file__).resolve().parent.parent / "docs" / "DATA_LIST_1.3C.md"
        write_document(jira_df, github_df, developers_df, summary, doc_path)
        logger.info("Updated exploration documentation: %s", doc_path)

    logger.info("Exploration export completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
