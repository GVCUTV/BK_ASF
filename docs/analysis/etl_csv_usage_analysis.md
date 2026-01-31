# ETL CSV Usage Analysis (Code-Truth Trace)

## High-level dataflow overview

**Primary flow (ETL → simulation/validation):**
1. **Raw ingestion**
   - `etl/1_download_jira_tickets.py` → `etl/output/csv/jira_issues_raw.csv`
   - `etl/2_download_github_prs.py` → `etl/output/csv/github_prs_raw.csv`
2. **Cleaning + merge + phase derivation**
   - `etl/3_clean_and_merge.py` reads both raw CSVs, outputs cleaned snapshots and a merged, phase-annotated dataset at `etl/output/csv/tickets_prs_merged.csv`.
3. **Enrichment (feedback/capacity)**
   - `etl/9_enrich_feedback_cols.py` reads/writes `tickets_prs_merged.csv` to add review/CI feedback proxies plus `dev_user`/`tester` identities.
4. **Downstream consumers**
   - **Simulation config generation:** `simulation/generate_sim_config.py` reads `tickets_prs_merged.csv` + `etl/output/csv/fit_summary.csv` to produce `simulation/config.py`.
   - **State-equation artifacts:** `simulation/state_equations.py` reads `tickets_prs_merged.csv` and generates `data/state_parameters/*.csv` + `service_params.json`.
   - **Validation baselines:** `validation/baseline_extract.py` reads `tickets_prs_merged.csv` + `fit_summary.csv` to generate `validation/baseline_metrics.csv` + `validation/baseline_metadata.json`.
   - **Validation checks:** `validation/checks.py` and `validation/distribution_diagnostics.py` load `fit_summary.csv` to compare ETL fits against simulation/service parameters.

**Secondary flow (ETL → reporting/diagnostics):**
- `etl/4_summarize_and_plot.py`, `etl/5_estimate_parameters.py`, `etl/6_diagnose_and_plot_tickets.py`, `etl/7_fit_distributions.py`, `etl/X_exponentiality_diagnostics.py` read `tickets_prs_merged.csv` to produce statistics CSVs and diagnostic plots. These outputs are **not** consumed by the simulator directly but are referenced in documentation and manual analysis.

**Auxiliary (exploration layer, separate from ETL pipeline):**
- `etl_exploration/*` exports additional CSVs under `data/exploration/` (not fed into simulation code), so they are not part of the primary ETL-to-simulation path.

---

## CSV: `etl/output/csv/jira_issues_raw.csv`

**Producer (module/function):**
- `etl/1_download_jira_tickets.py` → `main()` writes the raw flattened snapshot.

**Schema (from code):**
- Selected fields (when available) include:
  - `key`
  - `fields.summary`
  - `fields.issuetype.name`, `fields.issuetype.id`
  - `fields.status.name`, `fields.status.id`
  - `fields.resolution.name`, `fields.resolutiondate`
  - `fields.created`, `fields.updated`
  - `fields.assignee.name`, `fields.assignee.displayName`, `fields.assignee.key`
  - `fields.description`
- If preferred columns are absent, the entire JSON-normalized schema is persisted (flattened with `.` separators).

**Semantic role:**
- Canonical Jira snapshot of issue metadata, used as the raw truth table before cleaning and phase derivation.

**Downstream usage:**
- **Consumed by:** `etl/3_clean_and_merge.py` (`pd.read_csv(JIRA_CSV)` → `clean_tickets()`), which filters resolutions and derives `created`/`resolved` columns.

**Project phase mapping:**
- ETL ingestion → cleaning/enrichment pipeline.

---

## CSV: `etl/output/csv/github_prs_raw.csv`

**Producer (module/function):**
- `etl/2_download_github_prs.py` → `main()` writes the raw PR snapshot.

**Schema (from code):**
- Core PR fields:
  - `number`, `html_url`, `state`, `title`, `created_at`, `updated_at`, `closed_at`, `merged_at`, `merge_commit_sha`
  - `user.login`, `assignee.login`
  - `requested_reviewers` (JSON list string)
  - `head.ref`, `head.sha`, `base.ref`
