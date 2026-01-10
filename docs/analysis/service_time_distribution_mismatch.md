# Service-Time Distribution Mismatch — Lognormal (Simulation) vs Weibull (ETL)

## Executive summary
The repository contains **two distinct sources of service‑time modeling**:
1. **Simulation configuration and state-equation artifacts** that hard‑code **lognormal** fits (with `loc=0`) for DEV/REV/TEST, derived from *developer stint data* and persisted in `data/state_parameters/service_params.json`, then mirrored into `simulation/config.py`.
2. **ETL distribution fitting** over ticket/PR phase durations (`dev_duration_days`, `review_duration_days`, `test_duration_days`), which selects **Weibull** for DEV and TEST in the latest `etl/output/csv/fit_summary.csv`.

The mismatch is therefore not just a distribution choice; it stems from **different source datasets, different phase definitions, and different fitting pipelines**, plus a likely **configuration drift** between `fit_summary.csv` and `simulation/config.py`.

---

## Repo evidence map

| Area | Evidence | What it shows |
| --- | --- | --- |
| Simulation config | `simulation/config.py` (`SERVICE_TIME_PARAMS`) | DEV/REV/TEST are **lognorm** with only `s` and `scale`, no `loc` shift. |
| Service-time sampling | `simulation/service_distributions.py` | Sampling uses lognormal/weibull RNGs, applies optional `loc`, and rejects non‑positive samples. |
| Workflow usage | `simulation/workflow_logic.py` | Every service start calls `sample_service_time(stage)` and records it in stats. |
| State‑equation fit source | `simulation/state_equations.py` | Fits **lognormal** with `scipy.stats.lognorm.fit(..., floc=0)` on developer stints and writes `service_params.json`. |
| Persisted service params | `data/state_parameters/service_params.json` | DEV/REV/TEST lognormal μ/σ values (matches `config.py`). |
| ETL phase definition | `etl/3_clean_and_merge.py` | DEV/REV/TEST durations defined from ticket created → PR created → PR merged/closed → ticket resolved. |
| ETL fitting | `etl/7_fit_distributions.py` | Fits lognorm/weibull/expon/norm to phase durations, with KDE+curve_fit and tail truncation. |
| ETL selection output | `etl/output/csv/fit_summary.csv` | DEV/TEST winners are **weibull_min**, REVIEW is **lognorm**. |
| Docs linking lognormal | `docs/DERIVATIONS_3.2A.md`, `docs/ETL_OVERVIEW_2.2C.md` | Both assert **lognormal** service‑time fits tied to `service_params.json`. |

---

## Simulation pipeline (what the simulator actually does)

### 1) Configuration source and parameterization
- `simulation/config.py` defines `SERVICE_TIME_PARAMS` for each stage. DEV/REV/TEST are **lognorm** with parameters `{s, scale}` and no explicit `loc`, so the lognormal is *implicitly unshifted*.
- Those values are numerically consistent with `data/state_parameters/service_params.json` (lognormal μ/σ), i.e., `scale = exp(mu)` and `s = sigma`.

### 2) Sampling logic
- `sample_service_time(stage)` in `simulation/service_distributions.py`:
  - Uses a per‑stream RNG.
  - For lognormal: `np.random.lognormal(mean=log(scale), sigma=s)`. The `loc` parameter is **not** part of the RNG call; it is **added afterwards**, if provided.
  - Rejects non‑positive values by resampling up to 50 times, then clips to `1e-6` if still non‑positive.
- There is **no truncation** (other than positivity), **no rounding**, and **no mixture** logic in sampling.

### 3) Stage usage and recording
- `WorkflowLogic.try_start_service` calls `sample_service_time(stage)` for every stage and records the `service_time` into the per‑ticket stats output, so the service times are **exactly the samples drawn from the configured distribution**.

### 4) Alternative “service” definitions used elsewhere
- `simulation/state_equations.py` fits lognormal distributions with `floc=0` on *developer stint durations* and persists them as `data/state_parameters/service_params.json`.
- These stints are derived from developer assignment intervals (`dev_start_ts`, `dev_end_ts`, etc.) and are **not identical** to ticket‑level phase durations. This is a key source of mismatch.

