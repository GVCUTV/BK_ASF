// v1.4
// CONCEPTUAL_WORKFLOW_MODEL.md
# PMCSN ASF — Conceptual Workflow Model
*(Aligned with the semi-Markov free-choice developer policy and `GPT_INSTRUCTIONS.md` conventions)*

---

## 1 ▪ Purpose

This document defines the **conceptual workflow model** of the ASF team as a stochastic, queue-driven process.
It provides the high-level structure that connects:
- developer behavior (governed by a semi-Markov model),
- the ASF task queues (**BACKLOG, DEV, REV, TEST, DONE**), and
- the feedback mechanisms linking stages in the software-development lifecycle.

This conceptual layer serves as the **foundation for the analytical (3.x)** and **simulation (4.x)** stages of the PMCSN ASF project.

---

## 2 ▪ Conceptual Structure Overview

### 2.1 System Entities
| Entity | Description |
|---------|--------------|
| **Developer agent** | Individual representing a team member; follows a semi-Markov policy deciding which activity to perform next. |
| **Developer state** | One of four modes: **OFF, DEV, REV, TEST**, modeling availability and focus. |
| **Queue stage** | Ticket positions **BACKLOG → DEV → REV → TEST → DONE**; the middle stages correspond to the active workflow queues. |
| **Task (ticket)** | Unit of work entering the ASF workflow; characterized by its state, effort, and service requirements. |
| **Coordinator (policy layer)** | Implicit mechanism ensuring that each developer selects their next state according to the transition matrix \( P \). |
| **System clock** | Advances on event completion; synchronizes all arrivals, transitions, and service completions. |

---

### 2.2 Developer Behavior Model
Each developer is modeled as a **semi-Markov agent** with state set
$$
S = \{ \text{OFF}, \text{DEV}, \text{REV}, \text{TEST} \}.
$$

- On **entry** to state _i_, the agent draws a *stint length* ℓ from the empirical distribution \( f_i(ℓ) \).
- The developer completes ℓ tickets sequentially in that state (pulling from the queue that matches the state).
- Upon stint exhaustion, the agent transitions to state _j_ according to \( P_{ij} \).
- If the selected queue has no pending work, fallback logic (wait/switch) is applied by the simulation layer.

This policy allows agents to **self-select** work focus periods, reflecting realistic autonomy in collaborative teams.

#### 2.2.1 Developer state semantics, stints, and overlap logic
- **OFF** — volunteer not logged in or between sessions; OFF absorbs calendar gaps so that the effective daily contribution caps at the agreed **≈7.5 net hours of distinct effort** highlighted in [`docs/schedule.md`](schedule.md).
- **DEV** — implementation focus performing code additions or modifications; ticket service times follow \(T_{DEV}\) and each stint contributes at most the net-availability budget once, regardless of how many developers pair-program.
- **REV** — code-review focus handling peer validation and comment resolution.
- **TEST** — integration and regression validation before DONE.

Stint distributions \(f_i(ℓ)\) match the empirical exports described in [`docs/DERIVATIONS_3.2A.md`](DERIVATIONS_3.2A.md) and persisted alongside \(P\) in `data/state_parameters/matrix_P.csv`. The overlap-weighting logic referenced in [`docs/schedule.md`](schedule.md) and reiterated in [`docs/Schedule_Prompts.md`](Schedule_Prompts.md) ensures concurrent contributions to a single ticket are churn-weighted so that total net availability never exceeds the ≈7.5-hour planning envelope. This same assumption feeds the analytical capacity checks in [`docs/analytical_model.md`](analytical_model.md) and the metric definitions in [`docs/key_metrics_3.2C.md`](key_metrics_3.2C.md), keeping the developer policy consistent across documents.

---

### 2.3 Queueing Interpretation

| Stage | Queue Type | Servers | Service-Time Law | Notes |
|--------|-------------|----------|------------------|-------|
| **BACKLOG** | Infinite buffer | Coordinated arrivals | $\lambda_{BL}$ arrivals/time unit | Tickets approved by the community wait for volunteers. |
| **DEV** | Single FIFO queue per developer state | # developers in DEV | $ T_{DEV} \sim \text{LogNormal}(\mu_{DEV}, \sigma_{DEV}) $ | Code creation and modification. |
| **REV** | Shared FIFO review queue | # developers in REV | $ T_{REV} \sim \text{LogNormal}(\mu_{REV}, \sigma_{REV}) $ | Peer code validation and comments. |
| **TEST** | FIFO testing queue | # developers in TEST | $ T_{TEST} \sim \text{LogNormal}(\mu_{TEST}, \sigma_{TEST}) $ | Integration and regression testing. |
| **DONE** | Absorbing sink | — | — | Tickets leave the system once confidence is achieved. |
| **OFF** | Idle state (no service) | — | — | Developer unavailable or between stints. |