- Review + CI signals:
  - `reviews_count`, `requested_changes_count`
  - `pull_request_review_states` (JSON list string)
  - `check_runs_conclusions` (JSON list string)
  - `combined_status_states` (JSON list string)

**Semantic role:**
- Raw PR metadata + review/CI signals used to link PRs to Jira issues and derive review/test feedback proxies.

**Downstream usage:**
- **Consumed by:** `etl/3_clean_and_merge.py` (`pd.read_csv(PRS_CSV)` → `clean_prs()`), which extracts `jira_key` from `title`/`body` and parses PR timestamps.

**Project phase mapping:**
- ETL ingestion → cleaning/enrichment pipeline.

---

## CSV: `etl/output/csv/jira_issues_clean.csv`

**Producer (module/function):**
- `etl/3_clean_and_merge.py` → `clean_tickets()` writes the cleaned Jira issue snapshot.

**Schema (from code):**
- Inherits from `jira_issues_raw.csv` with additional normalized timestamps:
  - `created` (alias of `fields.created`)
  - `resolved` (alias of `fields.resolutiondate`)
- Filters out tickets with resolutions in `{"Won't Fix", "Duplicate", "Not A Problem", "Incomplete", "Cannot Reproduce"}` when `fields.resolution.name` is present.

**Semantic role:**
- Cleaned Jira dataset used for merging with PRs and deriving phase metrics.

**Downstream usage:**
- **Consumed by:** `etl/3_clean_and_merge.py` only (as an intermediate artifact).
- **Not consumed elsewhere in code** beyond documentation references.

**Project phase mapping:**
- ETL cleaning intermediate.

---

## CSV: `etl/output/csv/github_prs_clean.csv`

**Producer (module/function):**
- `etl/3_clean_and_merge.py` → `clean_prs()` writes the cleaned PR snapshot.

**Schema (from code):**
- Inherits from `github_prs_raw.csv` plus:
  - `jira_key` (extracted from PR title/body)
  - Parsed datetime columns for `created_at`, `updated_at`, `closed_at`, and optionally `merged_at`.

**Semantic role:**
- Cleaned PR dataset used to merge with Jira issues and derive phase boundaries.

**Downstream usage:**
- **Consumed by:** `etl/3_clean_and_merge.py` only (as an intermediate artifact).
- **Not consumed elsewhere in code** beyond documentation references.

**Project phase mapping:**
- ETL cleaning intermediate.

---

## CSV: `etl/output/csv/tickets_prs_merged.csv`

**Producer (module/function):**
- `etl/3_clean_and_merge.py` → `derive_phase_times()` + final `merged.to_csv(...)`.
- **Augmented by:** `etl/9_enrich_feedback_cols.py` (overwrites/adds feedback + identity columns).

**Schema (from code):**
- Merge of Jira (ticket) + PR (GitHub) datasets with derived phase timestamps and durations.
- Key derived columns include:
  - PR aggregation: `first_pr_created_at`, `last_pr_merged_at`, `last_pr_closed_at`
  - Phase boundaries: `dev_start_ts`, `dev_end_ts`, `review_start_ts`, `review_end_ts`, `test_start_ts`, `test_end_ts`
  - Phase durations (days): `dev_duration_days`, `review_duration_days`, `test_duration_days`
  - Resolution duration (days): `resolution_time_days`
- Feedback/identity enrichment (`etl/9_enrich_feedback_cols.py`) can add:
  - `review_rounds`, `review_rework_flag`
  - `ci_failed_then_fix`
  - `dev_user`, `tester`

**Semantic role:**
- Central ETL artifact containing per-ticket phase timelines, used to calibrate arrival rates, service-time fits, feedback probabilities, and developer capacity.