**Conclusion (simulation side):** the simulator uses the distributions configured in `simulation/config.py` and does **not** read or adapt to `etl/output/csv/fit_summary.csv` unless `simulation/generate_sim_config.py` is explicitly run to regenerate the config.

---

## ETL pipeline (what the ETL actually fits and why it selects Weibull)

### 1) Service‑time dataset and definitions
- `etl/3_clean_and_merge.py` defines phase durations as:
  - **Development:** `fields.created → first PR created_at`
  - **Review:** `first PR created_at → last PR merged_at (or closed_at)`
  - **Testing:** `review_end → fields.resolutiondate`
- These durations are stored in `tickets_prs_merged.csv` as `dev_duration_days`, `review_duration_days`, and `test_duration_days`.

This definition implicitly includes **queueing, idle, and coordination delays** (e.g., time between ticket creation and first PR, or time between review end and resolution), which can shift distribution shapes away from per‑developer stints.

### 2) Cleaning and truncation
- In `etl/7_fit_distributions.py`:
  - Series are coerced to numeric and filtered to **non‑negative** values.
  - A hard cap is applied: `MAX_DAYS = 3650` (10 years). This is a form of right‑tail truncation.
- **Zero‑length durations are kept**, which is problematic for lognormal fits (strictly positive support) but permissible for Weibull when using a negative `loc` shift.

### 3) Fitting and selection
- ETL fits **Lognormal, Weibull (weibull_min), Exponential, Normal** to each phase using KDE + `curve_fit`, with MSE between KDE and PDF as the loss in `7_fit_distributions.py`.
- `fit_summary.csv` is then generated with the winning distribution in SciPy naming.
  - The current `etl/output/csv/fit_summary.csv` lists **weibull_min** for `dev` and `testing`, and **lognorm** for `review`.
  - Stage‑specific detail files (e.g., `distribution_fit_stats_development.csv` and `distribution_fit_stats_testing.csv`) show the Weibull rows with the lowest MAE/MSE and **negative `loc` shifts**.

**Conclusion (ETL side):** the ETL fits are based on ticket lifecycle phase durations, use KDE‑based curve fitting with truncation, and the current exported summary explicitly prefers **Weibull** for DEV and TEST.

---

## Mismatch hypotheses (confirmed/denied with evidence)

### 1) Different target variable (confirmed — **very likely**)
- **Simulation:** service times are sampled from `SERVICE_TIME_PARAMS`, which align with `service_params.json` generated from **developer stints** (state‑equation data).
- **ETL:** service times are **ticket phase durations** from creation → PR events → resolution.
- These are **not the same variable**, so distribution differences are expected.

### 2) Censoring / truncation (confirmed — **likely**)
- ETL truncates tails at `MAX_DAYS = 3650` and filters to non‑negative values.
- Simulation does not truncate upper tails; it only enforces positivity.
- Tail truncation can push best‑fit distributions toward Weibull shapes.

### 3) Shifts (offsets) via `loc` (confirmed — **likely**)
- ETL fit summary for DEV/TEST includes **negative `loc`** values for Weibull fits.
- Simulation config’s lognormal parameters **do not include `loc`**, and state‑equations fit is explicitly `floc=0`.
- This offset mismatch alone can invert best‑fit comparisons across distributions.

### 4) Parameterization mismatch (not confirmed — **possible but unproven**)
- Simulation lognormal parameterization uses `s` and `scale` (`mu = log(scale)`), which is consistent with SciPy’s lognorm.
- No evidence of a wrong transformation is present in the current code.
- The mismatch appears to be **a source‑data issue**, not a formula bug.

### 5) Model selection bug (possible — **medium risk**)
- The ETL selection logic is split between `7_fit_distributions.py` (MSE on KDE) and `8_export_fit_summary.py` (MAE with AIC/BIC tiebreakers).
- The output files in `etl/output/csv/` show `MAE_KDE_PDF` columns, while the current fitting script writes `MSE_KDE_PDF`. This suggests **version drift** between scripts and outputs.
- A mismatch here could lead to different winners depending on which script produced the current `fit_summary.csv`.

