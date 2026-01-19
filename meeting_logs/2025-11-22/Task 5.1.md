# Meeting 5 — Task 5.1 (E2E Integrated Run)
## Steps 1–8 — What Has to Be Done

This document describes **only the actions that must be completed** for Steps 1 through 8 of Task 5.1, aligned with the current BK_ASF repository structure.

---

## **1. Validate Configuration (`simulation/config.py`)**
- Ensure all state parameter file paths in `STATE_PARAMETER_PATHS` are correct.
- Confirm the following files exist and are readable:
  - `data/state_parameters/matrix_P.csv`
  - `data/state_parameters/service_params.json`
  - `data/state_parameters/stint_PMF_DEV.csv`
  - `data/state_parameters/stint_PMF_OFF.csv`
  - `data/state_parameters/stint_PMF_REV.csv`
  - `data/state_parameters/stint_PMF_TEST.csv`
- Verify seed logic:
  - `GLOBAL_RANDOM_SEED` is defined.
  - Optional override via `BK_ASF_SIM_SEED` is recognized.

---

## **2. Initialize the Simulation Environment**
- Ensure directories referenced in `config.py` (logs, output) exist.
- Remove any previous logs or outputs if needed:
  ```
  rm -f simulation/logs/*.log
  rm -f simulation/output/*.csv
  ```
- Ensure Python path resolution in `simulate.py` works correctly.

---

## **3. Run the Simulation**
- Execute the simulator:
  ```
  python -m simulation.simulate
  ```
- Confirm:
  - Logging initializes in the correct path.
  - State validation passes.
  - DeveloperPool initializes with Markov matrix + PMFs.
  - SystemState and queues are created.
  - First arrival is scheduled at `t=0`.
- Allow the simulation to run until the time horizon is reached.

---

## **4. Validate Event Loop Operation**
Check that the simulation:
- Processes arrivals in increasing time order.
- Creates tickets and enqueues them correctly.
- Starts dev_review and testing services using service distributions.
- Applies feedback routing (dev_review ↔ testing).
- Applies Markov state transitions for developers.
- Terminates cleanly at the horizon.

Evidence comes from:
- `simulation/logs/simulation.log`
- `simulation/logs/simulation_stats.log`
- The content of `tickets_stats.csv`.

---

## **5. Validate Generated Outputs**
Verify:
- The presence of:
  - `simulation/output/tickets_stats.csv`
  - `simulation/output/summary_stats.csv`
- Internal consistency:
  - Arrival times strictly increasing.
  - `tickets_arrived` = number of rows in tickets file.
  - `tickets_closed` matches summary.
  - `time_in_system = closed_time - arrival_time` for closed tickets.
  - Wait times ≥ 0.
  - Markov aggregates present (time in states, stint counts, means).

---

## **6. Validate Reproducibility**
Perform two runs with the same seed:

```
export BK_ASF_SIM_SEED=42
python -m simulation.simulate
cp simulation/output/*.csv reproducibility/run1/
python -m simulation.simulate
cp simulation/output/*.csv reproducibility/run2/
diff run1/tickets_stats.csv run2/tickets_stats.csv
diff run1/summary_stats.csv run2/summary_stats.csv
```

Outputs should match exactly.

---

## **7. Create a Baseline Snapshot**
- Create directory:
  ```
  mkdir -p simulation/baseline_outputs
  ```
- Save:
  - `tickets_stats.csv`
  - `summary_stats.csv`
  - Optional: `metadata.txt` containing seed and date.

This becomes the official baseline for later validation steps.

---

## **8. Document the E2E Run**
Create or update:
```
docs/e2e_run_notes.md
```

Include:
- Execution command and seed value.
- Initialization summary.
- Event loop behavior.
- Output artifacts.
- Consistency checks.
- Baseline snapshot location.
- Reproducibility status.

This completes Task 5.1 (Steps 1–8).