**Downstream usage (direct):**
- **ETL diagnostics/reporting:**
  - `etl/4_summarize_and_plot.py` (issue-type counts, reopened rates; writes `statistiche_riassuntive.csv`).
  - `etl/5_estimate_parameters.py` (phase summaries, arrival/throughput estimates; writes `phase_*` and `parameter_estimates.csv`).
  - `etl/6_diagnose_and_plot_tickets.py` (per-ticket diagnostic prints + resolution-time plots).
  - `etl/7_fit_distributions.py` (fits distributions over phase durations; writes distribution stats + `fit_summary.csv`).
  - `etl/X_exponentiality_diagnostics.py` (exponentiality diagnostics on `resolution_time_hours`).
  - `etl/9_enrich_feedback_cols.py` (adds feedback + identity columns).
- **Simulation configuration:**
  - `simulation/generate_sim_config.py` reads `tickets_prs_merged.csv` to estimate arrival rate, feedback probabilities, and capacity (distinct `dev_user`/`tester` or fallback columns).
- **State-equation artifacts (indirect simulation inputs):**
  - `simulation/state_equations.py` reads `tickets_prs_merged.csv` to compute `data/state_parameters/matrix_P.csv`, `stint_PMF_*.csv`, and `service_params.json`.
- **Validation baselines:**
  - `validation/baseline_extract.py` derives empirical metrics (arrival, throughput, service-time proxies) and persists `baseline_metrics.csv` + `baseline_metadata.json`.

**Project phase mapping:**
- **Simulation input** (via `generate_sim_config.py` and `state_equations.py`).
- **Validation** (baseline extraction, fit comparisons).
- **Analysis/reporting** (summaries, plots, diagnostics).

---

## CSV: `etl/output/csv/statistiche_riassuntive.csv`

**Producer (module/function):**
- `etl/4_summarize_and_plot.py` → summary export.

**Schema (from code):**
- `Tipo` (issue type)
- `Numero` (count)
- `% Totale` (percentage string)

**Semantic role:**
- Reporting summary of issue-type distribution.

**Downstream usage:**
- **No code consumers found** (referenced only in docs).

**Project phase mapping:**
- Reporting/plotting artifact.

---

## CSV: `etl/output/csv/phase_durations_wide.csv`

**Producer (module/function):**
- `etl/5_estimate_parameters.py` → exports per-ticket phase durations.

**Schema (from code):**
- `key` (if present) plus any of:
  - `dev_duration_days`, `review_duration_days`, `test_duration_days`

**Semantic role:**
- Wide table of per-ticket phase durations for manual analysis or external modeling.

**Downstream usage:**
- **No code consumers found** (referenced only in docs).

**Project phase mapping:**
- Analysis/reporting.

---

## CSV: `etl/output/csv/phase_summary_stats.csv`

**Producer (module/function):**
- `etl/5_estimate_parameters.py` → `summarize_phase()` per stage.

**Schema (from code):**
- `phase`, `count`, `nan_share`, `mean_d`, `median_d`, `std_d`, `p25_d`, `p75_d`, `min_d`, `max_d`

**Semantic role:**
- Per-stage descriptive statistics for phase durations.

**Downstream usage:**
- **No code consumers found** (referenced only in docs/validation plan text).

**Project phase mapping:**
- Analysis/reporting.

---

## CSV: `etl/output/csv/parameter_estimates.csv`

**Producer (module/function):**
- `etl/5_estimate_parameters.py` → global parameter summary export.

**Schema (from code):**
- `arrival_rate_per_day`, `mean_resolution_time_days`, `median_resolution_time_days`, `throughput_monthly_mean`

**Semantic role:**
- High-level global metrics for reporting or sanity checks.

**Downstream usage:**
- **No code consumers found**.

**Project phase mapping:**
- Analysis/reporting.

---

## CSV: `etl/output/csv/distribution_fit_stats.csv`

**Producer (module/function):**
- `etl/7_fit_distributions.py` → legacy fit over `resolution_time_days`.

**Schema (from code):**
- `Distribuzione`, `FitType`, `Parametri`, `KS_pvalue`, `AIC`, `BIC`, `MSE_KDE_PDF`, `FitMean`, `FitStd`, `Plausible`

