# ETL As-Is Analysis (Code as Source of Truth)
Generated from repository code inspection of /etl (recursive).

## 0. Inventory
| File | Type | Primary responsibility | Entrypoint | Key dependencies |
| --- | --- | --- | --- | --- |
| etl/1_download_jira_tickets.py | script | Download and flatten Apache BookKeeper Jira issues into a raw CSV for downstream ETL. | CLI via `python etl/1_download_jira_tickets.py` (main guard). | Internal: `path_config.PROJECT_ROOT`; External: `requests`, `pandas`, `logging`. |
| etl/2_download_github_prs.py | script | Download GitHub PR list + per-PR details (reviews/checks/statuses), with caching and incremental mode, into a raw CSV. | CLI via `python etl/2_download_github_prs.py` (main guard). | Internal: `path_config.PROJECT_ROOT`; External: `requests`, `pandas`, `concurrent.futures`, `logging`. |
| etl/3_clean_and_merge.py | script | Clean Jira and PR raw CSVs, derive phase timestamps/durations, and merge into a single dataset. | CLI via `python etl/3_clean_and_merge.py` (main guard). | Internal: `path_config.PROJECT_ROOT`; External: `pandas`, `logging`, `re`. |
| etl/4_summarize_and_plot.py | script | Produce summary counts and a ticket-type pie chart from merged ticket/PR data. | CLI via `python etl/4_summarize_and_plot.py` (main guard). | Internal: `path_config.PROJECT_ROOT`; External: `pandas`, `matplotlib`, `logging`. |
| etl/5_estimate_parameters.py | script | Compute arrival/throughput stats and phase duration summaries; export parameter CSVs and backlog plot. | CLI via `python etl/5_estimate_parameters.py` (main guard). | Internal: `path_config.PROJECT_ROOT`; External: `pandas`, `numpy`, `matplotlib`, `logging`. |
| etl/6_diagnose_and_plot_tickets.py | script | Print per-ticket diagnostics and plot resolution time distribution. | CLI via `python etl/6_diagnose_and_plot_tickets.py` (main guard). | Internal: `path_config.PROJECT_ROOT`; External: `pandas`, `matplotlib`, `logging`. |
| etl/7_fit_distributions.py | script | Fit candidate distributions to phase durations and export fit statistics/plots. | CLI via `python etl/7_fit_distributions.py` (main guard). | Internal: `path_config.PROJECT_ROOT`; External: `pandas`, `numpy`, `scipy`, `matplotlib`, `logging`. |
| etl/8_export_fit_summary.py | script/cli | Convert per-stage fit statistics into a compact `fit_summary.csv` for simulation use. | CLI via `python etl/8_export_fit_summary.py` (argparse). | Internal: `path_config.PROJECT_ROOT`; External: `pandas`, `numpy`, `argparse`, `logging`. |
| etl/9_enrich_feedback_cols.py | script/cli | Enrich merged dataset with review/CI feedback signals and inferred developer/tester fields. | CLI via `python etl/9_enrich_feedback_cols.py` (argparse). | Internal: `path_config.PROJECT_ROOT`; External: `pandas`, `numpy`, `logging`. |
| etl/X_exponentiality_diagnostics.py | script | Run exploratory distribution diagnostics (KDE, fits, QQ) for resolution time hours. | Executed on import or `python etl/X_exponentiality_diagnostics.py` (no main guard). | External: `pandas`, `numpy`, `scipy`, `matplotlib`, `logging`. |
| etl/assignee_date.py | script | Parse Jira issue changelog JSON to extract assignment date and close date to CSV. | CLI via `python etl/assignee_date.py` (main guard). | External: `json`, `csv`, `datetime`, `pathlib`. |

## 1. Big Picture
The ETL in `/etl` is a pipeline of stand-alone scripts that fetch raw Jira and GitHub data, clean/merge it into a ticket-centric dataset, derive phase durations, then compute descriptive statistics and distribution fits for downstream simulation/analysis. The core data flow is: Jira issues and GitHub PR details are downloaded into raw CSVs, then cleaned and merged on Jira key, then augmented/diagnosed/fit in subsequent scripts. Configuration is mostly file-path constants rooted at `path_config.PROJECT_ROOT`, plus environment variables for GitHub token/QPS behavior. Execution is not a single orchestrated runner; it is a sequence of independent scripts invoked manually in order (download → clean/merge → summarize/estimate/fit/enrich as needed). The pipeline makes extensive use of filesystem outputs under `etl/output/` (CSV, PNG, logs), so re-runs depend on the presence and freshness of those artifacts.

