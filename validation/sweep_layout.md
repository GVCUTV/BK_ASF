# Validation sweep layout

This sweep isolates monotonicity and stress scenarios using a CSV spec consumable by `simulation.run_sweeps`.

## Spec columns
- `experiment_id`: folder name for the run.
- `validation_case`: semantic tag used by the sweep report (baseline/arrival_up/arrival_down/feedback_up/capacity_up).
- `arrival_rate`: ARRIVAL_RATE override.
- `feedback_dev`, `feedback_test`: FEEDBACK_P_DEV / FEEDBACK_P_TEST overrides.
- `total_contributors`: TOTAL_CONTRIBUTORS override for capacity perturbations.
- `global_seed`: GLOBAL_RANDOM_SEED override used per row.
- `sim_duration`: SIM_DURATION override (days).

## Expected output tree
```
simulation/experiments/validation_monotonicity/
  baseline/
    summary_stats.csv
    tickets_stats.csv
    config_used.json
  arrival_high/
  arrival_low/
  feedback_high/
  capacity_high/
  aggregate_summary.csv
  validation_sweep_report.md
```
`validation_sweep_report.md` is produced automatically after the aggregate CSV when the spec includes a `validation_case` column.