**Semantic role:**
- Legacy single-series distribution diagnostics (resolution-time based), kept for historical comparisons.

**Downstream usage:**
- **No code consumers found** (not used by `simulation/generate_sim_config.py`).

**Project phase mapping:**
- Analysis/diagnostics only.

---

## CSV: `etl/output/csv/distribution_fit_stats_development.csv`

**Producer (module/function):**
- `etl/7_fit_distributions.py` → per-stage fit for `dev_duration_days`.

**Schema (from code):**
- Same as `distribution_fit_stats.csv` (per-stage fit details).

**Semantic role:**
- Detailed distribution fit diagnostics for development-phase durations.

**Downstream usage:**
- **Consumed by:** `etl/8_export_fit_summary.py` when stage aliases map to `development`.

**Project phase mapping:**
- Analysis → feeds `fit_summary.csv` generation.

---

## CSV: `etl/output/csv/distribution_fit_stats_review.csv`

**Producer (module/function):**
- `etl/7_fit_distributions.py` → per-stage fit for `review_duration_days`.

**Schema (from code):**
- Same as `distribution_fit_stats.csv`.

**Semantic role:**
- Detailed distribution fit diagnostics for review-phase durations.

**Downstream usage:**
- **Consumed by:** `etl/8_export_fit_summary.py`.

**Project phase mapping:**
- Analysis → feeds `fit_summary.csv` generation.

---

## CSV: `etl/output/csv/distribution_fit_stats_testing.csv`

**Producer (module/function):**
- `etl/7_fit_distributions.py` → per-stage fit for `test_duration_days`.

**Schema (from code):**
- Same as `distribution_fit_stats.csv`.

**Semantic role:**
- Detailed distribution fit diagnostics for testing-phase durations.

**Downstream usage:**
- **Consumed by:** `etl/8_export_fit_summary.py`.

**Project phase mapping:**
- Analysis → feeds `fit_summary.csv` generation.

---

## CSV: `etl/output/csv/fit_summary.csv`

**Producer (module/function):**
- **Primary (direct):** `etl/7_fit_distributions.py` → emits winners per stage after fitting.
- **Alternative (compact export):** `etl/8_export_fit_summary.py` → selects winners from stage-specific `distribution_fit_stats_*.csv` files.

**Schema (from code):**
- Shared required columns: `stage`, `dist`.
- Distribution parameters by type (consumed by `simulation/generate_sim_config.py`):
  - Lognormal: `s`, `loc`, `scale` (optional `mu`, `sigma` are sometimes included).
  - Weibull: `c`, `loc`, `scale` (optional `shape`).
  - Exponential: `loc`, `scale`.
  - Normal: `mu`, `sigma`.
- Additional metrics may differ by producer:
  - `7_fit_distributions.py` adds `mse`, `ks_pvalue`, `aic`, `bic`.
  - `8_export_fit_summary.py` adds `mae`, `is_winner`, `ks_pvalue`, `aic`, `bic`.

**Semantic role:**
- Canonical per-stage distribution selection for service-time modeling.

**Downstream usage:**
- **Simulation config generation:** `simulation/generate_sim_config.py` reads `fit_summary.csv` to populate `SERVICE_TIME_PARAMS` in `simulation/config.py`.
- **Validation & diagnostics:**
  - `validation/baseline_extract.py` snapshots `fit_summary.csv` into baseline metadata.
  - `validation/checks.py` reads it for parameter and distribution comparisons.
  - `validation/distribution_diagnostics.py` uses it to drive plausibility checks.

**Project phase mapping:**
- Simulation configuration + validation.

---

## CSV: `etl/output/search_output.csv`

**Producer (module/function):**
- `etl/assignee_date.py` → `main()` writes assignment/close timestamps derived from `etl/search.json` (Jira search payload).

**Schema (from code):**
- `issue_key`, `assignment_date`, `close_date`

**Semantic role:**
- Auxiliary extraction for assignment/close dates from cached Jira search payloads.

**Downstream usage:**
- **No code consumers found** (standalone extraction).