## 2. Per-File Deep Dive (high-level first)

### etl/1_download_jira_tickets.py
**Role in ETL:** Downloads Jira issues for the BOOKKEEPER project from Apache’s Jira API, flattens nested fields, and writes a raw CSV used by downstream cleaning and merges. It is the canonical Jira data ingest step for the ETL. It also logs counts and basic assignee coverage for debugging.
**Inputs:** Jira REST API `/rest/api/2/search` (network), JQL query for project BOOKKEEPER, pagination parameters. No local input files.
**Outputs:** `etl/output/csv/jira_issues_raw.csv` (flattened CSV), `output/logs/download_jira_tickets.log`.
**Main steps:**
1. Configure logging and output paths rooted at `PROJECT_ROOT`.
2. Paginate Jira issues via `startAt`/`maxResults` and a fixed JQL order.
3. Retry failed requests with backoff for transient errors.
4. Flatten nested JSON with `pandas.json_normalize` using dot-separated column names.
5. Select preferred columns (key, fields.*), falling back to all flattened columns if missing.
6. Write CSV output and log assignee coverage statistics.
**Key functions/classes:**
- `_jira_get`: GET with retries and backoff for Jira API calls.
- `download_all_issues`: paginated fetch loop over Jira issues.
- `main`: orchestrates download, flatten, select columns, and write CSV.
**Important logic & edge cases:**
- If no issues are downloaded, it still writes an empty CSV with headers so downstream steps can run.
- Only a subset of fields are requested (fields list), so other Jira data is not captured.
**Error handling & fallbacks:**
- Retries for 429/5xx with backoff; non-retryable errors raise `RuntimeError`.
- If preferred columns are missing, it writes all flattened columns.
**Side effects:** Writes CSV/logs; makes HTTP requests to Jira.
**Performance notes:** Pagination defaults to 1000 issues per call with a hard cap of 200 batches.
**How to run:** `python etl/1_download_jira_tickets.py`.

### etl/2_download_github_prs.py
**Role in ETL:** Downloads GitHub pull requests for `apache/bookkeeper`, along with per-PR details (reviews, check-runs, combined statuses), and exports a raw CSV for merging. It implements multi-token rotation, caching with ETags, concurrency, and incremental updates to reduce API usage.
**Inputs:** GitHub REST API endpoints for PR list, PR reviews, check-runs, and commit statuses. Tokens from `etl/env/github_tokens.env` and/or `GITHUB_TOKENS` env var. Optionally a prior `github_prs_raw.csv` for incremental reuse.
**Outputs:** `etl/output/csv/github_prs_raw.csv` (raw PRs + derived review/CI fields), `output/logs/download_github_prs.log`, cache file `etl/cache/github_http_cache.json`.
**Main steps:**
1. Initialize logging, token pool, HTTP session, and cache.
2. Discover last PR page (via Link header) and fetch PR list pages concurrently.
3. Optionally reuse unchanged PR rows from prior CSV (incremental mode).
4. For remaining PRs, fetch reviews, check-runs, and combined status in parallel.
5. Derive review/CI summary signals and assemble row fields.
6. Write combined CSV and log quick stats.
**Key functions/classes:**
- `TokenPool`: rotates tokens on rate limit, tracks remaining/reset.
- `_req_get`: GET with QPS throttling, ETag cache, retries, and token rotation.
- `_list_all_prs_concurrent`: concurrent pagination fetch.
- `_process_one_pr`: fetch per-PR details and assemble output row.
- `main`: orchestrates the entire download and write.
**Important logic & edge cases:**
- Incremental mode reuses previous rows if `updated_at` is unchanged, skipping detail calls.
- 304 responses reuse cached bodies; if cache missing, it retries without ETag.
- If no tokens are available, it proceeds unauthenticated (low rate limits).
**Error handling & fallbacks:**
- Transient errors (429/5xx) are retried with backoff or `Retry-After`.
- Rate-limit 403 triggers token rotation or sleep until reset.
- Errors in per-PR processing are logged and skipped; the run continues.
**Side effects:** Writes CSV/logs, persists cache, and makes many network calls.
**Performance notes:** Uses concurrency (two ThreadPoolExecutors) and pooled HTTP connections with QPS throttling.
**How to run:** `python etl/2_download_github_prs.py`.

