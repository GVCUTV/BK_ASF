# Validation Testing Guide

This guide explains how to exercise the ASF BookKeeper simulation validation suite end-to-end, confirm each check fires, and reproduce results locally. It assumes you have access to the repository and ETL outputs packaged with it.

## 1) Prerequisites & Setup
1. **Python & OS**
   - Python 3.7+ is required. Confirm with:
     ```bash
     python --version
     ```
     The project is Linux/macOS friendly; Windows works when using a virtual environment.
2. **Virtual environment (recommended)**
   - From the repo root:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
     ```
3. **Dependencies**
   - Install required packages:
     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```
4. **Inputs on disk**
   - Ensure the ETL outputs exist (used by baseline extraction and plausibility checks):
     - `etl/output/csv/tickets_prs_merged.csv`
     - `etl/output/csv/fit_summary.csv`
     - State parameter files under `data/state_parameters/` (matrix/stint PMFs/service params)
   - Baseline artifacts should be present (generated once and versioned):
     - `validation/baseline_metrics.csv`
     - `validation/baseline_metadata.json`
5. **Environment variables (optional overrides)**
   - `BK_ASF_SIM_SEED` overrides `GLOBAL_RANDOM_SEED` in `simulation/config.py`.
   - `SIMULATION_RANDOM_SEED` is accepted by the simulator but normally left unset because validation passes explicit seeds.
6. **Smoke checks**
   - Validate the baseline extractor imports and finds ETL inputs:
     ```bash
     python -m validation.baseline_extract --config validation/baseline_config.yaml --help
     ```
   - Confirm the validation runner CLI is available:
     ```bash
     python -m simulation.validate --help
     ```

## 2) Validation System Overview
- **What “validation” means**: The harness runs seeded scenarios, applies bounds/conservation checks, compares against empirical baselines, enforces monotonicity, and tests parameter plausibility against ETL fits. Reports and machine-readable JSON are produced per run.
- **Where logic lives**:
  - Scenario runner and report writer: `simulation/validate.py`
  - Core checks (bounds, conservation, baseline, monotonicity, plausibility): `validation/checks.py`
  - Baseline creation from ETL data: `validation/baseline_extract.py` with config `validation/baseline_config.yaml`
  - Sweep spec for monotonicity: `simulation/sweeps/validation_monotonicity.csv`
  - Reference docs: `docs/validation/validation_runner.md` and `docs/validation/validation_plan.md`
- **Artifacts produced per validation run** (under a timestamped `simulation/experiments/validation_*` folder):
  - `summary_stats.csv`, `tickets_stats.csv` (copied simulation outputs)
  - `config_used.json` (effective configuration snapshot)
  - `verification_report.md` (from `simulation.verify`)
  - `validation_report.md`, `validation_results.json` (overall status + details)
  - `distribution_checks.json` and optional plots under `validation/plots/` (plausibility diagnostics)
  - `validation.log` (runner log)

## 3) Run Validation End-to-End (Happy Path)
1. Activate your environment and ensure inputs exist.
2. Execute the seeded scenarios:
   ```bash
   python -m simulation.validate --outdir simulation/experiments --seed 22015001
   ```
   - The command creates `simulation/experiments/validation_YYYYMMDDTHHMMSS/` with five scenarios: `baseline`, `arrival_high`, `feedback_high`, `service_slow`, `capacity_high`.
3. Expected success signals:
   - Exit code `0`.
   - `validation_report.md` lists all scenarios with ✅ statuses and shows monotonicity/plausibility sections.
   - `validation_results.json` mirrors the report and records per-check booleans.
   - `distribution_checks.json` exists when baseline metadata is present.

## 4) Run and Interpret Individual Checks
Each category can be exercised without running the full suite.

### 4.1 Baseline extraction
- Command:
  ```bash
  python -m validation.baseline_extract --config validation/baseline_config.yaml
  ```
