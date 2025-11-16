// v3.2A-002
// file: docs/analytical_equations_3.2A.md
# Meeting 3.2A — Unified Analytical Equations

## 1 ▪ Introduction
This document centralizes every equation and parameter required by the semi-Markov developer submodel and the associated queueing network. All numerical inputs are sourced from the ETL artifacts already produced for stage 3.2A (`data/state_parameters/matrix_P.csv` and `data/state_parameters/service_params.json`) and the descriptive notes in [`docs/DERIVATIONS_3.2A.md`](DERIVATIONS_3.2A.md). No new data are generated here; the goal is to expose the existing matrices, routing rules, and derived quantities in a single, human-readable reference.

### 1.1 Developer states, stint distributions, and overlap logic
The developer-state semantics mirror the conceptual workflow in [`docs/CONCEPTUAL_WORKFLOW_MODEL.md`](CONCEPTUAL_WORKFLOW_MODEL.md):

- **OFF** — slack time between focus periods so that each volunteer’s **≈7.5 net productive hours** per planning window (documented in [`docs/schedule.md`](schedule.md)) are not double-counted.
- **DEV / REV / TEST** — active queues whose service laws \(T_s\) are documented in `data/state_parameters/service_params.json` and whose stint pmfs \(f_i(\ell)\) originate from the ETL exports summarized in [`docs/DERIVATIONS_3.2A.md`](DERIVATIONS_3.2A.md).

Overlap logic follows the churn-weighted accounting described in [`docs/Schedule_Prompts.md`](Schedule_Prompts.md), meaning simultaneous work on a single ticket contributes only one unit of net availability. This constraint ensures the \(c_s\) terms derived from \(\pi\) and \(f_i(\ell)\) tie directly to the capacity assumptions later enforced in [`docs/analytical_model.md`](analytical_model.md) and the availability metrics in [`docs/key_metrics_3.2C.md`](key_metrics_3.2C.md).

## 2 ▪ Symbols & Notation
- \(\mathcal{S} = \{\text{OFF}, \text{DEV}, \text{REV}, \text{TEST}\}\): developer states.
- \(P_{ij}\): probability of transitioning from developer state \(i\) to state \(j\).
- \(f_i(\ell)\): stint-length pmf for state \(i\) with support \(\ell > 0\).
- \(L_i\): random stint duration in state \(i\); \(\mathbb{E}[L_i] = \sum_{\ell} \ell f_i(\ell)\).
- \(\pi_i\): steady-state probability that a developer is in state \(i\).
- \(\theta_{s\to k}\): routing probability that work leaving queue \(s\) enters queue \(k\).
- \(\lambda_s\): effective arrival rate into queue \(s\).
- \(T_s\): service time for queue \(s \in \{\text{DEV}, \text{REV}, \text{TEST}\}\).
- \((\mu^{LN}_s, \sigma^{LN}_s)\): log-normal parameters of \(T_s\) estimated from ETL outputs.
- \(\mu_s\): service rate for queue \(s\), defined as \(\mu_s = 1 / \mathbb{E}[T_s]\).
- \(c_s\): expected number of available servers (developers) for queue \(s\).
- \(X_s\): throughput of queue \(s\) (jobs per unit time).
- \(W_s\): total mean time jobs spend in queue \(s\) (waiting + service).
- \(\mathbb{E}[Q_s]\): expected number of jobs in queue \(s\).

## 3 ▪ Data Sources
- **Transition matrix:** `data/state_parameters/matrix_P.csv` lists the smoothed empirical \(P_{ij}\) values derived from Jira/GitHub event sequences.
- **Service parameters:** `data/state_parameters/service_params.json` records the fitted log-normal parameters for \(T_{DEV}, T_{REV}, T_{TEST}\).
- **Stint pmfs:** `simulation/state_equations.py` outputs the per-state `stint_PMF_<STATE>.csv` files referenced by \(f_i(\ell)\).