### etl/3_clean_and_merge.py
**Role in ETL:** Cleans raw Jira issues and GitHub PR datasets, merges them on Jira key, and derives phase timestamps/durations for development, review, and testing. This script produces the canonical merged dataset used by subsequent analysis steps.
**Inputs:** `etl/output/csv/jira_issues_raw.csv`, `etl/output/csv/github_prs_raw.csv`.
**Outputs:** `etl/output/csv/jira_issues_clean.csv`, `etl/output/csv/github_prs_clean.csv`, `etl/output/csv/tickets_prs_merged.csv`, `etl/output/logs/clean_and_merge.log`.
**Main steps:**
1. Load Jira and PR raw CSVs.
2. Clean Jira tickets: drop duplicate keys, filter out unwanted resolutions, normalize timestamps.
3. Clean PRs: extract Jira key from title/body, normalize timestamps, handle missing merged_at.
4. Merge tickets and PRs on Jira key (left join).
5. Derive phase timestamps (dev/review/test) using PR-created and PR-merged/closed dates.
6. Calculate phase durations and total resolution time in days.
7. Write cleaned and merged CSVs.
**Key functions/classes:**
- `extract_jira_key`: regex extraction of `BOOKKEEPER-<num>`.
- `clean_tickets`: dedupe/filter/normalize Jira data.
- `clean_prs`: extract key + parse PR timestamps.
- `derive_phase_times`: aggregate PR timestamps and compute durations.
**Important logic & edge cases:**
- Review end uses `merged_at` if available, otherwise `closed_at` as proxy.
- Duration values are set to `NaN` for missing timestamps or negative deltas.
- If a column is missing, it logs a warning and continues (fail-soft).
**Error handling & fallbacks:**
- Soft failure: missing columns are logged and left as NaN.
- No explicit try/except around CSV reads; exceptions propagate.
**Side effects:** Writes multiple CSVs and logs.
**Performance notes:** GroupBy aggregation per ticket key; otherwise straightforward pandas operations.
**How to run:** `python etl/3_clean_and_merge.py`.

### etl/4_summarize_and_plot.py
**Role in ETL:** Provides simple descriptive statistics and a ticket-type pie chart from the merged dataset. Primarily for reporting and high-level summaries.
**Inputs:** `etl/output/csv/tickets_prs_merged.csv`.
**Outputs:** `etl/output/png/distribuzione_ticket_tipo.png`, `etl/output/csv/statistiche_riassuntive.csv`, `etl/output/logs/summarize_and_plot.log`.
**Main steps:**
1. Load merged CSV.
2. Compute counts by issue type and print them.
3. Identify reopened, in-progress, and closed-without-PR tickets.
4. Build and save a pie chart with legend.
5. Export the summary table as CSV.
**Key functions/classes:** None (inline script).
**Important logic & edge cases:**
- The pie chart uses a legend instead of labels to avoid overlap.
- Assumes columns like `fields.issuetype.name` and `fields.status.name` exist.
**Error handling & fallbacks:**
- No explicit error handling; missing columns would raise at runtime.
**Side effects:** Writes PNG, CSV, and logs.
**Performance notes:** O(n) aggregations; no heavy computation.
**How to run:** `python etl/4_summarize_and_plot.py`.

