# ASF BookKeeper Simulation — Validation Plan

## 1. Purpose and scope
This plan defines how simulation metrics map to ASF BookKeeper operational data, what constitutes the “real system” proxy, and the acceptance criteria used to validate simulator outputs. It applies to end-to-end runs driven by `simulation/simulate.py` and to sweeps produced by `simulation/run_sweeps.py`. All times are expressed in **days**, matching the simulator configuration.

## 2. Real-system proxy and data sources
- **Primary proxy:** historical ASF BookKeeper workflow data extracted by the ETL pipeline (Jira + GitHub) over the window **2009-04-01–2017-10-18**. The ETL merges ticket and PR history in `etl/output/csv/tickets_prs_merged.csv`, including creation/closure timestamps, resolution states, and feedback markers. Service-time fits for DEV/REV/TEST are recorded in `etl/output/csv/fit_summary.csv` and reflected in `data/state_parameters/service_params.json`/`simulation/config.py`.
- **Arrival baseline:** exogenous backlog inflow calibrated to `ARRIVAL_RATE = 0.3075 tickets/day` in `simulation/config.py`; backlog is **equated to the DEV queue** for queue-length and wait metrics.
- **Feedback baseline:** `FEEDBACK_P_DEV` and `FEEDBACK_P_TEST` default to 0.0 (no forced rework) but ETL reopen counts in `tickets_prs_merged.csv` act as the empirical upper bound for rework tolerances.
- **Developer availability proxy:** steady-state occupancy implied by `matrix_P.csv` and observed `markov_time_in_states`/`avg_servers_*` from baseline runs; these form the denominator for utilization checks.
- **Synthetic baselines:** when ETL refreshes are unavailable, use the reproducible baseline outputs in `simulation/baseline_outputs/` (produced with the canonical seeds and state parameters) as the comparison target. Synthetic baselines are only acceptable when the ETL window or schema is unchanged.

## 3. KPI mapping to ETL observations
The table aligns simulator KPIs to measurable quantities or derived checks from the ETL exports. All simulator metrics come from `summary_stats.csv` and per-ticket fields in `tickets_stats.csv`.

| Simulator metric | Real-system observable / proxy | Notes on horizon & units |
| --- | --- | --- |
| `closure_rate`, `throughput_*` | Ratio of closed to arrived tickets per day using creation/closure timestamps in `tickets_prs_merged.csv`; compare per-stage throughput to completion counts inferred from phase durations and service fits in `fit_summary.csv`. | Horizon: 365-day simulation by default; compare to ETL window averaged to tickets/day. |
| `avg_service_time_*`, `avg_system_length_*`, `avg_queue_length_*` | Not directly observed; ETL phase durations (`phase_summary_stats.csv`) act as **service-time proxies**, not queue waits. Total wait is approximated by `resolution_time_days - sum(stage durations)` when available; per-stage queue lengths are **not** observable in ETL and are omitted from baseline comparisons. | Units are days; backlog = DEV queue. |
| `utilization_*` | Compare simulated busy time divided by average capacity to expected server exposure from `markov_time_in_states` (derived from `matrix_P.csv` steady state) and the observed developer count (`N_DEVS`/`TOTAL_CONTRIBUTORS` in config). | Expect utilization in [0,1]. |
| `rework_rate_*` | Measure reopen fractions in ETL (tickets returning to DEV after REVIEW/TEST) from `tickets_prs_merged.csv`; simulator rates should not exceed empirical reopen ratios when `FEEDBACK_P_*` stay at baseline. | When FEEDBACK rates are overridden upward, expect higher rework rates. |
| `markov_time_in_states`, `markov_stint_counts`, `markov_stint_means`, `avg_servers_*` | Compare to steady-state occupancy computed from `matrix_P.csv` and stint pmfs; ETL-derived stint distributions (per state PMF files) provide expected cycle timing. | Reported in developer-days over the horizon; divide by horizon to obtain average server counts. |
| `markov_time_in_states` consistency | Ensure total state time divided by horizon approximates `N_DEVS` (or configured headcount) to keep utilization denominators meaningful. | Applies per run and per sweep experiment. |

## 4. Acceptance criteria and tolerances
- **Closure and throughput alignment:**
  - Simulated `closure_rate` and `throughput_*` must be within **±10%** of the empirical tickets/day computed from the ETL window, after normalizing to the 365-day horizon. Deviations above 10% trigger manual review; above 20% are failures.