- Outputs: rewrites `validation/baseline_metrics.csv` and `validation/baseline_metadata.json` with hashes, seeds, and ETL provenance.
- Pass/Fail: Script exits 0; printed table shows arrival/closure rates and stage summaries. Missing inputs or NaNs indicate an extraction issue.
- Repro: Deterministic via `random_seed` in the config.

### 4.2 Single validation scenario
- Command:
  ```bash
  python -m simulation.validate --outdir simulation/experiments --seed 22015001
  ```
- Interpretation:
  - Bounds check: waits/utilization/closure_rate within ranges.
  - Conservation: arrivals vs ticket rows, closure rate recomputation, throughput vs cycle counts, Little’s Law.
  - Baseline comparison: only for `baseline` scenario using `validation/baseline_metrics.csv` with 10% relative tolerance.
  - Directionality: verified after all scenarios complete (see monotonicity below).

### 4.3 Distribution/plausibility checks only
- Command (standalone):
  ```bash
  python -m validation.distribution_diagnostics \
    --fit etl/output/csv/fit_summary.csv \
    --service-json data/state_parameters/service_params.json \
    --metadata validation/baseline_metadata.json \
    --output validation/distribution_checks.json \
    --plot-dir validation/plots
  ```
- Outputs: `distribution_checks.json` plus CDF comparison plots per stage when matplotlib is available.
- Interpretation: KS distance ≤ 0.2 and parameter drifts within 5% pass; larger deltas indicate drift from ETL fits.

### 4.4 Monotonicity sweep (CSV-driven)
- Command:
  ```bash
  python -m simulation.run_sweeps \
    --spec simulation/sweeps/validation_monotonicity.csv \
    --outdir simulation/experiments/validation_monotonicity
  ```
- Post-run, attach verification summaries (optional but recommended):
  ```bash
  python -m simulation.verify --mode sweep --input simulation/experiments/validation_monotonicity
  ```
- Outputs:
  - Per-experiment folders with summary/ticket stats and `config_used.json`.
  - Sweep-level `aggregate_summary.csv` and `validation_sweep_report.md` describing directionality/baseline deltas.
- Interpretation: Checks ensure `arrival_up` raises waits/WIP, `arrival_down` lowers them, `feedback_up` increases waits/lowers closure rate, and capacity adjustments move waits/utilization in the expected directions.

## 5) Negative / Fail-Fast Tests
Use these to prove the validators fire. Restore files with `git checkout -- <file>` after testing.

1. **Baseline mismatch failure**
   - Temporarily inflate an expected metric:
     ```bash
     python - <<'PY'
     import pandas as pd
     path = "validation/baseline_metrics.csv"
     df = pd.read_csv(path)
     df.loc[df.metric == "closure_rate", "value"] *= 10
     df.to_csv(path, index=False)
     PY
     python -m simulation.validate --outdir simulation/experiments --seed 22015001
     ```
   - Expected: `validation_report.md` shows a ❌ for `Baseline: closure_rate`; exit code is non-zero. Restore the file afterward.

2. **Plausibility drift failure**
   - Temporarily perturb service parameters used for comparison (non-destructive to runtime config):
     ```bash
     python - <<'PY'
     import json
     path = "validation/baseline_metadata.json"
     data = json.load(open(path))
     data["stage_info"]["dev"]["mean"] *= 5
     json.dump(data, open(path, "w"), indent=2)
     PY
     python -m validation.distribution_diagnostics \
       --fit etl/output/csv/fit_summary.csv \
       --service-json data/state_parameters/service_params.json \
       --metadata validation/baseline_metadata.json \
       --output /tmp/distribution_checks_bad.json
     ```
   - Expected: Output JSON marks failures for dev KS/parameter drift. Restore `validation/baseline_metadata.json` after the test.

