# // v1.1-ASF-BK-Overview
### PMCSN ASF — Documentation / Analysis Deliverable  
*(Prepared for Meeting 1 – Kickoff & Familiarization)*  

---

## 1 ▪ Purpose and Scope
This document introduces the **ASF (BK Academic Software Foundation)** framework within the PMCSN project, presenting its rationale, operating structure, and modeling paradigm.  
It supersedes previous overviews to incorporate the **semi-Markov free-choice policy** that now governs developer behavior in all subsequent analytical and simulation stages.

---

## 2 ▪ ASF in the BK Project Context
ASF serves as the methodological backbone of the **BookKeeper (BK)** case study used in the *Performance Modeling of Computer Systems and Networks* course.  
It formalizes:
- a reproducible software-foundation lifecycle (ideation → development → review → testing → release),  
- agent roles (developers, reviewers, testers) governed by explicit state machines,  
- the data and simulation pipelines connecting ETL → analytics → DES → experiments → reporting.

ASF integrates **AI-assisted lifecycle management** where ChatGPT and Codex act as meta-agents:  
- **ChatGPT** → documentation, coordination, reasoning, prompt generation;  
- **Codex** → deterministic code synthesis following these prompts.

---

## 3 ▪ New Modeling Paradigm (Free-Choice Semi-Markov Policy)

### 3.1 Rationale
Previous iterations assumed deterministic or workload-balanced assignments of tasks.  
To reflect realistic team autonomy, each ASF team member now follows a **semi-Markov decision process**:

| Element | Description |
|----------|--------------|
| **State set S** | { OFF, DEV, REV, TEST } — developer’s current working mode |
| **Transition matrix P** | Empirically derived probabilities \( P_{ij} \) of moving from state _i_ to state _j_ after a ticket completion |
| **Stint distribution fᵢ(ℓ)** | Empirical PMF of consecutive tickets ℓ handled before leaving state _i_ |
| **Service-time law Tₛ** | Log-normal distribution fitted per queue stage s ∈ {DEV, REV, TEST} |

Together, \( P \) and \( fᵢ(ℓ) \) define a *free-choice semi-Markov policy*:
> Each developer autonomously selects their next activity according to P,  
> remaining in the chosen state for ℓ tickets drawn from fᵢ(ℓ).

### 3.2 Implications
- Queue capacities dynamically equal the number of developers currently in each productive state.  
- Workflow evolution becomes stochastic yet data-driven, improving fidelity to observed JIRA behavior.  
- All downstream analytics, validation, and reporting must reference this policy explicitly.

---

## 4 ▪ ASF Component Interactions (Conceptual Summary)

| Layer | Main Artifacts | Function |
|-------|----------------|-----------|
| **ETL / Data Prep** | JIRA and Git extractors | Produce developer-state sequences and effort metrics |
| **Analytics (3.2 A–C)** | `state_equations`, `parameter_estimation` | Derive P, fᵢ(ℓ), Tₛ |
| **Simulation Core (4.x)** | Discrete-event engine | Replay ASF workflow using semi-Markov agents |
| **Validation & Experiments (5–6)** | Statistical tests & plots | Verify throughput, WIP, utilization |
| **Reporting (7–8)** | Docs + Slides | Interpret results and propose improvements |

---

## 5 ▪ Terminology Update for Consistency

| Term | Old Meaning | Revised Meaning |
|------|--------------|----------------|
| *Developer state* | Fixed role (Dev/Rev/Test) | Dynamic state in Markov chain |
| *Transition rule* | Manual rotation or round-robin | Probabilistic transition via P |
| *Task stint* | Unspecified block of work | Empirical # of tickets per state drawn from fᵢ(ℓ) |
| *Routing parameters* | Fixed queue delays | Fitted service-time laws Tₛ |
| *Simulator agent* | Generic worker | Semi-Markov developer agent with free choice |

---

## 6 ▪ Expected Deliverables for 1.1
- `docs/ASF_BK_overview.md` (updated or created) — this content.  
- Cross-reference entries in `project_documentation.md` and `README.md`.  
- Inclusion of new glossary section *“Semi-Markov Free-Choice Policy”*.  
- No diagrams generated here (to be produced separately).

---

## 7 ▪ Definition of Done (DoD)
1. Version header and compliance banner present (`// v1.1-ASF-BK-Overview`).  
2. Terminology consistent with the semi-Markov paradigm.  
3. All previous deterministic descriptions removed or rewritten.  
4. Document cross-linked in repo table of contents.  
5. Validation: peer review ensures conceptual alignment with sections 3.2 A–D.  

---

**End of Document — ASF BK Overview (v1.1)**
