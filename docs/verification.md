# Verification guide

Use `simulation.verify` to confirm that simulation outputs are self-consistent before consuming them in analysis or regression comparisons. The verifier inspects per-ticket microdata and summary aggregates to catch drift in the dev queue/backlog workflow measurements.

## Running the verifier

- Single run (default):
  ```bash
  python -m simulation.verify --input simulation/output
  ```
  The input directory must contain `summary_stats.csv` and `tickets_stats.csv`. A Markdown report (`verification_report.md`) is written inside the same directory.

- Sweep mode:
  ```bash
  python -m simulation.verify --mode sweep --input simulation/output
  ```
  When `--mode` is omitted, the verifier auto-detects sweep layouts whenever `--input` contains subdirectories with both CSV files. Sweep mode writes a report to each experiment folder plus a consolidated report in the sweep root.

Useful flags:
- `--fail-fast` stops on the first failing check.
- `--tolerance` (default `1e-6`) sets the absolute tolerance used in numeric comparisons.
- `--mean-jobs-rel-tolerance` (default `0.02`) sets the relative tolerance for Little’s mean-jobs identity checks.

Exit code is `0` when all checks pass and `1` otherwise. Reports list each check with ✅/❌ so you can pinpoint the failure source.

## Checks enforced (A–F)

A. **Required artifacts and metrics** — Ensures `summary_stats.csv` and `tickets_stats.csv` exist, parse correctly, and include `tickets_arrived`, `tickets_closed`, and `closure_rate` (stage averages use the “service_time>0 or cycles>0” inclusion rule).

B. **Summary sanity** — Confirms throughput, waits, and queue lengths are non-negative and per-stage utilizations stay within `[0, 1]`; validates Little’s mean-jobs identity `L = Lq + (avg_servers × utilization)` for dev, review, and testing within the configured relative tolerance.

C. **Flow conservation** — Checks that `tickets_arrived` matches ticket row counts, `tickets_closed` matches rows with `closed_time`, and `closure_rate` equals `tickets_closed / tickets_arrived`.

D. **Time accounting** — Verifies `mean_time_in_system` matches the closed-ticket average, waits and service times are non-negative with `time_in_system ≥ total_wait`, stage cycle counts align with waits/services, and `total_wait` equals the sum of stage waits.

E. **Stage means and Little identities** — Compares per-stage wait means in `summary_stats.csv` to microdata averages built from tickets that entered each stage, and checks per-stage Little identities `E[T] = E[wait] + E[service]` under the same inclusion rule.

F. **Sweep aggregate alignment** (sweep mode only) — Validates `aggregate_summary.csv` exists, includes required columns (`experiment_id` plus summary metrics), has one row per experiment directory, and that each aggregate metric matches the corresponding per-experiment summary value.

## Output locations

- Single run: `verification_report.md` is written to the provided `--input` directory.
- Sweep: each experiment directory receives its own `verification_report.md`, and the sweep root gets a consolidated report that summarizes per-experiment status and aggregate alignment.

Interpret failures by opening the report to see the first ❌ entry; use the details to trace back to the offending metric or ticket row. Adjust tolerances only when differences reflect expected floating-point noise rather than modeling changes.