### 6) Sampling source mismatch (confirmed — **very likely**)
- `simulation/config.py` currently reflects lognormal parameters that match `data/state_parameters/service_params.json`, **not** the `etl/output/csv/fit_summary.csv` values.
- `simulation/generate_sim_config.py` would read `fit_summary.csv` and could output Weibull, but it has **not been run** against the current ETL outputs.

### 7) Phase mapping mismatch (confirmed — **likely**)
- ETL defines DEV/REV/TEST boundaries using ticket + PR timestamps; simulation uses abstract queues and developer stages.
- Review end in ETL is last PR merged/closed, which may include waiting time that simulation treats as queue or service time differently.

### 8) Mixture / heterogeneity (plausible — **likely**)
- ETL fits are computed on **aggregate** stage data with no segmentation by issue type, priority, contributor, or era.
- A mixture of ticket types can shift a best‑fit distribution toward Weibull even if some sub‑populations are lognormal.

### 9) Time unit mismatch (unlikely — **low**)
- Both simulation and ETL explicitly use **days** as the unit for service times. No unit conversion mismatch is evident.

### 10) RNG/seed artifacts (unlikely — **low**)
- Simulation logs the configured distribution at start and then samples directly from that distribution; there is no post‑transformation that would implicitly emulate Weibull.

### 11) Rounding/discretization (unlikely — **low**)
- ETL uses continuous durations in days with no rounding before fitting; discretization effects are not evident in the fitting pipeline.

### 12) Boundary conditions / zeros (possible — **medium**)
- ETL keeps zero‑length durations after non‑negative filtering. Lognormal distributions cannot model zeros, which can bias selection in favor of Weibull with negative `loc`.

---

## Decision trail: where “lognormal” and “weibull” claims come from

### Lognormal (simulation side)
- `simulation/config.py` explicitly configures DEV/REV/TEST as `lognorm`.
- `data/state_parameters/service_params.json` contains lognormal μ/σ for DEV/REV/TEST, derived from state‑equation fits.
- Documentation (`docs/DERIVATIONS_3.2A.md`, `docs/ETL_OVERVIEW_2.2C.md`) asserts lognormal service times based on those artifacts.

### Weibull (ETL side)
- `etl/output/csv/fit_summary.csv` declares **weibull_min** for DEV and TEST.
- `etl/output/csv/distribution_fit_stats_development.csv` and `distribution_fit_stats_testing.csv` show Weibull rows with the lowest error metrics.

---

## Next steps (read‑only checks / experiments)

1. **Re-run `simulation/generate_sim_config.py` on the current ETL outputs** (no edits) to see whether it produces Weibull in `SERVICE_TIME_PARAMS`.
   - **Expected outcome:** if `fit_summary.csv` is the source of truth, the regenerated config should show `weibull_min` for dev/testing.
2. **Run `validation/checks.py` distribution comparison** (if available in your environment) using the current config, `fit_summary.csv`, and `service_params.json`.
   - **Expected outcome:** the check should flag a distribution mismatch for dev/testing and quantify param drift.
3. **Sanity‑check the source dataset alignment**:
   - Compare the ticket‑phase durations (`dev_duration_days`, `test_duration_days`) vs. developer stints used by `state_equations.py` to confirm they are distinct measures.
4. **Align ETL and simulation definitions**:
   - Decide whether “service time” should be a *ticket lifecycle duration* (current ETL) or *developer active stint* (state‑equation artifacts). Pick one and make both pipelines use the same source.
5. **Fix the fit-summary generator drift**:
   - Ensure a single script is responsible for `fit_summary.csv`, and verify that selection uses a consistent metric (MAE vs MSE), to avoid silent winner flips.

---

## What is missing (if you want deeper certainty)
- The actual ETL run logs or notebooks that produced the current `fit_summary.csv`, if they are external to the repo.
- A small anonymized sample (or summary statistics) of the raw phase‑duration data to validate whether zeros / truncations are driving the Weibull preference.