### etl/5_estimate_parameters.py
**Role in ETL:** Computes global arrival/throughput metrics and per-phase duration summaries, exporting parameters needed for modeling or simulation. Also generates a backlog-over-time plot from created/resolution dates.
**Inputs:** `etl/output/csv/tickets_prs_merged.csv`.
**Outputs:** `etl/output/csv/phase_durations_wide.csv`, `etl/output/csv/phase_summary_stats.csv`, `etl/output/csv/parameter_estimates.csv`, `etl/output/png/backlog_over_time.png`, `etl/output/logs/estimate_parameters.log`.
**Main steps:**
1. Load merged CSV and parse creation/resolution timestamps.
2. Estimate inter-arrival times and arrival rate (tickets/day).
3. Compute global resolution time statistics (mean/median days).
4. Compute backlog time series (open tickets per day) and plot.
5. Export per-phase duration columns (wide form) and summary stats.
6. Export overall parameter estimates for downstream use.
**Key functions/classes:**
- `summarize_phase`: returns count, NaN share, mean, median, std, quartiles, min/max for a phase column.
**Important logic & edge cases:**
- Arrival rate is computed as inverse of mean inter-arrival; if mean is zero/NaN, rate is NaN.
- Backlog computation iterates daily across the full timeline (potentially large).
- Warns if phase duration columns are missing (expects output from `3_clean_and_merge.py`).
**Error handling & fallbacks:**
- CSV load errors cause SystemExit.
- Missing columns log warnings and skip related computations.
**Side effects:** Writes multiple CSVs/PNG and logs.
**Performance notes:** Backlog computation loops over each day in range and scans all tickets, which can be O(n * days).
**How to run:** `python etl/5_estimate_parameters.py`.

### etl/6_diagnose_and_plot_tickets.py
**Role in ETL:** Produces per-ticket diagnostic output and a histogram of resolution times to identify data quality issues. It is a verbose diagnostic utility rather than a core pipeline step.
**Inputs:** `etl/output/csv/tickets_prs_merged.csv`.
**Outputs:** `etl/output/png/distribuzione_resolution_times_0_10000.png`, `etl/output/logs/diagnose_tickets.log`, plus extensive console output.
**Main steps:**
1. Load merged CSV and parse key timestamps if present.
2. Compute resolution time in hours (if possible).
3. Print each ticket’s key fields and flags for common inconsistencies.
4. Plot histogram of resolution times between 0 and 10,000 hours.
5. Log warnings for detected inconsistencies.
**Key functions/classes:** None (inline script).
**Important logic & edge cases:**
- Checks for missing keys, missing creation dates, resolution before creation, negative durations, and closed tickets without resolution dates.
- Histogram uses dynamic bin count based on sample size.
**Error handling & fallbacks:**
- CSV load errors cause exit(1).
- If no resolution-time data, histogram is skipped with a warning.
**Side effects:** Writes PNG/logs; prints per-ticket details to stdout.
**Performance notes:** Per-row iteration over the entire dataset; could be expensive on large datasets.
**How to run:** `python etl/6_diagnose_and_plot_tickets.py`.

### etl/7_fit_distributions.py
**Role in ETL:** Fits candidate distributions (lognormal, Weibull, exponential, normal) to phase duration series and exports fit diagnostics and plots. Also produces a `fit_summary.csv` for downstream simulation configuration.
**Inputs:** `etl/output/csv/tickets_prs_merged.csv`.
**Outputs:**
- `etl/output/csv/distribution_fit_stats.csv` (legacy resolution-time fit)
- `etl/output/csv/distribution_fit_stats_development.csv`
- `etl/output/csv/distribution_fit_stats_review.csv`
- `etl/output/csv/distribution_fit_stats_testing.csv`
- `etl/output/csv/fit_summary.csv`
- `etl/output/png/confronto_fit_*.png`
- `etl/output/logs/fit_distributions.log`
**Main steps:**
1. Load merged CSV and compute `resolution_time_days` if missing.
2. For legacy resolution time, fit distributions and export stats/plot.
3. For each stage (development/review/testing), fit distributions on duration days.
4. Compute MSE against KDE, KS p-values, AIC/BIC, and plausibility.
5. Write per-stage stats CSVs and comparison plots.
6. Write a compact `fit_summary.csv` using the best fit per stage.
**Key functions/classes:**
- `_fit_distribution_set`: runs KDE-based curve fitting and metrics for candidate distributions.
- `_to_fit_summary_row`: maps winner to SciPy naming/params.
- `_mean_std_from_params`, `_plausible`, `_ks_aic_bic`: helper metrics.
**Important logic & edge cases:**
- Data is filtered to non-negative, finite values and capped at 10 years (`MAX_DAYS`).
- Requires at least 10 data points; otherwise skips fitting.
- Best fit is chosen by minimum MSE vs KDE curve.
**Error handling & fallbacks:**
- CSV load errors cause SystemExit.
- If no fits are possible, logs an error and does not output `fit_summary.csv`.
**Side effects:** Writes multiple CSVs/PNGs/logs.
**Performance notes:** KDE and curve fitting can be expensive; uses 1000-point grid for each fit.
**How to run:** `python etl/7_fit_distributions.py`.

