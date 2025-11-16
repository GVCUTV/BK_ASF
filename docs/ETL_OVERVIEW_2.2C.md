// v1
// ETL_OVERVIEW_2.2C.md
# ETL Overview — Release 2.2C

## Version snapshot
- **Raw downloader:** `etl/1_download_jira_tickets.py` (v3) handles Jira pagination, flattening, and CSV export with structured logging.
- **Exploration toolkit:** `etl_exploration/jira_explorer.py` (v1.3C-Data-List) loads cached payloads, normalizes assignment/close timestamps, and emits normalized CSV snapshots.

## Pipeline walkthrough
### 1. Jira bulk download
The downloader authenticates against `issues.apache.org/jira`, issues paginated searches for every `BOOKKEEPER` ticket, flattens nested fields (status, resolution, assignee), and writes a canonical raw snapshot to `etl/output/csv/jira_issues_raw.csv`. All network retries and filesystem writes are logged to `output/logs/download_jira_tickets.log`, ensuring reproducibility when the API is stable.【F:etl/1_download_jira_tickets.py†L1-L185】

### 2. Exploration normalization
`JiraExplorer` can reload the cached payloads (JSON dumped next to the exploration config) or re-query Jira when credentials are provided. Each payload is normalized into `issue_key`, assignee metadata, assignment/close timestamps (derived from changelog histories), and status labels. The resulting DataFrame can be exported via `export_csv()` (header-prefixed CSV) to `data/exploration/jira_issues.csv` for ad-hoc notebooks or downstream ETL steps that expect standardized columns.【F:etl_exploration/jira_explorer.py†L1-L225】

### 3. Input / output flow
| Stage | Input | Output | Canonical location |
| --- | --- | --- | --- |
| Download | Jira REST API (`BOOKKEEPER` project) | Flattened raw CSV (statuses, resolutions, timestamps, descriptions) | `etl/output/csv/jira_issues_raw.csv`【F:etl/1_download_jira_tickets.py†L31-L185】 |
| Cleaning & enrichment | Raw CSV + changelog metadata | Clean issue snapshot (`jira_issues_clean.csv`) with parsed `created/resolved` columns for modeling | `etl/output/csv/jira_issues_clean.csv`【F:etl/output/csv/jira_issues_clean.csv†L1-L11】 |
| Phase statistics | Clean issue snapshot filtered by phase | Aggregate tables for each queue (`phase_summary_stats.csv`, `phase_durations_wide.csv`) | `etl/output/csv/phase_summary_stats.csv`【F:etl/output/csv/phase_summary_stats.csv†L1-L5】 |
| Typology summaries | Clean issue snapshot grouped by `issuetype` | Counts and % totals for reporting dashboards | `etl/output/csv/statistiche_riassuntive.csv`【F:etl/output/csv/statistiche_riassuntive.csv†L1-L10】 |

## Preliminary statistics
- **Issue volume:** 943 Jira tickets in the clean snapshot, providing 870 records with both `created` and `resolved` timestamps for cycle-time analysis.【f3ed62†L1-L18】
- **Status distribution:** Closed (454), Resolved (417), Open (64), Reopened (3), and In Progress (3) dominate the lifecycle states available in the clean export.【f3ed62†L4-L10】
- **Issue-type mix:** Bugs remain the majority (494 / 51.5%), with Improvements (217 / 22.6%), Sub-tasks (142 / 14.8%), and smaller contributions from New Feature, Task, Test, Wish, Documentation, and Story items.【F:etl/output/csv/statistiche_riassuntive.csv†L1-L10】
- **Cycle-time aggregates:** Median time from creation to resolution is ~20.8 days (mean 212.2 days, 75th percentile 101.3 days, max 3112.8 days) across issues with both timestamps.【f3ed62†L11-L18】
- **Phase-level durations:** Dev stints average 148.4 days (median <1 day), reviews average 35.0 days (median 9.2), and tests average 10.7 days (median minutes), reflecting skewed volunteer availability captured in `phase_summary_stats.csv`.【F:etl/output/csv/phase_summary_stats.csv†L1-L5】

## Reproducibility notes
- `JiraExplorer` first reuses cached JSON payloads; only when explicit credentials are configured does it requery Jira, which keeps the exploration CSV stable under offline work. Missing credentials simply result in cache-only behavior, preventing accidental re-downloads.【F:etl_exploration/jira_explorer.py†L58-L114】
- `1_download_jira_tickets.py` logs every batch boundary and CSV write, so reruns can be verified via `output/logs/download_jira_tickets.log` even when no data changes occur.【F:etl/1_download_jira_tickets.py†L31-L185】

## Data → model linkage
- The `phase_summary_stats.csv` and related duration tables feed the queueing model calibration together with the transition matrix stored in `data/state_parameters/matrix_P.csv` (semi-Markov transitions for OFF/DEV/REV/TEST).【F:data/state_parameters/matrix_P.csv†L1-L6】
- Service-time assumptions for DEV/REV/TEST lognormal fits are kept in `data/state_parameters/service_params.json`, ensuring simulations use the exact µ/σ values estimated from the ETL outputs.【F:data/state_parameters/service_params.json†L1-L20】
- Model notebooks refer to the `data/state_parameters` artifacts and `etl/output/csv` snapshots exclusively—no regeneration is needed for reproducibility under release 2.2C.