- **Service-time and queue metrics:**
  - `avg_service_time_*` should stay within **±20%** of the ETL-derived phase-duration means (service-time proxies, not queue waits). `avg_system_length_*` and `avg_queue_length_*` do not have ETL baselines; these are checked only for non-negativity and internal consistency, not against empirical CI bounds.
- **Utilization bounds:**
  - `utilization_*` must remain in **[0, 1.05]**. Values between 1.0 and 1.05 require justification (e.g., horizon clipping); above 1.05 fails. Average servers (`avg_servers_*`) should be within **±5%** of `N_DEVS * π_state` when using the canonical `matrix_P.csv` and seeds.
- **Rework rates:**
  - With baseline `FEEDBACK_P_DEV/TEST = 0`, simulated `rework_rate_*` should not exceed the ETL reopen ratio by more than **+5 percentage points**. When feedback probabilities are increased, `rework_rate_*` must rise monotonically with the configured probabilities; non-monotonic behavior triggers review.
- **Markov consistency:**
  - Sum of `markov_time_in_states` divided by horizon should match the configured headcount within **±1%**; deviations imply lost or duplicated developer time and fail validation.
- **Manual review triggers:**
  - Any tolerance breach, negative waits/service times, closure_rate outside [0,1], or Little’s Law violations reported by `simulation.verify` require manual analysis of the run configuration and ETL inputs before accepting results.

## 5. Monotonicity and consistency expectations
- **Arrival pressure:** Increasing `ARRIVAL_RATE` should increase WIP (`avg_queue_length_*`, `avg_system_length_*`) and waits/response times; closure throughput may saturate at service capacity but must not decrease without congestion evidence.
- **Capacity scaling:** Increasing `N_DEVS` or observed `avg_servers_*` should reduce waits and utilizations; throughput should weakly increase or stay flat (never decrease) unless bounded by arrival rate.
- **Feedback sensitivity:** Raising `FEEDBACK_P_TEST` or `FEEDBACK_P_DEV` should increase `total_wait`, `time_in_system`, `rework_rate_*`, and WIP; lowering feedback should not increase these metrics.
- **Service-time fits:** Changing service parameters according to `fit_summary.csv` updates should shift waits and queue lengths in the same direction as the mean service time change.

## 6. Real-system vs. synthetic baselines
- Prefer ETL-derived metrics for validation whenever the Jira/GitHub window matches the simulation inputs. Synthetic baselines (e.g., archived runs in `simulation/baseline_outputs/`) are acceptable only when:
  - The ETL window is unchanged and the same `matrix_P.csv`/service pmfs are in use.
  - Seeds and configuration match the baseline run (see Section 7).
  - Deviations are interpreted as regression checks rather than claims about real-system fidelity.

## 7. Reproducibility requirements
- **Seeds:** Use `GLOBAL_RANDOM_SEED` from `simulation/config.py` or override via the `BK_ASF_SIM_SEED` environment variable; the arrival, service-time, and state-transition streams have fixed subseeds for determinism.
- **State parameters:** Runs must reference `STATE_PARAMETER_PATHS` (transition matrix, service params, stint PMFs) from `simulation/config.py`; changes require re-validating against ETL fits.
- **Artifacts to retain:** Keep `summary_stats.csv`, `tickets_stats.csv`, run logs, and any `verification_report.md` produced by `simulation.verify`. For sweeps, also retain `aggregate_summary.csv`.
- **Baseline preservation:** Store copies of the exact config (`config_used.json` where applicable), seed values, and output CSVs for any run used as a validation anchor or regression reference.

### Baseline extractions (empirical reference)
- The script `validation/baseline_extract.py` reads `etl/output/csv/tickets_prs_merged.csv` and `etl/output/csv/fit_summary.csv` to export:
  - `validation/baseline_metrics.csv`: KPIs aligned to `simulation/output/summary_stats.csv` (arrival rate, closure rate, throughput_* per stage, service-time baselines, placeholders for queue/utilization, and rework proxies) with confidence bounds when available.
  - `validation/baseline_metadata.json`: provenance (source file hashes, ETL window, seed, config snapshot, state-parameter hashes) plus stage-level service-duration summaries.
- Configuration lives in `validation/baseline_config.yaml`; paths, seeds, and window overrides can be adjusted without code edits.
- Outputs are deterministic given fixed inputs/seeds and do **not** change simulator behavior; regenerate as needed to refresh “golden” baselines prior to validation runs.
- For queue length metrics (`avg_queue_length_*`), the baseline extractor writes `NaN` values to explicitly disable ETL comparisons because per-stage queue waits are not available in the current ETL schema.
