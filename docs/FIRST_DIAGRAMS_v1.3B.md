// v1.3C
// FIRST_DIAGRAMS_v1.3B.md
# PMCSN ASF — First Diagrams / Conceptual Visual Package
*(Compliant with `GPT_INSTRUCTIONS.md` and the semi-Markov developer policy)*  

---

## 1 ▪ Purpose  

This document defines the **first-generation conceptual diagrams** that visualize the PMCSN ASF workflow under the **semi-Markov free-choice paradigm**.  
These diagrams will be used in both documentation and presentations to convey the new stochastic-behavior logic adopted in the updated model (v1.3 series).  

They replace all previous deterministic or static diagrams, ensuring visual consistency with the following documents:
- `Intro_Overview_Refresh_v1.4.md`
- `ASF_BK_Overview_v1.3.md`
- `CONCEPTUAL_WORKFLOW_MODEL.md` (v1.3)
- `JIRA_WORKFLOW_MAPPING_2.2A.md`

---

## 2 ▪ Diagram Set Overview  

| ID | Title | Purpose | Associated Section | Intended Tool |  
|----|--------|----------|-------------------|----------------|  
| D1 | ASF System Layer Stack | Depict the five-layer pipeline (ETL → Analytics → Simulation → Validation → Reporting). | Intro Overview | Draw.io / Mermaid |  
| D2 | Developer Semi-Markov State Machine | Show states OFF/DEV/REV/TEST and transitions via matrix P with stint counter ℓ. | Conceptual Model 2.2 | Draw.io / Mermaid |  
| D3 | Queue Network View | Represent the queueing interpretation of ASF with dynamic servers per developer state. | Conceptual Model 2.3 | Draw.io / TikZ |  
| D4 | Simulation Control Flow | Outline events: arrival → service → completion → state transition → feedback. | Simulation 4.x | Mermaid Sequence / Flowchart |  
| D5 | Validation Loop | Show empirical data feeding model calibration and comparison against simulated outputs. | Validation 5–6 | Draw.io / Mermaid |  

---

## 3 ▪ Diagram Briefs and Captions  

### D1 — ASF System Layer Stack  
**Caption:** *Overview of the five logical layers forming the PMCSN ASF pipeline.*  
**Description:**  
- Displays a vertical stack labeled **ETL**, **Analytics**, **Simulation**, **Validation**, **Reporting**.  
- Each layer annotated with its input/output data artifacts (e.g., `etl_outputs/*.csv`, `state_parameters/`, simulation logs).  
- Arrows show deterministic data flow; feedback loops connect Validation → Analytics for calibration.  

---

### D2 — Developer Semi-Markov State Machine  
**Caption:** *Per-developer semi-Markov chain representing state transitions and stint counters.*  
**Description:**  
- Four nodes: **OFF**, **DEV**, **REV**, **TEST**.  
- Directed edges labeled \( P_{ij} \) = transition probability from _i_ to _j_.  
- Each state bubble contains a small sublabel ℓ ~ fᵢ(ℓ) representing stint-length distribution.  
- Highlight self-loops for persistent stints (e.g., DEV → DEV).  

---

### D3 — Queue Network View
**Caption:** *Three service queues (DEV, REV, TEST) with dynamic servers equal to developers in each state.*
**Description:**
- DEV, REV, TEST drawn as process boxes; OFF represented as an external idle pool, while the BACKLOG queue feeds DEV following the mapping in `docs/JIRA_WORKFLOW_MAPPING_2.2A.md`.
- Developers (agents) move among these queues per \( P \).
- Feedback path TEST → DEV included to indicate rework.
- Annotate each queue with service-time law \( T_s ∼ \text{LogNormal}(μ_s, σ_s) \) and show DONE as the absorbing sink.

---

### D4 — Simulation Control Flow
**Caption:** *Event-driven sequence of ASF simulation activities.*
**Description:**
- Horizontal timeline or flowchart:
  `Backlog arrival → DEV queue service → REV queue service → TEST queue service → DONE/feedback → State transition (via P) → Stint counter check → Metrics update`.
- Indicates parallel developer agents and synchronization points tied to OFF/DEV/REV/TEST states.

---

### D5 — Validation Loop  
**Caption:** *Feedback cycle linking empirical data to simulation calibration.*  
**Description:**  
- Shows empirical metrics (transition counts, stint PMFs, service times) feeding parameter estimation.
- Simulation outputs return to comparison modules (Little’s Law, χ², KS tests).
- Arrows back to Analytics represent automatic parameter tuning and re-estimation while preserving the OFF/DEV/REV/TEST mapping.

---

## 4 ▪ Integration Guidelines  

- Save this file as `docs/FIRST_DIAGRAMS_v1.3B.md`.  
- Use provided captions and descriptions to generate the actual diagrams in Draw.io or Mermaid.
- Cross-link each diagram to its source section in:
  - `Intro_Overview_Refresh_v1.4.md`
  - `CONCEPTUAL_WORKFLOW_MODEL.md`
  - `DERIVATIONS_3.2A.md`
  - `JIRA_WORKFLOW_MAPPING_2.2A.md`
- When rendered in slides, include one caption line and source reference at the bottom right corner.  

---

## 5 ▪ Definition of Done (DoD)  

1. Version header `// v1.3C` present and referenced in `docs/schedule.md`.
2. Five diagram briefs fully described (text-only, no graphics).  
3. Terminology aligned with semi-Markov policy and queueing interpretation.  
4. File cross-referenced from intro and conceptual documents.  
5. Markdown lint clean and consistent style.  

---

**End of Document — First Diagrams (v1.3C)**
_Compliant with PMCSN ASF project standards and `GPT_INSTRUCTIONS.md`._
