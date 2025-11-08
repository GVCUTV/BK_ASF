# // v1.3-Intro-Overview-Refresh
### PMCSN ASF — Intro / Overview Update  
*(Compliant with `GPT_INSTRUCTIONS.md`; aligned with semi-Markov developer policy & queueing interpretation)*

---

## 1 ▪ Updated Overview

The **PMCSN ASF** project models the software‑foundation lifecycle as a **semi‑Markov queueing system** grounded in real data (JIRA + Git).  
Developers are autonomous agents whose activities (OFF, DEV, REV, TEST) evolve stochastically:
- **Transitions** follow an empirical **Markov matrix** \( P \).
- **Focus duration** in a state follows an empirical **stint PMF** \( f_i(\ell) \).
- **Service times** per stage follow fitted **log‑normal** laws \( T_s \).

This free‑choice paradigm replaces earlier deterministic or fixed rotations, yielding more realistic dynamics of throughput, WIP, and utilization.

---

## 2 ▪ Objectives (Refreshed)

1. **Autonomy Modeling** — Capture self‑directed developer choices via \( P \) and \( f_i(\ell) \).  
2. **Queueing Representation** — Treat DEV/REV/TEST as service centers whose server pool equals the # developers in that state.  
3. **Analytics ↔ Simulation Alignment** — Ensure 3.2A artifacts (\( P, f_i, T_s \)) parameterize the 4.x DES.  
4. **Validation** — Compare state occupation, throughput, and latency to empirical traces; report deviations.  
5. **Reproducibility** — Deterministic ETL → Analytics → Simulation → Validation pipeline; versioned artifacts.

---

## 3 ▪ System Layers

| Layer | Function | Key Outputs / Files |
|---|---|---|
| **ETL / Data Prep** | Extract developer sequences & effort metrics | `data/etl_outputs/*.csv` |
| **Analytics (3.x)** | Derive \( P \), \( f_i(\ell) \), fit \( T_s \) | `data/state_parameters/*`, notes in `docs/` |
| **Simulation (4.x)** | DES with semi‑Markov agents & dynamic servers | `simulation/des_core.py` |
| **Validation (5–6)** | Compare empirical vs simulated metrics | `docs/validation.md`, `results/` |
| **Reporting (7–8)** | Synthesize findings, prepare slides | `docs/project_documentation.md`, `slides/` |

---

## 4 ▪ Glossary (v1.3)

| Term | Definition |
|---|---|
| **Semi‑Markov policy** | Developer transitions via \( P \); stint length \( \ell \sim f_i(\ell) \). |
| **Transition matrix \( P \)** | Prob. of moving i → j after stint exhaustion. |
| **Stint PMF \( f_i(\ell) \)** | Distribution of consecutive tickets handled in state i. |
| **Service‑time law \( T_s \)** | Log‑normal duration for stage s ∈ {DEV, REV, TEST}. |
| **Queueing interpretation** | DEV/REV/TEST as queues with dynamic server pools (developers in that state). |
| **Feedback loop** | TEST → DEV rework routing when validation fails. |
| **Free‑choice** | Next activity chosen probabilistically, not centrally assigned. |

---

## 5 ▪ Figure Briefs (No Graphics)

1. **ASF Queueing Network** — DEV, REV, TEST queues with feedback; dynamic servers = developers per state.  
2. **Developer Semi‑Markov Process** — States, stint counter decrements, and transitions \( P_{ij} \).  
3. **Data→Sim Pipeline** — ETL → Analytics (\( P, f_i, T_s \)) → DES → Validation → Reporting.  
4. **Validation View** — Overlay of empirical vs simulated state occupancy and throughput.

---

## 6 ▪ Integration

- Replace older intro in `docs/project_documentation.md` with this v1.3 reference.  
- Cross‑link to `docs/CONCEPTUAL_WORKFLOW_MODEL_v1.2.md` and `docs/DERIVATIONS_3.2A.md`.  
- Keep version header in derived copies.

---

## 7 ▪ DoD

- v1.3 header present & ASF compliance noted.  
- Objectives, glossary, and captions reflect semi‑Markov & queueing paradigm.  
- Cross‑refs verified; Markdown lint OK.

---

**End — Intro / Overview Refresh (v1.3)**