### etl/8_export_fit_summary.py
**Role in ETL:** Converts per-stage distribution fit statistics into a compact `fit_summary.csv` with SciPy-compatible parameter names and minimal fields for simulation. It is primarily a post-processing helper for `7_fit_distributions.py` outputs.
**Inputs:** `etl/output/csv/distribution_fit_stats_<stage>.csv` (or override paths). CLI options include stage selection and plausible-only filtering.
**Outputs:** `etl/output/csv/fit_summary.csv`, `etl/output/logs/export_fit_summary.log`.
**Main steps:**
1. Parse CLI args for base directory, output CSV, stages, and optional overrides.
2. For each stage, locate the matching distribution fit CSV.
3. Parse the `Parametri` column into numeric lists.
4. Choose the best fit row (lowest MAE/MSE, then AIC/BIC).
5. Map labels to SciPy distribution names and parameter fields.
6. Write a compact summary CSV.
**Key functions/classes:**
- `parse_params`: robust parsing of `Parametri` strings into float lists.
- `choose_winner`: selection by metric/AIC/BIC.
- `map_to_scipy_row`: maps Italian labels to SciPy naming.
**Important logic & edge cases:**
- Supports aliases for stage names (dev/development, test/testing, etc.).
- Fails with SystemExit if required columns are missing or no CSV found.
**Error handling & fallbacks:**
- Hard-fails on missing columns, missing files, or no plausible rows after filtering.
**Side effects:** Writes CSV/logs.
**Performance notes:** Minimal; just CSV IO and sorting.
**How to run:** `python etl/8_export_fit_summary.py --stages dev review testing` (defaults are set).

### etl/9_enrich_feedback_cols.py
**Role in ETL:** Enriches the merged dataset with derived feedback/capacity signals (review rounds, rework flag, CI fail→fix) and inferred developer/tester identifiers. It updates the existing merged CSV or writes to a specified output.
**Inputs:** `etl/output/csv/tickets_prs_merged.csv` by default (CLI overridable).
**Outputs:** `etl/output/csv/tickets_prs_merged.csv` by default (overwrites input) and `output/logs/enrich_feedback.log`.
**Main steps:**
1. Load merged CSV from CLI path.
2. Derive `review_rounds` and `review_rework_flag` from numeric or string review signals.
3. Derive `ci_failed_then_fix` from check/status histories or boolean flags.
4. Infer `dev_user` and `tester` from prioritized columns.
5. Log coverage statistics and missing signals.
6. Write enriched CSV.
**Key functions/classes:**
- `enrich`: central enrichment logic for review/CI/dev/tester columns.
- `_to_listish`, `_has_fail_then_success`: parse and interpret list-like status fields.
**Important logic & edge cases:**
- For review rounds, numeric counters take precedence; otherwise, string states with `CHANGES_REQUESTED` imply rework.
- CI fail→fix requires a failure-like token preceding a success-like token.
- If no candidates exist, it logs warnings and omits columns.
**Error handling & fallbacks:**
- Relies on best-effort heuristics and logs when signals cannot be derived.
- No try/except around CSV load; errors propagate.
**Side effects:** Writes CSV/logs; overwrites input by default.
**Performance notes:** Column-wise operations; expected to scale linearly.
**How to run:** `python etl/9_enrich_feedback_cols.py --in-csv <path> --out-csv <path>`.