**Project phase mapping:**
- Auxiliary diagnostics / ad-hoc analysis.

---

## Orphan / unused CSV outputs (present but not produced or consumed by current code)

Based strictly on code references, the following CSVs appear in `etl/output/csv/` (or in logs) but **have no producer or consumer in the current codebase**:
- `kde_estimate.csv`, `kde_statistics.csv` — referenced only in `etl/output/logs/kde_estimation.log`.
- `fit_comparison_results.csv` — referenced only in `etl/output/logs/distribution_fit_comparison.log`.
- Stage-specific outputs like `distribution_fit_stats_dev_duration_days.csv` are **only listed as optional inputs** in `etl/8_export_fit_summary.py`; there is no producer in the repository.

These should be treated as **external/legacy artifacts** unless new producer scripts are added.

---

## Divergences / potential mismatches (code vs. consumer expectations)

1. **`fit_summary.csv` schema drift**
   - `etl/7_fit_distributions.py` writes `MSE_KDE_PDF` into distribution stats and emits `fit_summary.csv` with `mse` fields.
   - `etl/8_export_fit_summary.py` chooses winners using `MAE_KDE_PDF` when present (fallback to `MSE_KDE_PDF`) and writes `fit_summary.csv` with `mae`.
   - **Risk:** downstream consumers (`simulation/generate_sim_config.py`, `validation/checks.py`) only require the `stage/dist` and parameter fields, but the **selection criteria** differ depending on which script produced the file.

2. **Feedback/capacity columns required by downstream consumers**
   - `simulation/generate_sim_config.py` expects `dev_user`/`tester` and feedback proxy columns (`review_rounds`, `review_rework_flag`, `ci_failed_then_fix`) that are **only added by** `etl/9_enrich_feedback_cols.py`.
   - **Risk:** running only `etl/3_clean_and_merge.py` leaves required columns missing, causing `generate_sim_config.py` to fall back on heuristics or fail.

3. **Phase definition vs. documentation assumptions**
   - Code defines phase boundaries using **ticket timestamps and PR events** (`dev_start_ts` = ticket creation, `review_end_ts` = last PR merged/closed, etc.).
   - Documentation sometimes describes the phase summaries as “clean issue snapshot filtered by phase,” which is not how phases are actually derived in code.

4. **Service-time source mismatch**
   - `simulation/state_equations.py` fits service times from **developer stint durations** derived from `tickets_prs_merged.csv` (`dev_start_ts`/`dev_end_ts`, etc.).
   - ETL fit summaries (`fit_summary.csv`) are based on **ticket-level phase durations**. The simulator only reflects those ETL fits **if** `simulation/generate_sim_config.py` is executed.

---

## Final synthesis: dependencies, fragilities, and consistency risks

**Critical dependencies**
- `tickets_prs_merged.csv` is the single highest-impact CSV; it feeds configuration generation, state-equation artifacts, and validation baselines.
- `fit_summary.csv` is the only ETL output directly read by simulation tooling and validation diagnostics.

**Key fragilities**
- The pipeline assumes PR titles contain Jira keys; missing keys break the merge and degrade phase derivation.
- `fit_summary.csv` production can vary depending on the export script used, changing the selected distributions without changing downstream code.
- `generate_sim_config.py` depends on columns that are only created by `9_enrich_feedback_cols.py`, making that script implicitly required even though it is not part of the core ETL merge step.

**Potential inconsistency sources**
- Divergent service-time definitions (ticket-phase durations vs. developer stints) mean **ETL fits and simulator parameters can disagree** unless explicitly reconciled.
- Legacy/unknown CSV outputs (e.g., KDE-related exports) cannot be validated or reproduced from code, risking confusion during audits.

**Summary judgment**
- The codebase has a coherent ETL → merge → enrichment → fit → simulation/validation flow, but the **ETL outputs used by simulation are limited to `tickets_prs_merged.csv` and `fit_summary.csv`**. Everything else is either intermediate or diagnostic. Ensuring consistency between `fit_summary.csv` production and simulation config generation is the most important safeguard against silent drift.
