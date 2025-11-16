// v3.1-001
// file: docs/analytical_model.md
# PMCSN ASF — Analytical Model (Stage 3.1)

## 1 ▪ Introduction
This note defines the analytical representation that bridges the conceptual workflow in [`docs/CONCEPTUAL_WORKFLOW_MODEL.md`](CONCEPTUAL_WORKFLOW_MODEL.md) and the formal derivations slated for [`docs/DERIVATIONS_3.2A.md`](DERIVATIONS_3.2A.md). It states the queueing network, developer-state submodel, and high-level balance equations that must stay consistent with the Jira alignment in [`docs/JIRA_WORKFLOW_MAPPING_2.2A.md`](JIRA_WORKFLOW_MAPPING_2.2A.md) and the dataset expectations listed in [`docs/DATA_LIST_1.3C.md`](DATA_LIST_1.3C.md). No derivations are provided here; Section 3.2A remains the canonical source for algebraic proofs and parameter estimation.

## 2 ▪ Queueing Network Description
- **Topology:** Serial-feedback network `BACKLOG → DEV → REV → TEST → DONE` with a feedback arc from REV and TEST to DEV for rework, mirroring the Jira transitions (`Reopened`, `Patch Available → In Progress`) documented in the workflow mapping.
- **Nodes:**
  - **BACKLOG:** Infinite-capacity buffer; fed solely by the exogenous arrival process with rate \(\lambda_{BL}\).
  - **DEV queue:** Work-in-progress requiring implementation; serviced by developers currently in the **DEV** state.
  - **REV queue:** Code-review staging area pulled by **REV**-state developers.
  - **TEST queue:** Integration/testing queue drained by **TEST**-state developers.
  - **DONE sink:** Absorbing node; no service time.
- **Servers:** Each active developer constitutes a single server for the queue associated with their current state. OFF-state developers provide no service.
- **Routing:** Tickets normally follow BACKLOG → DEV → REV → TEST → DONE. REV or TEST completion may route back to DEV with probability \(P_{\text{REV→DEV}}\) or \(P_{\text{TEST→DEV}}\) to represent rework noted as "Reopened" in Jira.

## 3 ▪ Developer Process Overview
- **States:** \(\mathcal{S} = \{\text{OFF}, \text{DEV}, \text{REV}, \text{TEST}\}\) exactly as in the conceptual model.
- **Policy:** Developers follow a semi-Markov process. Upon entering state \(i\), the developer samples a stint length \(L_i\) from the empirical pmf \(f_i(\ell)\) (fitted per `DERIVATIONS_3.2A`).
- **Service coupling:** During a stint, the developer repeatedly pulls tickets from the queue matching their state until the stint counter hits zero or the queue empties.
- **Transitions:** When the stint completes, the next state \(j\) is drawn according to transition matrix \(P_{ij}\). OFF serves as the recovery/idle state that enables future arrivals to be absorbed without overloading the active queues.

## 4 ▪ Assumptions
### 4.1 Arrival Processes
1. **Exogenous inflow:** Tickets arrive to BACKLOG via a stationary process with average rate \(\lambda_{ext}\). ETL inputs (see `DATA_LIST_1.3C`) provide timestamped Jira creation events for calibrating \(\lambda_{ext}\).
2. **Poisson approximation:** For tractability, arrivals are treated as Poisson unless ETL calibration enforces another renewal structure.
3. **Independence from service:** Arrivals are independent of current queue lengths and developer states.

### 4.2 Service Processes
1. **State-conditioned service times:** Each active queue \(s \in \{\text{DEV}, \text{REV}, \text{TEST}\}\) has service rate \(\mu_s\) derived from the log-normal fits summarized in `DERIVATIONS_3.2A`.
2. **Developer homogeneity inside a state:** All developers in the same state share the same \(\mu_s\) in the analytical layer (simulation may introduce heterogeneity later).
3. **Single-ticket focus:** A developer services one ticket at a time; multitasking is ignored.

### 4.3 Routing
1. **Deterministic forward routing:** After service in DEV, tickets proceed to REV with probability 1 unless flagged for abandonment (not modeled here).
2. **Feedback:** REV and TEST may send tickets back to DEV with routing probabilities \(P_{\text{REV→DEV}}\) and \(P_{\text{TEST→DEV}}\) that capture "Reopened" Jira events.
3. **Completion:** Tickets exiting TEST with probability \(1 - P_{\text{TEST→DEV}}\) move to DONE and leave the system permanently.

