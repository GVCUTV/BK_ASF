# // v1.4-Intro-Overview-Refresh
### PMCSN ASF — Intro / Overview Update  
*(Compliant with `GPT_INSTRUCTIONS.md`; aligned with final semi‑Markov developer policy & queueing interpretation)*

---

## 1 ▪ Overview

The **PMCSN ASF** project formalizes the lifecycle of a software‑foundation team as a **semi‑Markov queueing system** calibrated on empirical data (JIRA + Git).  
Each developer acts as a **semi‑Markov agent**, alternating among the states **OFF**, **DEV**, **REV**, and **TEST**, according to probabilistic rules drawn from real-world workflow traces.

- **Transitions** between states follow a Markov transition matrix \( P \).  
- **Focus periods** (stints) in each state follow empirical PMFs \( f_i(\ell) \).  
- **Service times** for each queue stage follow log‑normal distributions \( T_s \).  

This free‑choice paradigm replaces deterministic role rotation, allowing realistic stochastic variation in throughput, utilization, and WIP across the development pipeline.

---

## 2 ▪ Objectives (v1.4)

1. **Model Developer Autonomy** — Represent free‑choice behavior using empirically fitted \( P \) and \( f_i(\ell) \).  
2. **Integrate Queueing Theory** — Express DEV/REV/TEST as service centers whose capacity equals the number of developers in that state.  
3. **Ensure Analytical–Simulation Continuity** — Use 3.2A outputs (\( P, f_i, T_s \)) as inputs to the DES layer (4.x).  
4. **Enable End‑to‑End Validation** — Compare simulated throughput and state frequencies against empirical data.  
5. **Maintain Reproducibility** — Guarantee deterministic ETL → Analytics → Simulation → Validation → Reporting pipeline.  

---

## 3 ▪ ASF Workflow Architecture

| Layer | Purpose | Key Artifacts |
|---|---|---|
| **ETL / Data Prep** | Extract developer sequences, timestamps, churn metrics. | `data/etl_outputs/*.csv` |
| **Analytics (3.x)** | Derive \( P \), \( f_i(\ell) \), and fit \( T_s \). | `data/state_parameters/`, `simulation/state_equations.py` |
| **Simulation Core (4.x)** | Execute discrete‑event simulation with semi‑Markov agents. | `simulation/des_core.py`, logs, CSVs |
| **Validation (5–6)** | Compare simulated and empirical metrics. | `docs/validation.md`, `results/` |
| **Reporting (7–8)** | Compile experiments, improvements, slides. | `docs/project_documentation.md`, `slides/` |

---

## 4 ▪ Glossary (v1.4)

| Term | Definition |
|---|---|
| **Developer state** | One of four operational modes: OFF, DEV, REV, TEST. |
| **Transition matrix \( P \)** | Probabilities \( P_{ij} \) of moving from state _i_ to _j_. |
| **Stint PMF \( f_i(\ell) \)** | Probability distribution of consecutive tickets handled in state _i_. |
| **Service‑time law \( T_s \)** | Log‑normal distribution of task durations for queue stage s ∈ {DEV, REV, TEST}. |
| **Semi‑Markov policy** | Developer transitions probabilistically between states after completing a stint ℓ tasks long. |
| **Queueing interpretation** | ASF represented as a three‑queue open network with dynamic server pools (developers per state). |
| **Feedback loop** | TEST → DEV routing for rework, maintaining closed‑loop stability. |

---

## 5 ▪ Figure Briefs (For Future Diagrams)

1. **ASF Queueing Network (Dynamic Servers)** — Shows DEV/REV/TEST queues, feedback loop, and dynamic developer pools.  
2. **Developer Semi‑Markov Process** — Illustrates states OFF, DEV, REV, TEST with transition matrix P and stint counters ℓ.  
3. **Pipeline Architecture** — Depicts data flow ETL → Analytics → Simulation → Validation → Reporting.  
4. **Validation Feedback Loop** — Demonstrates data–model alignment cycle for calibration.  

---

## 6 ▪ Integration Instructions

- Replace the previous introduction text in `docs/project_documentation.md` with this version (v1.4).  
- Maintain cross‑links to:  
  - `docs/ASF_BK_Overview_v1.3.md`  
  - `docs/CONCEPTUAL_WORKFLOW_MODEL_v1.2.md`  
  - `docs/FIRST_DIAGRAMS_v1.3B.md`  
- Keep version header for traceability in derived copies.  

---

## 7 ▪ Definition of Done (DoD)

1. Version header `// v1.4‑Intro‑Overview‑Refresh` present.  
2. Glossary and objectives consistent with the final semi‑Markov & queueing model.  
3. Figure captions aligned with `FIRST_DIAGRAMS_v1.3B.md`.  
4. Cross‑references validated; Markdown passes linting.  
5. Document synchronized with repo artifacts.  

---

**End of Document — Intro / Overview Refresh (v1.4)**  
_Compliant with PMCSN ASF standards and `GPT_INSTRUCTIONS.md`._
