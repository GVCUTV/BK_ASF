// v3.2C-001
// file: docs/key_metrics_3.2C.md
# PMCSN ASF — Key Metrics Reference (Stage 3.2C)

## 1 ▪ Introduction
This catalog consolidates the operational performance indicators required across the PMCSN ASF analytical workflow. Every metric below is derived from the notation and balance relations already defined in [`docs/analytical_equations_3.2A.md`](analytical_equations_3.2A.md), so no new parameters or datasets are introduced. The goal is to provide a single lookup table that pairs each symbol with its analytical definition, required dependencies (\(\lambda, \mu, P, \pi, c_s\), etc.), and a plain-language interpretation that can be cited by the analytical model, simulation prototypes, or reporting artifacts.

## 2 ▪ Metrics Table
| Metric | Symbol | Mathematical definition | Units | Dependencies | Interpretation |
| --- | --- | --- | --- | --- | --- |
| Throughput of queue \(s\) | \(X_s\) | \(X_s = \lambda_s (1 - P_{\text{exit}\to s})\) when fed by upstream departures; in steady state of a single queue \(X_s = \lambda_s = \mu_s \cdot c_s \cdot \rho_s\). | jobs/time | Arrival rates \(\lambda_s\); routing matrix \(P\); service rate \(\mu_s\); effective server count \(c_s\). | Completed tickets per unit time for queue \(s\); equals the arrival rate when the node is stable. |
| Utilization | \(\rho_s\) | \(\rho_s = \frac{\lambda_s}{c_s \mu_s}\) for \(M/M/c\)-style capacity or \(\rho_s = \frac{X_s}{c_s \mu_s}\). | dimensionless | \(\lambda_s\), \(\mu_s\), expected available developers \(c_s\). | Fraction of service capacity that is busy; \(\rho_s < 1\) is required for stability. |
| Mean queue length | \(\mathbb{E}[Q_s]\) | \(\mathbb{E}[Q_s] = \lambda_s W_s\) (Little's Law). When the split between waiting and service is needed, \(\mathbb{E}[Q_s^{wait}] = \lambda_s W^{wait}_s\). | jobs | \(\lambda_s\), total response time \(W_s\) or waiting time \(W^{wait}_s\). | Average number of tickets present in queue \(s\); includes both waiting and being serviced unless noted. |
| Waiting time | \(W^{wait}_s\) | \(W^{wait}_s = W_s - \frac{1}{\mu_s}\). For \(M/M/1\) approximations, \(W^{wait}_s = \frac{\rho_s}{\mu_s (1-\rho_s)}\). | time | \(W_s\), \(\mu_s\), \(\rho_s\). | Expected time a ticket spends waiting before a developer starts service. |
| Response time | \(W_s\) | \(W_s = W^{wait}_s + \frac{1}{\mu_s}\). System-level response time aggregates across DEV/REV/TEST: \(W_{sys} = \sum_{s\in\{DEV,REV,TEST\}} W_s\). | time | Waiting time \(W^{wait}_s\); service rate \(\mu_s\). | Total sojourn time per queue (waiting + processing); governs SLA-style lead time. |
| Developer availability | \(A_s\) | \(A_s = \pi_s\) for \(s \in \{DEV, REV, TEST\}\); aggregate availability \(A = \sum_{s\in\{DEV,REV,TEST\}} \pi_s = 1 - \pi_{OFF}\). | probability (or fraction of developer time) | Semi-Markov steady-state probabilities \(\pi\) from `matrix_P.csv`. | Fraction of developer time spent in a productive state; directly scales the number of active servers per queue. |
| Effective capacity (net hours) | \(C^{net}_s\) | \(C^{net}_s = c^{gross} \cdot A_s \cdot H_{net}\), where \(c^{gross}\) is the rostered headcount for queue \(s\) and \(H_{net}\) is the length of the planning window (hours). When \(c^{gross}\) maps one-to-one to developers, \(C^{net}_s = c_s H_{net}\). | developer-hours | Developer availability \(A_s\); headcount allocation \(c^{gross}\); planning horizon \(H_{net}\). | Net productive hours a queue can deliver after OFF-state deductions; used to validate \(c_s\) and throughput assumptions. |
| Flow efficiency | \(FE\) | \(FE = \frac{\sum_{s\in\{DEV,REV,TEST\}} \frac{1}{\mu_s}}{W_{sys}}\). | dimensionless | Service rates \(\mu_s\); system response time \(W_{sys}\). | Share of total lead time spent actively processing work versus waiting; values near 1 indicate minimal idle time in queues. |

## 3 ▪ Notes on Usage in the Analytical Model
1. **Balance checks:** \(X_s\), \(\rho_s\), and \(\mathbb{E}[Q_s]\) provide the primary stability diagnostics. If \(\rho_s \geq 1\) the parameterization in [`docs/analytical_model.md`](analytical_model.md) must be revisited before simulation is attempted.
2. **Developer coupling:** Availability \(A_s\) and effective capacity \(C^{net}_s\) are the levers that translate the semi-Markov state occupancy (\(\pi_s\)) into usable queue servers (\(c_s\)). Any change to the state transition matrix \(P\) or stint lengths propagates directly into these quantities.
3. **Reporting alignment:** Flow efficiency and response-time metrics should be quoted alongside empirical Jira/GitHub measurements so stakeholders can trace analytical assumptions back to observable performance.

## 4 ▪ Future Extensions
- Incorporate percentile-based variants of response time and waiting time once empirical distribution fits are finalized.
- Add separate metrics for backlog health (e.g., aging buckets) when the arrival process calibration in stage 3.3 is complete.
- Extend capacity accounting to differentiate core committers versus ad-hoc contributors if a roster dataset becomes available.
