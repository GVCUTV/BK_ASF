# // v1.3C-Data-List
# // file: documentation.py
"""Generate exploration layer documentation in Markdown."""
# // DoD:
# // - Produce deterministic Markdown summarizing schema and metrics.
# // - Reuse exported DataFrames to describe counts and column types.
# // - Provide helper invoked by the CLI orchestration layer.

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


HEADER = "# // v1.3C-Data-List\n# // file: DATA_LIST_1.3C.md\n"
DOD_BLOCK = (
    "<!-- // DoD:\n"
    "// - Document exploration export schemas.\n"
    "// - Record observed dataset counts.\n"
    "// - Capture cross-validation metrics.\n"
    "-->\n\n"
)


def _schema_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "| Column | Dtype |\n| --- | --- |\n"
    schema = "| Column | Dtype |\n| --- | --- |\n"
    for column, dtype in df.dtypes.items():
        schema += f"| {column} | {dtype} |\n"
    return schema


def _counts_section(title: str, df: pd.DataFrame) -> str:
    return (
        f"## {title}\n\n"
        f"Total rows: {len(df)}\n\n"
        f"{_schema_table(df)}\n"
    )


def _metrics_section(summary: Dict[str, int]) -> str:
    lines = ["## Cross-Source Validation Metrics", ""]
    for key, value in sorted(summary.items()):
        lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
    lines.append("")
    return "\n".join(lines)


def render_document(
    jira_df: pd.DataFrame, github_df: pd.DataFrame, developers_df: pd.DataFrame, summary: Dict[str, int]
) -> str:
    """Construct the full Markdown document."""

    sections = [HEADER, DOD_BLOCK]
    sections.append("## 1 ▪ Overview\n\nExploration exports capture synchronized views of JIRA and GitHub activity for Apache BookKeeper.\n\n")
    sections.append(_counts_section("JIRA Issues", jira_df))
    sections.append(_counts_section("GitHub Commits", github_df))
    sections.append(_counts_section("Developer Dictionary", developers_df))
    sections.append(_metrics_section(summary))
    return "".join(sections)


def write_document(
    jira_df: pd.DataFrame,
    github_df: pd.DataFrame,
    developers_df: pd.DataFrame,
    summary: Dict[str, int],
    path: Path,
) -> None:
    """Persist the Markdown document to disk."""

    content = render_document(jira_df, github_df, developers_df, summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


__all__ = ["write_document", "render_document"]