### etl/X_exponentiality_diagnostics.py
**Role in ETL:** Runs a diagnostic suite to test whether resolution times are exponential or heavy-tailed using KDE, distribution fits, CDF/QQ plots, and KS tests. This appears to be an exploratory analysis script rather than a pipeline step.
**Inputs:** `etl/output/csv/tickets_prs_merged.csv` (relative path `./output/csv/tickets_prs_merged.csv` from `etl/`).
**Outputs:** `./output/png/diagnostic_*.png`, `../simulation/output/logs/exponentiality_diag.log`, stdout prints of skewness, kurtosis, and KS p-values.
**Main steps:**
1. Load merged CSV and compute resolution time in hours.
2. Filter resolution times to 0–10,000 hours.
3. Fit exponential, normal, lognormal, and Weibull distributions.
4. Plot histogram with KDE + fitted PDFs.
5. Plot empirical vs theoretical CDFs.
6. Generate QQ plots for each distribution.
7. Plot log-survival curves for tail behavior.
8. Print skewness, kurtosis, and KS p-values.
**Key functions/classes:** None (top-level script).
**Important logic & edge cases:**
- Runs immediately on import (no main guard).
- Exits if fewer than 10 valid data points.
**Error handling & fallbacks:**
- Minimal; relies on try/except around each distribution fit.
**Side effects:** Writes PNGs/logs, prints to stdout.
**Performance notes:** KDE and multiple fits can be expensive; uses 1000-point grids.
**How to run:** `python etl/X_exponentiality_diagnostics.py` (from `etl/` directory to resolve relative paths).

### etl/assignee_date.py
**Role in ETL:** Extracts assignment and close dates from a Jira search JSON (including changelog histories) and writes a CSV. This is an auxiliary extractor and is not directly wired into the main ETL pipeline.
**Inputs:** `etl/search.json` in the same directory (fixed filename).
**Outputs:** `etl/output/search_output.csv` (relative to script directory).
**Main steps:**
1. Load `search.json` containing Jira issues and changelog.
2. For each issue, find the latest assignee change date (or creation date if none).
3. For each issue, find the last transition to a “done” status (Closed/Done/Resolved), falling back to resolution date.
4. Write a CSV with issue key, assignment date, and close date.
**Key functions/classes:**
- `parse_iso`: normalizes Jira timestamp strings into `datetime`.
- `get_assignment_date`: choose last assignee change or creation date.
- `get_close_date`: choose last done-status change or resolution date.
**Important logic & edge cases:**
- Changelog parsing is purely history-based; if history absent, it falls back.
- Assumes specific status names (`Closed`, `Done`, `Resolved`).
**Error handling & fallbacks:**
- If `search.json` is missing, prints an error and returns.
- Parsing errors return None and fall back to raw strings where applicable.
**Side effects:** Writes CSV; prints status to stdout.
**Performance notes:** Linear in number of issues and history entries.
**How to run:** `python etl/assignee_date.py`.

## 3. Cross-Cutting Concerns
- **Logging strategy:** Every script configures logging locally, typically to both a file under `etl/output/logs` (or `output/logs`) and stdout. There is no shared logging configuration, so format and log location vary slightly per script.
- **Config strategy:** Paths are mostly derived from `path_config.PROJECT_ROOT`. GitHub downloader additionally uses environment variables for concurrency, QPS, token locations, and incremental mode. Other scripts use hard-coded filenames relative to `PROJECT_ROOT`.
- **Schema/contracts:** The core contract is `tickets_prs_merged.csv`, which includes Jira fields (e.g., `fields.created`, `fields.resolutiondate`) and PR fields (e.g., `created_at`, `closed_at`, `reviews_count`). There is no explicit schema validation; scripts assume columns exist and log warnings when missing.
- **Idempotency:** Download scripts overwrite their outputs; clean/merge and downstream analysis overwrite outputs as well. Re-running is mostly safe but can change results if upstream data has changed. Incremental mode in GitHub downloader reuses old rows by `updated_at`.
- **Determinism & randomness:** No randomness in ETL scripts. Outcomes depend on live API responses and on current CSVs.
- **External integrations:** Jira API and GitHub API (network). GitHub credentials from `etl/env/github_tokens.env` or `GITHUB_TOKENS` env var; Jira uses anonymous access. No DBs.
- **Hard-coded paths and assumptions:** Many scripts assume execution from repo root (or `etl/`) and specific relative output directories. `X_exponentiality_diagnostics.py` writes to `../simulation/output/...`, which is outside `etl` and assumes a particular working directory. `assignee_date.py` assumes `search.json` in the same folder.

