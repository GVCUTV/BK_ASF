# E2E Run Notes (BK_ASF Simulation)

## 1. Run Configuration

### Execution Command
```
python -m simulation.simulate
```

### Seed Used
- Default from `simulation/config.py` (`GLOBAL_RANDOM_SEED`)
- Or overridden via:
```
export BK_ASF_SIM_SEED=42
```

### State Parameter Files Used
- `data/state_parameters/matrix_P.csv`
- `data/state_parameters/service_params.json`
- `data/state_parameters/stint_PMF_DEV.csv`
- `data/state_parameters/stint_PMF_REV.csv`
- `data/state_parameters/stint_PMF_TEST.csv`
- `data/state_parameters/stint_PMF_OFF.csv`

These are referenced via `STATE_PARAMETER_PATHS` in `simulation/config.py`.

---

## 2. Initialization Summary

The simulation correctly:
- Validated all required state parameter files.
- Initialized:
  - DeveloperPool with proper transition matrix and PMF stint distributions.
  - 44 developers sampled from stationary distribution.
  - SystemState with empty queues.
  - WorkflowLogic and Stats modules.
  - EventQueue (priority queue).
- Scheduled the first ticket arrival at `t = 0.0`.

---

## 3. Event Loop Verification

Evidence from logs confirms:
- 116 Poisson arrivals occurred during the horizon.
- Tickets were created and routed through queues.
- Service processes for both dev_review and testing started normally.
- Feedback loops occurred (tickets with >1 review or test cycle).
- Developer Markov transitions occurred (REV→DEV, TEST→OFF, etc.).
- The simulation terminated cleanly at the horizon (365 days).

---

## 4. Output Artifacts

Generated outputs include:

### Mandatory CSVs
- `simulation/output/tickets_stats.csv`
- `simulation/output/summary_stats.csv`

### Logs
- `simulation/logs/simulation.log`
- `simulation/logs/simulation_stats.log`

These contain all ticket-level, stage-level, and developer-level metrics needed for validation.

---

## 5. Consistency Checks

Verified:
- `tickets_arrived = 116` matches logs and summary.
- `tickets_closed = 10` matches logs and summary.
- `closure_rate = 10 / 116` correctly computed.
- Arrival times are strictly non-decreasing.
- Closed tickets have `time_in_system = closed_time - arrival_time`.
- All wait times are ≥ 0.
- Summary includes:
  - `markov_time_in_states`
  - `markov_stint_counts`
  - `markov_stint_means`

---

## 6. Baseline Snapshot Created

Created directory:
```
simulation/baseline_outputs/
```

Saved:
- `tickets_stats.csv`
- `summary_stats.csv`
- Optional: `metadata.txt`

This snapshot serves as baseline “golden output”.

---

## 7. Reproducibility Result

The simulation was re-run using the same seed.

To compare:
```
diff run1/tickets_stats.csv run2/tickets_stats.csv
diff run1/summary_stats.csv run2/summary_stats.csv
```

Both files must match exactly for reproducibility.

Logs may differ in timestamps but should not differ in message sequence beyond timing.

---

## 8. Summary

The E2E simulation:
- Initializes correctly.
- Runs the event loop correctly.
- Produces coherent and consistent outputs.
- Exhibits developer Markov transitions.
- Terminates at horizon.
- Is reproducible given a fixed seed.
- Produces baseline artifacts ready for Steps 5.2A, 5.2B, and 5.2C.

This completes Step 8 of Meeting 5 for BK_ASF.
