# // v1.1-Intro-Overview-Refresh
### PMCSN ASF — Intro / Overview Update  
*(Compliant with `GPT_INSTRUCTIONS.md` and the semi-Markov developer policy)*  

---

## 1 ▪ Updated Overview

The **PMCSN ASF** project models the internal workflow of a small software-foundation team through **data-driven simulation**.  
Its purpose is to study how developer behavior, task routing, and feedback loops impact the performance and stability of collaborative development processes.

In the current version, the system operates under a **semi-Markov free-choice policy**.  
This means that each team member **chooses their next activity autonomously** after completing a task, following transition probabilities empirically derived from real-world data (e.g., JIRA histories).

This approach replaces the previous deterministic or round-robin assignment logic and allows for a more realistic representation of:
- self-directed work choices,  
- varying focus periods (“stints”),  
- and asynchronous progression across stages of the ASF lifecycle.

---

## 2 ▪ Objectives

The updated modeling objectives are:

1. **Capture realistic developer behavior**  
   - Use a *semi-Markov process* with transition matrix \( P \) and stint distribution \( f_i(ℓ) \) to represent how developers shift between work states.
2. **Model queueing interactions dynamically**  
   - Developer states (OFF, DEV, REV, TEST) determine instantaneous service capacity for the corresponding queue.
3. **Enable quantitative validation**  
   - Compare simulated throughput, utilization, and WIP with empirical data.
4. **Preserve reproducibility**  
   - All analytical and simulation artifacts are generated automatically through deterministic ETL → Analytics → Simulation → Validation phases.

---

## 3 ▪ High-Level System Interpretation

| Layer | Function | Associated Files |
|-------|-----------|------------------|
| **ETL / Data Extraction** | Collect developer sequences, ticket events, and code churn metrics. | `etl_extractors/`, `data/etl_outputs/` |
| **Analytics** | Derive Markov transition matrix P, stint PMFs, and service-time parameters. | `simulation/state_equations.py`, `data/state_parameters/` |
| **Simulation Core** | Discrete-event engine reproducing ASF team dynamics under semi-Markov policy. | `simulation/des_core.py` |
| **Validation / Results** | Compare observed vs. simulated behavior (transition frequencies, throughput, utilization). | `docs/validation.md` |
| **Reporting** | Prepare final report and presentation of findings. | `docs/project_documentation.md`, `slides/` |

---

## 4 ▪ Glossary (Updated)

| Term | Definition (v1.1) |
|------|-------------------|
| **Developer state** | One of four modes {OFF, DEV, REV, TEST}. |
| **Semi-Markov policy** | Developer transitions between states probabilistically after completing a stint of ℓ tasks. |
| **Transition matrix \( P_{ij} \)** | Probability of moving from state _i_ to state _j_. |
| **Stint distribution \( f_i(ℓ) \)** | Empirical PMF of consecutive tasks in state _i_. |
| **Service-time law \( T_s \)** | Log-normal duration distribution for each stage s ∈ {DEV, REV, TEST}. |
| **Queueing interpretation** | Each stage is modeled as a queue; servers correspond to developers currently in that state. |
| **Free-choice** | The policy allowing developers to select their next activity probabilistically, not deterministically. |

---

## 5 ▪ Figure Captions (For Future Diagrams)

These captions describe the diagrams to be produced later (no graphics included):

1. **Figure 1 — ASF Workflow Layers**  
   *Depicts the four primary queues (DEV, REV, TEST, OFF) with transitions governed by P and developer capacities as dynamic servers.*

2. **Figure 2 — Semi-Markov Developer Model**  
   *Illustrates the per-developer state machine with outgoing transition probabilities and stint-length counters.*

3. **Figure 3 — End-to-End ASF Pipeline**  
   *Shows the data path ETL → Analytics → Simulation → Validation → Reporting, highlighting feedback loops.*

---

## 6 ▪ Integration Instructions
- Replace or update the introductory section of `docs/project_documentation.md` with this text.  
- Link glossary entries to `docs/ASF_BK_overview.md`.  
- Ensure captions are reused when diagrams are drawn in Draw.io or Figma.  
- Keep version header `// v1.1-Intro-Overview-Refresh` for traceability.

---

## 7 ▪ Definition of Done (DoD)
- Overview explicitly mentions the **semi-Markov free-choice policy** and **queueing interpretation**.  
- All old deterministic or fixed-assignment references removed.  
- Updated glossary and figure captions included.  
- Cross-references to analytics and simulation layers verified.  
- Markdown lint passes with no syntax or formatting errors.  

---

**End of Document — Intro / Overview Refresh (v1.1)**  
_Compliant with PMCSN ASF project conventions._