## 4. Data Contracts Map
- **`etl/output/csv/jira_issues_raw.csv`**
  - Producer: `etl/1_download_jira_tickets.py`
  - Consumer: `etl/3_clean_and_merge.py`
  - Location: `etl/output/csv/jira_issues_raw.csv`
  - Minimal schema: `key`, `fields.*` (specifically `fields.created`, `fields.resolutiondate`, `fields.issuetype.name`, `fields.status.name`, and assignee subfields if present). Fields are flattened with dot notation; exact columns depend on Jira API response.
- **`etl/output/csv/github_prs_raw.csv`**
  - Producer: `etl/2_download_github_prs.py`
  - Consumer: `etl/3_clean_and_merge.py`
  - Location: `etl/output/csv/github_prs_raw.csv`
  - Minimal schema: `number`, `title`, `body` (optional), `created_at`, `updated_at`, `closed_at`, `merged_at` (optional), review and CI fields (`reviews_count`, `requested_changes_count`, `pull_request_review_states`, `check_runs_conclusions`, `combined_status_states`). Some fields are JSON-serialized lists.
- **`etl/output/csv/jira_issues_clean.csv`**
  - Producer: `etl/3_clean_and_merge.py`
  - Consumer: None explicitly in `/etl` (intermediate output).
  - Location: `etl/output/csv/jira_issues_clean.csv`
  - Minimal schema: `key`, `fields.created`, `fields.resolutiondate`, `fields.resolution.name` (if available), plus cleaned/derived aliases.
- **`etl/output/csv/github_prs_clean.csv`**
  - Producer: `etl/3_clean_and_merge.py`
  - Consumer: None explicitly in `/etl` (intermediate output).
  - Location: `etl/output/csv/github_prs_clean.csv`
  - Minimal schema: `jira_key`, `created_at`, `updated_at`, `closed_at`, `merged_at` (if available).
- **`etl/output/csv/tickets_prs_merged.csv`**
  - Producer: `etl/3_clean_and_merge.py`
  - Consumers: `etl/4_summarize_and_plot.py`, `etl/5_estimate_parameters.py`, `etl/6_diagnose_and_plot_tickets.py`, `etl/7_fit_distributions.py`, `etl/9_enrich_feedback_cols.py`, `etl/X_exponentiality_diagnostics.py`.
  - Location: `etl/output/csv/tickets_prs_merged.csv`
  - Minimal schema: Jira columns (`fields.created`, `fields.resolutiondate`, `fields.issuetype.name`, `fields.status.name`), PR columns (`created_at`, `closed_at`, `merged_at` optionally), and derived phase durations (`dev_duration_days`, `review_duration_days`, `test_duration_days`) where produced.
- **`etl/output/csv/phase_durations_wide.csv`**
  - Producer: `etl/5_estimate_parameters.py`
  - Consumer: None explicitly in `/etl`.
  - Location: `etl/output/csv/phase_durations_wide.csv`
  - Minimal schema: `key` (if present), `dev_duration_days`, `review_duration_days`, `test_duration_days`.
- **`etl/output/csv/phase_summary_stats.csv`**
  - Producer: `etl/5_estimate_parameters.py`
  - Consumer: None explicitly in `/etl`.
  - Location: `etl/output/csv/phase_summary_stats.csv`
  - Minimal schema: columns from `summarize_phase` (phase, count, mean, median, std, quantiles).
- **`etl/output/csv/parameter_estimates.csv`**
  - Producer: `etl/5_estimate_parameters.py`
  - Consumer: None explicitly in `/etl`.
  - Location: `etl/output/csv/parameter_estimates.csv`
  - Minimal schema: `arrival_rate_per_day`, `mean_resolution_time_days`, `median_resolution_time_days`, `throughput_monthly_mean`.
- **`etl/output/csv/distribution_fit_stats*.csv`**
  - Producer: `etl/7_fit_distributions.py`
  - Consumer: `etl/8_export_fit_summary.py`
  - Location: `etl/output/csv/distribution_fit_stats*.csv`
  - Minimal schema: `Distribuzione`, `Parametri`, `MSE_KDE_PDF` (or MAE), plus KS/AIC/BIC if present.