## 4 ▪ Semi-Markov Transition Matrix \(P\)
Empirical transition counts \(n_{ij}\) are converted into probabilities with Laplace smoothing (\(\alpha = 1\)) to enforce non-zero mass:
\[
P_{ij} = \frac{n_{ij} + \alpha}{\sum_k n_{ik} + \alpha\cdot|\mathcal{S}|}
\]
The resulting transition matrix persisted in `matrix_P.csv` is:

| from \ to | OFF | DEV | REV | TEST |
|-----------|-----|-----|-----|------|
| **OFF**  | 0.0078 | 0.5504 | 0.1783 | 0.2636 |
| **DEV**  | 0.0051 | 0.3112 | 0.6480 | 0.0357 |
| **REV**  | 0.1735 | 0.2908 | 0.2194 | 0.3163 |
| **TEST** | 0.8230 | 0.0619 | 0.0265 | 0.0885 |

Rows follow the state order OFF → DEV → REV → TEST. This matrix feeds both the simulator and the analytical steady-state equations below.

## 5 ▪ Stint-Length Distributions and Expected Sojourns
For each state \(i\), contiguous observations of a developer staying in \(i\) yield counts \(c_i(\ell)\) across discretized stint lengths. The pmf exported by the ETL pipeline is therefore
\[
 f_i(\ell) = \frac{c_i(\ell)}{\sum_{\ell'} c_i(\ell')}, \quad \ell \in \text{support}(i).
\]
The expected stint length is \(\mathbb{E}[L_i] = \sum_{\ell} \ell f_i(\ell)\). These expectations determine the mean active time spent in each state per visit and combine with \(P\) to produce the semi-Markov kernel required for steady-state analysis.

## 6 ▪ Service-Time Parameters
Log-normal fits summarize the ticket-level service durations for each active queue:

| Stage | Distribution | Samples | \(\mu^{LN}_s\) | \(\sigma^{LN}_s\) |
|-------|--------------|---------|----------------|-------------------|
| DEV | Log-normal | 192 | -0.5838 | 4.7425 |
| REV | Log-normal | 192 | 1.7868 | 2.3344 |
| TEST | Log-normal | 109 | -5.9267 | 4.5370 |

The mean service time implied by these parameters is
\[
\mathbb{E}[T_s] = \exp\left(\mu^{LN}_s + \frac{(\sigma^{LN}_s)^2}{2}\right), \quad s \in \{\text{DEV}, \text{REV}, \text{TEST}\},
\]
and the service rate used in queueing equations is \(\mu_s = 1 / \mathbb{E}[T_s]\). Reciprocal rates may be multiplied by \(c_s\) to obtain aggregate service capacity.

## 7 ▪ Routing Definitions
Tickets traverse the queues \(\{\text{DEV}, \text{REV}, \text{TEST}, \text{DONE}\}\) with deterministic forward motion and probabilistic feedback:
- Forward routing is mandatory: \(\theta_{\text{DEV→REV}} = 1\) and \(\theta_{\text{REV→TEST}} + \theta_{\text{REV→DEV}} = 1\).
- Rework probabilities reflect Jira “reopen” events captured in the ETL data: \(\theta_{\text{REV→DEV}} = P_{\text{REV→DEV}}\) and \(\theta_{\text{TEST→DEV}} = P_{\text{TEST→DEV}}\).
- Completion probabilities satisfy \(\theta_{\text{REV→TEST}} = 1 - \theta_{\text{REV→DEV}}\) and \(\theta_{\text{TEST→DONE}} = 1 - \theta_{\text{TEST→DEV}}\).
- DONE is absorbing: \(\theta_{\text{DONE→·}} = 0\).

Internal arrival rates follow immediately:
\[
\lambda_{\text{REV}} = \theta_{\text{DEV→REV}}\, \lambda_{\text{DEV}}, \quad
\lambda_{\text{TEST}} = \theta_{\text{REV→TEST}}\, \lambda_{\text{REV}},
\]
\[
\lambda_{\text{DEV}} = \lambda_{\text{ext}} + \theta_{\text{REV→DEV}}\, \lambda_{\text{REV}} + \theta_{\text{TEST→DEV}}\, \lambda_{\text{TEST}},
\]
where \(\lambda_{\text{ext}}\) is the exogenous backlog arrival rate.

