# Codex Prompt — ETL Distribution Fit Alignment (Simulation Fix)

Purpose: update the simulator’s service-time distributions and related parameters to reflect the latest ETL distribution fitting outputs.

## Prompt 1 — Align Simulator Distributions with Updated ETL Fits
- **Goal:** Update simulation distribution parameters and any dependent logic so the simulator reflects the latest ETL fit outputs, while preserving reproducibility and existing workflow semantics.
- **Context:** ETL has produced updated distribution fits (service-time parameters and arrival/feedback characteristics). The simulator’s distribution parameters and service-time generators must be aligned to these outputs to ensure validation consistency.
- **Files to read:**
  - `etl/output/csv/fit_summary.csv`
  - `etl/output/plots/*`
  - `etl/7_fit_distributions.py`
  - `etl/8_export_fit_summary.py`
  - `data/state_parameters/service_params.json`
  - `simulation/config.py`
  - `simulation/service_distributions.py`
  - `simulation/state_equations.py`
  - `simulation/workflow_logic.py`
  - `simulation/stats.py`
  - `docs/ETL_OVERVIEW_2.2C.md`
  - `docs/simulation/e2e_run_notes.md`
- **Files to change/create:**
  - Update `data/state_parameters/service_params.json` if parameters are stored there.
  - Update `simulation/config.py` (and related config files if present) to reference updated parameters.
  - Update `simulation/service_distributions.py` only if the parameter mapping or distribution logic must change.
  - Update `docs/simulation/e2e_run_notes.md` with a brief note of the updated fit alignment (only if documentation already tracks parameter changes).
- **Objectives:**
  - Extract the latest fitted parameters (shape/scale/loc or equivalent) from `etl/output/csv/fit_summary.csv` and map them to the simulator’s service-time distributions for each workflow stage.
  - Ensure any changes to `service_params.json` and/or `simulation/config.py` are deterministic and consistent with the ETL fitting methodology (as described in ETL scripts).
  - Verify distribution parameter usage in `simulation/service_distributions.py` aligns with the ETL fit definitions (e.g., lognormal parameterization, gamma shape/scale).
  - Preserve existing random seed behavior and reproducibility guarantees (no new RNGs or seeding logic unless required for correctness).
  - If the ETL fit implies changes to arrival or feedback parameters, update only the corresponding config values and note any modeling implications.
  - Run or update any verification steps already present in the repo if needed to confirm the new parameters import correctly and simulations still execute.
- **Output artifacts:**
  - Updated simulation parameter sources reflecting the latest ETL fits (config/service params).
  - Optional doc note summarizing which distributions were updated.
- **Definition of Done:**
  - Simulator uses the latest ETL fit parameters across all service-time distributions and any dependent config values.
  - No changes to model semantics beyond parameter updates unless explicitly required by the ETL fit.
  - Code imports cleanly and any existing verification scripts run without parameter-related errors.