3. **Monotonicity failure (sweep)**
   - Edit a copy of the sweep spec so `capacity_up` reduces contributors (flip to 10):
     ```bash
     cp simulation/sweeps/validation_monotonicity.csv /tmp/validation_monotonicity_bad.csv
     python - <<'PY'
     import pandas as pd
     path = "/tmp/validation_monotonicity_bad.csv"
     df = pd.read_csv(path, comment="#")
     df.loc[df.experiment_id == "capacity_up", "total_contributors"] = 10
     df.to_csv(path, index=False)
     PY
     python -m simulation.run_sweeps --spec /tmp/validation_monotonicity_bad.csv --outdir /tmp/validation_monotonicity_bad
     ```
   - Expected: The generated `validation_sweep_report.md` under `/tmp/validation_monotonicity_bad/` reports a failed `capacity_up/down` monotonicity check. Delete the temp folder and reuse the original spec for real runs.

## 6) Reproducibility & Determinism
- **Seeds**: `GLOBAL_RANDOM_SEED` defaults to `22015001` in `simulation/config.py`. The validation runner derives scenario seeds deterministically from the base seed. Override via `--seed` or `BK_ASF_SIM_SEED` when necessary.
- **Config snapshots**: Each scenario writes `config_used.json`; rerun comparisons use these to ensure inputs match.
- **Outputs to keep**: Preserve `summary_stats.csv`, `tickets_stats.csv`, `validation_report.md`, `validation_results.json`, and any sweep `aggregate_summary.csv` for audit. Generated plots/JSON under `validation/plots` and `validation/distribution_checks.json` document plausibility results.
- **Comparing runs**: Use `diff` on reports or `python - <<'PY'` snippets to compare JSON payloads. Example:
  ```bash
  diff -u runA/validation_results.json runB/validation_results.json
  ```

## 7) Troubleshooting
- **Missing dependencies / wrong Python**: Re-run `pip install -r requirements.txt`; check `python --version`.
- **Missing input files**: Ensure ETL CSVs and `data/state_parameters/*` exist. The baseline extractor and validation runner will warn or fail if `summary_stats.csv`/`tickets_stats.csv` are absent.
- **Validation artifacts not generated**: Inspect `validation.log` inside the run folder; confirm the simulator wrote `simulation/output/summary_stats.csv` and `tickets_stats.csv` before copying.
- **Flaky/non-deterministic results**: Pin `--seed` (or set `BK_ASF_SIM_SEED`) and avoid parallel runs sharing `simulation/output/`.
- **Schema changes in baselines**: Regenerate baselines with `validation/baseline_extract.py` after ETL schema updates; rerun validation.
- **Performance/memory issues**: Reduce sweep size (edit a temporary copy of the spec) or lower `sample_size` in distribution diagnostics; check system load.

## 8) CI Guidance
- No CI workflow is configured in-repo. To mimic a CI gate locally, run:
  ```bash
  python -m validation.baseline_extract --config validation/baseline_config.yaml
  python -m simulation.validate --outdir simulation/experiments --seed 22015001
  python -m simulation.run_sweeps --spec simulation/sweeps/validation_monotonicity.csv --outdir simulation/experiments/validation_monotonicity
  ```
- Inspect `validation_report.md` (single-run) and `validation_sweep_report.md` (sweep) for pass/fail status. Non-zero exits should be treated as CI failures.

## 9) Quick Checklist
Copy/paste and tick each item:
- [ ] Dependencies installed in virtualenv (`pip install -r requirements.txt`).
- [ ] ETL inputs present under `etl/output/csv/` and state parameters under `data/state_parameters/`.
- [ ] Baselines regenerated if upstream data changed (`python -m validation.baseline_extract --config validation/baseline_config.yaml`).
- [ ] Validation run executed (`python -m simulation.validate --outdir simulation/experiments --seed 22015001`) and exited 0.
- [ ] Monotonicity sweep executed (`python -m simulation.run_sweeps --spec simulation/sweeps/validation_monotonicity.csv --outdir simulation/experiments/validation_monotonicity`).
- [ ] Reports reviewed: `validation_report.md`, `validation_results.json`, `validation_sweep_report.md`, and (optionally) plots/`distribution_checks.json`.
- [ ] Negative tests performed and files restored.