## 8 ▪ Core Equations
### 8.1 Steady-State Developer Availability
Developers obey a semi-Markov process; their steady-state probabilities solve
\[
\boldsymbol{\pi} = \boldsymbol{\pi} P, \qquad \sum_{i \in \mathcal{S}} \pi_i = 1.
\]
Given \(N_{dev}\) concurrent volunteers, the expected number of servers in state \(s \in \{\text{DEV}, \text{REV}, \text{TEST}\}\) is \(c_s = N_{dev} \cdot \pi_s\).

### 8.2 Service Capacity and Throughput
Per-queue throughput is linked to developer availability by
\[
X_s = c_s \cdot \mu_s = \frac{c_s}{\mathbb{E}[T_s]},
\]
with \(\mu_s\) derived from the log-normal means above. Global throughput respects conservation: \(X_{\text{DEV}} = X_{\text{REV}} = X_{\text{TEST}} = X_{\text{DONE}}\) once the system reaches equilibrium.

### 8.3 Queue Flow Conservation
Internal flows must satisfy
\[
\lambda_{\text{DEV}} = \lambda_{\text{ext}} + \theta_{\text{REV→DEV}} X_{\text{REV}} + \theta_{\text{TEST→DEV}} X_{\text{TEST}},
\]
\[
\lambda_{\text{REV}} = X_{\text{DEV}}, \qquad \lambda_{\text{TEST}} = \theta_{\text{REV→TEST}} X_{\text{REV}}.
\]
These relations ensure that arrivals balance departures for every active stage.

### 8.4 Queue Lengths and Waiting Times
Little’s Law holds at both the node and network level:
\[
\mathbb{E}[Q_s] = \lambda_s W_s, \qquad \mathbb{E}[N_{system}] = \lambda_{tot} W_{system},
\]
where \(\lambda_{tot} = \lambda_{\text{DEV}}\) in steady state. Once \(W_s\) is derived (either analytically or via simulation), the expected queue length follows immediately.

### 8.5 Semi-Markov Cycle Metrics
Expected time spent in each developer state per cycle is
\[
\tau_i = \pi_i \cdot \mathbb{E}[L_i],
\]
and the overall mean cycle length is \(\sum_{i \in \mathcal{S}} \tau_i\). These quantities govern how frequently developers return to OFF, DEV, REV, and TEST roles and therefore how often servers become available to the queues.

## 9 ▪ Assumptions
1. Only the four developer states (OFF, DEV, REV, TEST) are allowed; no auxiliary states or queues are introduced.
2. Transition probabilities are time-homogeneous and equal to the smoothed empirical \(P_{ij}\) entries.
3. Stint lengths within a state are independent and identically distributed according to the exported pmfs \(f_i(\ell)\).
4. Service times per queue follow log-normal distributions with parameters fixed by `service_params.json`.
5. Routing adheres to the deterministic forward order BACKLOG → DEV → REV → TEST → DONE with rework limited to REV→DEV and TEST→DEV transitions.
6. Arrival processes are modeled via effective rates \(\lambda_s\) without altering the ETL-derived counts.

## 10 ▪ References
- `data/state_parameters/matrix_P.csv` — canonical source for \(P_{ij}\).
- `data/state_parameters/service_params.json` — canonical source for \(\mu^{LN}_s, \sigma^{LN}_s\) and sample counts.
- `simulation/state_equations.py` — code that generates the stint pmfs and validates the inputs summarized here.
- [`docs/DERIVATIONS_3.2A.md`](DERIVATIONS_3.2A.md) — provenance details for the smoothing, fitting, and validation steps used to construct these parameters.
- [`docs/CONCEPTUAL_WORKFLOW_MODEL.md`](CONCEPTUAL_WORKFLOW_MODEL.md) — defines the workflow semantics, queue order, and developer-state intent that these equations formalize.
- [`docs/analytical_model.md`](analytical_model.md) — embeds the equations into the broader analytical pipeline before simulation.
- [`docs/key_metrics_3.2C.md`](key_metrics_3.2C.md) — lists the reporting indicators computed from \(\lambda, \mu, P, \pi\), and \(c_s\).
