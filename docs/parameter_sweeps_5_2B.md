// v1
// file: docs/parameter_sweeps_5_2B.md
# Parameter Sweeps — Step 5.2B (semi‑Markov policy)

## 1 ▪ Overview
- **Goal.** I sweep selected inputs to stress the semi‑Markov developer policy (states **DEV**, **REV**, **TEST**, **OFF** with backlog feeding DEV) and observe queueing outcomes. The main axes are the external **ARRIVAL_RATE**, the **feedback** probabilities that route tickets back to DEV from REV/TEST, and optional Markov parameters (e.g., stint scalers) that reshape time spent per state.
- **Runner.** From repo root, execute:
  ```bash
  python -m simulation.run_sweeps --spec simulation/sweeps/5_2B_sweeps.csv --outdir experiments/5_2B
  ```
  `--spec` points to a CSV sweep file; `--outdir` controls where experiment folders are created. `--limit` caps how many rows are run; `--skip-aggregate` suppresses the aggregate CSV.
- **Where results land.** Each experiment is written under `<outdir>/<experiment_id>` with copies of the per-run outputs and the config snapshot used. An aggregate table is emitted at `<outdir>/aggregate_summary.csv` when aggregation is enabled.

## 2 ▪ Sweep specification format
- **File shape.** CSV with headers; comment lines starting with `#` and blank lines are ignored. The first column must be `experiment_id`; remaining columns supply overrides.
- **Core fields.**
  - `experiment_id`: label for the experiment folder.
  - Arrival parameters: `arrival_rate` maps to `ARRIVAL_RATE` (tickets/day).
  - Feedback parameters: `feedback_dev` → `FEEDBACK_P_DEV`, `feedback_test` → `FEEDBACK_P_TEST`.
  - Markov/policy parameters: any column not in the explicit map is uppercased and applied as a config override (e.g., `markov_stint_scaler` or churn weights) so you can scale stint pmfs or tweak transition intensities without altering the runner.
  - Seeds/horizon: `global_seed` → `GLOBAL_RANDOM_SEED`; `sim_duration` → `SIM_DURATION` (days simulated).
- **Default spec.** `simulation/sweeps/5_2B_sweeps.csv` illustrates the format with baseline arrival/feedback pairs plus optional policy knobs.

## 3 ▪ Per-experiment outputs
Each experiment folder contains:
- `summary_stats.csv`: one row per metric with `metric,value,units,description`. Includes closure ratio, per-stage throughput, mean waits, average queue lengths (backlog and service queues), utilization derived from developer state time, rework rates, and Markov policy observables (`markov_time_in_states`, `markov_stint_counts`, `markov_stint_means`).
- `tickets_stats.csv`: per-ticket timeline including waits per queue, time in system, cycle counts through DEV/REV/TEST, and observed stint counts per developer state. Useful to trace how backlog-fed DEV pulls propagate to REV/TEST under the semi‑Markov policy.
- `config_used.json`: snapshot of the fully resolved simulation config after applying row overrides (arrival rates, feedback, state-time scalers, seeds, horizon, etc.).
- `run.log`: copy of the simulation log for that run (includes queueing events and developer-state accrual consistent with DEV/REV/TEST/OFF terminology).

## 4 ▪ Aggregate summary
- **Location.** `<outdir>/aggregate_summary.csv` when aggregation is enabled.
- **Columns.** Begins with `experiment_id`, followed by the parameters present in the spec file, then the metric set aggregated from each run (`closure_rate`, `throughput_dev|review|testing`, `avg_wait_*`, `avg_queue_length_*`, `utilization_*`, rework rates, and Markov metrics).
- **Interpretation.**
  - `closure_rate`: closed/arrived tickets within the horizon.
  - `throughput_*`: completions per day for DEV/REV/TEST; align with the corresponding service stages.
  - `avg_wait_*`: average queue delay before each service stage; `avg_queue_length_dev` reuses the backlog queue area because DEV pulls directly from backlog.
  - `avg_queue_length_*`: time-weighted queue lengths for backlog/DEV/REV/TEST.
  - `utilization_*`: busy time divided by available stint time for developers in each stage.
  - `markov_time_in_states`, `markov_stint_counts`, `markov_stint_means`: summarize time spent and stint realizations in the semi‑Markov policy across **DEV**, **REV**, **TEST**, **OFF**, keeping terminology aligned with analytical_model.md and the Markov policy documents.

## 5 ▪ Terminology alignment
- States remain **DEV**, **REV**, **TEST**, **OFF**; the backlog queue feeds DEV and is tracked separately from service queues. Feedback routes from REV/TEST return work to DEV per the Markov routing matrix and service logic.
- Stints are the semi‑Markov sojourns in each state; stint counts and means in the outputs should be read as empirical realizations of those sojourns, supporting comparisons against the fitted pmfs and transition matrix documented in `analytical_model.md` and related state-parameter files.
- Metrics reference the same dev/review/testing stages used elsewhere (no new states introduced) so sweep outputs plug directly into the queueing equations and policy narratives already circulated.