- **`etl/output/csv/fit_summary.csv`**
  - Producer: `etl/7_fit_distributions.py` or `etl/8_export_fit_summary.py`
  - Consumer: Not visible in `/etl`; likely used by simulation (outside scope).
  - Location: `etl/output/csv/fit_summary.csv`
  - Minimal schema: `stage`, `dist`, and distribution parameters (e.g., `s`, `loc`, `scale`, `mu`, `sigma`).
- **`etl/output/png/*.png`**
  - Producers: `etl/4_summarize_and_plot.py`, `etl/5_estimate_parameters.py`, `etl/6_diagnose_and_plot_tickets.py`, `etl/7_fit_distributions.py`, `etl/X_exponentiality_diagnostics.py`.
  - Consumers: None in `/etl` (reporting artifacts).
  - Location: `etl/output/png/` (except diagnostic script also writes to `./output/png` and `../simulation/output/png`).

## 5. Execution Graph
```
[etl/1_download_jira_tickets.py] --(writes jira_issues_raw.csv)--> [etl/3_clean_and_merge.py]
[etl/2_download_github_prs.py]  --(writes github_prs_raw.csv)-->  [etl/3_clean_and_merge.py]
[etl/3_clean_and_merge.py]     --(writes tickets_prs_merged.csv)--> [etl/4_summarize_and_plot.py]
[etl/3_clean_and_merge.py]     --(writes tickets_prs_merged.csv)--> [etl/5_estimate_parameters.py]
[etl/3_clean_and_merge.py]     --(writes tickets_prs_merged.csv)--> [etl/6_diagnose_and_plot_tickets.py]
[etl/3_clean_and_merge.py]     --(writes tickets_prs_merged.csv)--> [etl/7_fit_distributions.py]
[etl/3_clean_and_merge.py]     --(writes tickets_prs_merged.csv)--> [etl/9_enrich_feedback_cols.py]
[etl/3_clean_and_merge.py]     --(writes tickets_prs_merged.csv)--> [etl/X_exponentiality_diagnostics.py]

[etl/7_fit_distributions.py] --(writes distribution_fit_stats_*.csv)--> [etl/8_export_fit_summary.py]

# Import/call edges
(path_config.PROJECT_ROOT) <- imported by most scripts for path resolution
```

## 6. Risks / Bugs / Smells (Code-Based)
- **Working directory assumptions:** `X_exponentiality_diagnostics.py` uses relative paths (`./output/...` and `../simulation/output/...`) and runs at import time. Running it from a different directory will break path resolution or write to unexpected locations.
- **No schema validation on merged dataset:** Downstream scripts assume columns exist (e.g., `fields.issuetype.name`, `fields.status.name`). Missing columns will raise runtime errors without graceful handling (notably in `4_summarize_and_plot.py`).
- **Potentially expensive backlog computation:** `5_estimate_parameters.py` computes backlog by iterating over each day and scanning all rows, which can be O(n*days) and slow for large datasets.
- **Silent drop of “bad” Jira resolutions:** `3_clean_and_merge.py` filters out tickets with certain resolution names; this can materially change totals but is not configurable or parameterized.
- **Token rotation logic with anonymous token fallback:** GitHub downloader proceeds without auth tokens, which may lead to very slow or incomplete downloads; it logs warnings but does not block.
- **Incremental mode risk:** `2_download_github_prs.py` reuses previous rows if `updated_at` matches; if derived fields change without `updated_at` changes (unlikely but possible), stale data may persist.

## 7. Open Questions (only those truly blocked by missing context)
- **Exact schemas of Jira and GitHub API responses** (which fields appear in CSVs): depends on API responses and permissions. To verify, inspect a generated `jira_issues_raw.csv` and `github_prs_raw.csv` after running the download scripts.
- **Presence of PR review/CI fields:** These fields depend on GitHub API availability and the repository’s CI configuration. To verify, run `2_download_github_prs.py` and inspect columns in the output CSV.
- **Upstream artifacts for `assignee_date.py`:** It requires a `search.json` file with changelog history, but this file is not produced by any script in `/etl`. To verify, locate or generate `etl/search.json` from Jira API with `expand=changelog`.