The queues are connected in a **serial-feedback topology**:
BACKLOG → DEV → REV → TEST → (DONE or rework feedback → DEV).

Each stage’s throughput and utilization depend dynamically on the number of active developers in each state and on the backlog pressure.

---

## 3 ▪ Control Flow and Event Logic

1. **Task Arrival**
   - Tasks originate from the backlog at a configured rate or trace replay.
2. **Assignment and Service Start**
   - Developers in active states pull tasks from their corresponding queues.
3. **Task Completion**
   - Upon completion, queue statistics are updated; the developer decrements their stint counter.
4. **State Transition (Decision Event)**
   - When stint counter = 0, the developer samples the next state from $P$.
5. **Feedback Routing**
   - Tasks may return to previous queues (e.g., DEV after failed TEST) or exit through DONE.
6. **Metrics Update**
   - WIP, throughput, and utilization recorded at each event.

### 3.1 Documentation Cross-References
- [`docs/DERIVATIONS_3.2A.md`](DERIVATIONS_3.2A.md) — proves the empirical extraction of \(P\), stint pmfs, and service distributions referenced above.
- [`docs/analytical_equations_3.2A.md`](analytical_equations_3.2A.md) — centralizes the algebraic balance relations that consume this conceptual layout.
- [`docs/analytical_model.md`](analytical_model.md) — applies the conceptual queues and developer policy to the broader analytical pipeline before simulation.
- [`docs/key_metrics_3.2C.md`](key_metrics_3.2C.md) — lists the throughput, utilization, and availability indicators whose symbols map back to this workflow model.

This logic underlies both the **analytical formulation (Section 3.2)** and the **simulation implementation (Section 4)**.

---

## 4 ▪ Conceptual Model Diagrams — Figure Briefs (No Graphics)

> **Reference diagrams:** `docs/diagrams/Diagramma modello concettuale.drawio` (source), `docs/diagrams/Diagramma modello concettuale.png` (render).

1. **Figure 1 — Developer State Machine**
   *Depicts the semi-Markov chain with states OFF, DEV, REV, TEST and transition probabilities $P_{ij}$.*

2. **Figure 2 — ASF Queue Network**
   *Shows the BACKLOG → DEV → REV → TEST → DONE flow with dynamic capacities and feedback paths.*

3. **Figure 3 — Control Flow Timeline**
   *Represents the alternation between developer stint phases, state transitions, and system-wide event updates.*

4. **Figure 4 — End-to-End ASF Lifecycle**
   *Integrates backlog arrivals, queue processing, feedback, and state evolution for multiple agents.*

---

## 5 ▪ Consistency with ASF Analytical Framework

| Component | Dependency | Description |
|------------|-------------|-------------|
| **Transition Matrix $P$** | Derived in 3.2 A | Governs inter-state developer transitions. |
| **Stint PMFs $f_i(\mathcal{l})$** | Derived in 3.2 A | Define duration of focus in each state. |
| **Service Laws $T_s$** | Derived in 3.2 A | Define per-stage ticket completion times. |
| **Backlog arrival process** | Uses ETL data | Captures inflow that feeds the BACKLOG stage. |
| **Parameter Estimation (3.2 B)** | Uses ETL data | Fits empirical distributions to observed metrics. |
| **Simulation Architecture (4.x)** | Uses this model | Implements events, queues, and developer transitions. |

---

## 6 ▪ Integration Instructions

- Save this document as `docs/CONCEPTUAL_WORKFLOW_MODEL.md`.
- Ensure `docs/project_documentation.md` and downstream analytical/simulation files reference this model explicitly.
- When generating diagrams, reuse captions, state names (OFF/DEV/REV/TEST), and queue labels (BACKLOG/DEV/REV/TEST/DONE).
- Reference `docs/diagrams/Diagramma modello concettuale.drawio` (and exported PNG/PDF) whenever citing the conceptual diagram.

---

## 7 ▪ Definition of Done (DoD)

1. Document versioned (`// v1.4`).
2. Describes all four developer states and the BACKLOG → DEV → REV → TEST → DONE queue structure.
3. Explicitly includes semi-Markov policy and stochastic stint concept.
4. Figure briefs ready for later diagram generation.
5. Cross-references analytical and simulation components correctly.
6. Markdown formatting validated and lint-clean.

---

**End of Document — Conceptual Workflow Model (v1.4)**
_Compliant with PMCSN ASF project conventions and `GPT_INSTRUCTIONS.md`._