### 4.4 Independence
1. **Queue independence:** Conditional on developer counts, service completions are independent across queues.
2. **State-transition independence:** The semi-Markov transitions depend only on the current state and stint completion, not on queue length (work shortages are handled via blocking rules in the simulation layer).

### 4.5 Stationarity
1. **Time-invariant parameters:** \(P\), \(f_i\), \(\lambda\), and \(\mu_s\) remain constant over the horizon analyzed in 3.1/3.2.
2. **Ergodicity:** The developer Markov renewal process is assumed irreducible and positive recurrent, ensuring a steady-state distribution \(\pi\).

## 5 ▪ Notation
| Symbol | Meaning | Source | Notes |
| --- | --- | --- | --- |
| \(\lambda_{ext}\) | Average external arrival rate into BACKLOG | Jira creation timestamps | May be segmented by release window. |
| \(\mu_{DEV}, \mu_{REV}, \mu_{TEST}\) | Service rates per active queue | Service fits in `DERIVATIONS_3.2A` | Reciprocal of mean service time. |
| \(P_{ij}\) | Semi-Markov transition matrix between developer states | `DERIVATIONS_3.2A` | Rows follow state order OFF, DEV, REV, TEST. |
| \(f_i(\ell)\) | Stint-length pmf for state \(i\) | `DERIVATIONS_3.2A` exports | Supports \(\ell \in \mathbb{R}^+\). |
| \(\pi\) | Steady-state distribution over developer states | Computed via \(\pi P = \pi\) | Provides expected active servers per queue. |
| \(Q_s\) | Queue length at stage \(s\) | Analytical state vector | Aligns with `BACKLOG, DEV, REV, TEST`. |
| \(\rho_s\) | Utilization of queue \(s\) | \(\rho_s = \lambda_s / (\mu_s \, c_s)\) | \(c_s\) = number of developers in state \(s\). |

## 6 ▪ Model Equations (High-Level)
1. **Developer balance:** \(\pi = \pi P\), subject to \(\sum_i \pi_i = 1\). This yields the expected fraction of developers in each state and therefore the effective server counts \(c_s = N_{dev} \cdot \pi_s\) for \(s \in \{\text{DEV}, \text{REV}, \text{TEST}\}\).
2. **Queue conservation:** Let \(\lambda_{DEV}\) be the effective arrival rate to DEV. Then \(\lambda_{DEV} = \lambda_{ext} + \lambda_{REV \to DEV} + \lambda_{TEST \to DEV}\), where the internal flows satisfy \(\lambda_{REV \to DEV} = P_{\text{REV→DEV}} \cdot \mu_{REV} \cdot c_{REV}\) and similarly for TEST.
3. **Service relations:** For each stage \(s\), the throughput obeys \(\lambda_s = \min(\lambda_{in,s}, \mu_s \, c_s)\). Bottlenecks appear when \(\lambda_{in,s} > \mu_s \, c_s\), inflating \(Q_s\).
4. **Little’s Law placeholders:** Mean queue lengths follow \(\mathbb{E}[Q_s] = \lambda_s \cdot W_s\) once waiting times \(W_s\) are derived in Section 3.2A (not included here).
5. **Routing probabilities:** Internal routing obeys \(\sum_{k \in \{\text{DEV},\text{REV},\text{TEST},\text{DONE}\}} P_{s \to k} = 1\) for \(s \in \{\text{DEV},\text{REV},\text{TEST}\}\), ensuring probability mass conservation.

## 7 ▪ Consistency Notes
- State labels and queue names mirror `JIRA_WORKFLOW_MAPPING_2.2A.md`, so future ETL refreshes can plug in without schema changes.
- All parameters referenced here correspond to the artifacts listed in `DATA_LIST_1.3C.md`, guaranteeing reproducibility.
- Derivations of \(P\), \(f_i\), \(\mu_s\), and steady-state solutions will be supplied in `DERIVATIONS_3.2A.md`; this document only states the structure and assumptions required to set up those derivations.

---
**End of Document — Analytical Model 3.1**
