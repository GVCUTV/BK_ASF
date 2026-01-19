# Validation sweep layout

- **Spec**: `simulation/sweeps/validation_monotonicity.csv` enumerates baseline plus
  monotone stressors. Columns map directly to `simulation.config` overrides via
  `simulation.run_sweeps` (`validation_tag` is only for reporting/aggregation).
- **Run command** (from repo root):
  ```bash
  python -m simulation.run_sweeps \
    --spec simulation/sweeps/validation_monotonicity.csv \
    --outdir simulation/experiments/validation_monotonicity
  ```
- **Outputs**: each experiment folder stores `summary_stats.csv`,
  `tickets_stats.csv`, `config_used.json`, and the run log copy. The sweep root
  adds `aggregate_summary.csv` and `validation_sweep_report.md` that capture
  baseline deltas plus monotonicity checks.
