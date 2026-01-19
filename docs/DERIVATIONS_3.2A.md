// v3.2A-003
// file: docs/DERIVATIONS_3.2A.md

# Meeting 3.2A — State Equation Derivations

## Overview
This note documents the analytical layer implemented in [`simulation/state_equations.py`](../simulation/state_equations.py) that converts ETL outputs into simulation-ready parameters for the semi-Markov developer model. The workflow uses the merged Jira/GitHub dataset at `etl/output/csv/tickets_prs_merged.csv` as the single source of empirical timelines for developer assignments. Queue and state labels for Jira events follow the canonical mapping in [`docs/JIRA_WORKFLOW_MAPPING_2.2A.md`](JIRA_WORKFLOW_MAPPING_2.2A.md) to keep analytical derivations aligned with the conceptual workflow.

## Developer state semantics, stints, and overlap logic
The developer-state set \(\mathcal{S} = \{\text{OFF}, \text{DEV}, \text{REV}, \text{TEST}\}\) matches the definitions enumerated in [`docs/CONCEPTUAL_WORKFLOW_MODEL.md`](CONCEPTUAL_WORKFLOW_MODEL.md) and is summarized here for traceability:

- **OFF** — downtime between contributions so that each developer’s effective effort remains bounded by the **≈7.5 net productive hours** cited in [`docs/schedule.md`](schedule.md).
- **DEV** — implementation focus on code edits with service durations characterized by the \(T_{DEV}\) samples recorded in `data/state_parameters/service_params.json`.
- **REV** — code-review focus that consumes \(T_{REV}\) and executes the overlap-weighted peer feedback captured by the ETL pipeline.
- **TEST** — verification focus handling regression and integration cycles driven by \(T_{TEST}\).

Contiguous time spent in each state forms the stint distribution \(f_i(\ell)\), exported as `stint_PMF_<STATE>.csv` and referenced in both the analytical model and simulation layers. The overlap-weighting logic described in [`docs/schedule.md`](schedule.md) and [`docs/Schedule_Prompts.md`](Schedule_Prompts.md) adjusts raw ticket effort so that concurrent developers on a single ticket count once toward the net-availability budget. This keeps the \(\approx 7.5\)-hour planning envelope consistent with the capacity formulas in [`docs/analytical_model.md`](analytical_model.md) and the developer-availability metrics in [`docs/key_metrics_3.2C.md`](key_metrics_3.2C.md).

## Transition Matrix \(P\)
The developer state transition probabilities are derived from chronological stage events per contributor. For each developer, observed state changes yield empirical counts \(n_{ij}\) from state \(i\) to state \(j\). Laplace smoothing with \(\alpha = 1\) enforces non-zero mass across all outcomes:
\[
P_{ij} = \frac{n_{ij} + \alpha}{\sum_k n_{ik} + \alpha \cdot |\mathcal{S}|}
\]
where \(\mathcal{S} = \{\text{OFF}, \text{DEV}, \text{REV}, \text{TEST}\}\). The resulting matrix is written to `data/state_parameters/matrix_P.csv`.

**Summary of \(P\)**

| from \ to | OFF | DEV | REV | TEST |
|-----------|-----|-----|-----|------|
| OFF | 0.0078 | 0.5504 | 0.1783 | 0.2636 |
| DEV | 0.0051 | 0.3112 | 0.6480 | 0.0357 |
| REV | 0.1735 | 0.2908 | 0.2194 | 0.3163 |
| TEST | 0.8230 | 0.0619 | 0.0265 | 0.0885 |

## Stint-Length PMFs \(f_i(\ell)\)
For each state \(i\), the procedure aggregates contiguous sojourn durations into stint samples. Durations are rounded to \(10^{-3}\) days to form discrete support points \(\ell\). The probability mass function is estimated via:
\[
 f_i(\ell) = \frac{c_i(\ell)}{\sum_{\ell'} c_i(\ell')}
\]
with counts \(c_i(\ell)\) drawn from observed stint lengths, and exported as `stint_PMF_<STATE>.csv` (columns `length,prob`). OFF-state gaps correspond to idle intervals between assignments of the same developer.

## Service-Time Distributions \(T_s\)
Service times for the active queues (\(s \in \{\text{DEV}, \text{REV}, \text{TEST}\}\)) are fit with log-normal laws by maximum likelihood:
\[
\hat{\sigma}_s, \hat{\mu}_s = \arg\max_{\sigma,\mu} \prod_{x \in \mathcal{D}_s} \text{LogNormal}(x; \mu, \sigma)
\]
using \(\texttt{scipy.stats.lognorm.fit}\) with \(\text{loc} = 0\). The parameters are reported in natural-log space and persisted in `data/state_parameters/service_params.json`.

| Stage | Samples | Distribution | \(\hat{\mu}\) | \(\hat{\sigma}\) |
|-------|---------|--------------|---------------|----------------|
| DEV | 192 | Log-normal | -0.5838 | 4.7425 |
| REV | 192 | Log-normal | 1.7868 | 2.3344 |
| TEST | 109 | Log-normal | -5.9267 | 4.5370 |

## Validation Notes
The module includes stubs (`validate_transitions`, `validate_stint`) for future statistical checks. Recommended tests include a \(\chi^2\) goodness-of-fit over transition frequencies and Kolmogorov–Smirnov comparisons of stint distributions between empirical and simulated traces.

## Determinism and Versioning
All generated files contain the ASF banner `v3.2A-001` and are produced deterministically from the aforementioned ETL snapshot. Re-running `python -m simulation.state_equations` will reproduce the same artifacts provided the source dataset remains unchanged.

## Documentation Cross-References
- [`docs/CONCEPTUAL_WORKFLOW_MODEL.md`](CONCEPTUAL_WORKFLOW_MODEL.md) — source of the workflow semantics and developer-state assumptions duplicated in this derivation log.
- [`docs/analytical_equations_3.2A.md`](analytical_equations_3.2A.md) — consumes the parameters derived here and restates the governing equations for the analytical pipeline.
- [`docs/analytical_model.md`](analytical_model.md) — integrates the derived \(P\), \(f_i\), and \(T_s\) into the queueing network description prior to simulation.
- [`docs/key_metrics_3.2C.md`](key_metrics_3.2C.md) — references the same availability, throughput, and capacity symbols to maintain reporting consistency.

<!-- Generated by Codex Meeting 3.2A -->
