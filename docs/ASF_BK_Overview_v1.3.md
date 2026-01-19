# // v1.3-ASF-BK-Overview
### PMCSN ASF — ASF / BK Context Overview  
*(Updated for alignment with Intro_Overview_Refresh_v1.4 and the semi‑Markov queueing framework)*

---

## 1 ▪ ASF’s Role in the BK Project

The **Academic Software Foundation (ASF)** defines the formal workflow modeling structure for the **BookKeeper (BK)** case study used in the PMCSN course.  
It ensures a reproducible, data‑driven representation of developer activities across the software lifecycle.  

ASF integrates the **semi‑Markov free‑choice developer policy**, enabling stochastic transitions among work states (OFF, DEV, REV, TEST) governed by:  
- **Transition matrix** \( P \), estimated from empirical event sequences.  
- **Stint distributions** \( f_i(\ell) \), capturing persistence in a given role.  
- **Service‑time laws** \( T_s \), describing ticket completion durations.  

---

## 2 ▪ Conceptual Foundation

| Concept | Implementation | Description |
|---|---|---|
| **Developer Behavior** | Semi‑Markov process (states, transitions, stints). | Represents real decision autonomy in task selection. |
| **Workflow Structure** | 3‑stage queueing network. | DEV/REV/TEST service centers; OFF = idle. |
| **Routing Logic** | Empirical probabilities \( P_{ij} \). | Captures state‑to‑state transition likelihoods. |
| **Calibration Data** | JIRA + Git. | Provides timestamps, effort weights, and code churn metrics. |
| **Feedback Loop** | TEST → DEV rework path. | Maintains model stability and realism. |

---

## 3 ▪ Analytical Alignment

| Section | Output | File |
|---|---|---|
| **3.2 A** | Derivation of \( P, f_i, T_s \) | `simulation/state_equations.py`, `docs/DERIVATIONS_3.2A.md` |
| **3.2 B** | Parameter estimation validation | `data/state_parameters/` |
| **4.x** | Simulation architecture | `simulation/des_core.py` |
| **5–6** | Validation and experiments | `docs/validation.md`, `results/` |

---

## 4 ▪ Integration and Maintenance

- Keep this file as `docs/ASF_BK_Overview_v1.3.md`.  
- Link from `Intro_Overview_Refresh_v1.4.md`.  
- Reference it in `project_documentation.md` and `schedule.md`.  
- Synchronize terminology with other v1.3+ documentation.  

---

## 5 ▪ Definition of Done (DoD)

1. Version banner updated to v1.3.  
2. Explicitly references semi‑Markov developer policy and queueing interpretation.  
3. Cross‑links and paths consistent with updated intro file.  
4. Markdown validation passed.  

---

**End of Document — ASF / BK Overview (v1.3)**  
_Compliant with PMCSN ASF project conventions and `GPT_INSTRUCTIONS.md`._
