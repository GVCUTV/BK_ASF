# // v1.3A-Intro-Objectives
### PMCSN ASF — Introduction & Objectives  
*(Compliant with `GPT_INSTRUCTIONS.md` and the semi-Markov developer policy)*  

---

## 1 ▪ Purpose and Scope

This section introduces the **academic foundation and research motivation** of the BK ASF project.  
Its goal is to frame how autonomous developer behavior, represented through **semi-Markov processes**, affects workflow performance in modern software-foundation lifecycles.

ASF serves as the **reference case study** for the course *Performance Modeling of Computer Systems and Networks (PMCSN)*, aiming to merge:

- empirical data analysis (JIRA + Git),  
- stochastic modeling (queueing and semi-Markov processes), and  
- discrete-event simulation for validation and optimization.

---

## 2 ▪ Background and Motivation

Traditional software-project models treat developer assignment as centralized and deterministic.  
However, empirical evidence from open-source projects shows that team members exercise autonomy in choosing tasks and staying on specific roles for variable durations.  

ASF addresses this gap by modeling developers as **agents that self-select their next activity** using transition probabilities \( P_{ij} \) and empirical stint distributions \( f_i(ℓ) \).  
This creates a stochastic yet data-driven representation of team dynamics and resource allocation.

---

## 3 ▪ High-Level Objectives

### 3.1 Scientific Objectives
1. **Formalize developer autonomy** as a semi-Markov decision process within a queueing network framework.  
2. **Derive analytical equations** for transition matrices, stint PMFs, and service-time laws.  
3. **Quantitatively validate** the model against historical data to assess accuracy and predictive power.  

### 3.2 Technical Objectives
1. **Design an ETL pipeline** to extract developer sequences and effort weights from JIRA and Git.  
2. **Develop a simulation core** supporting semi-Markov agents and dynamic server capacities.  
3. **Implement a validation suite** for comparing empirical and simulated metrics (throughput, utilization, WIP).  

### 3.3 Pedagogical Objectives
1. Provide a replicable teaching artifact linking data analytics and stochastic modeling.  
2. Demonstrate integration of AI agents (ChatGPT for reasoning, Codex for code generation) within a controlled engineering workflow.  
3. Encourage students to experiment with policy variants and optimization strategies (e.g., adaptive transition matrices or bounded stints).

---

## 4 ▪ Conceptual Framework Overview

| Layer | Description | Key Deliverables |
|-------|--------------|------------------|
| **ETL / Data Acquisition** | Extracts ticket lifecycles and developer assignments from real repositories. | `data/etl_outputs/*.csv` |
| **Analytical Derivation** | Computes transition matrix \( P \), stint PMFs \( f_i(ℓ) \), and service-time laws \( T_s \). | `simulation/state_equations.py`, `data/state_parameters/` |
| **Simulation Engine** | Implements semi-Markov developer agents operating across queues DEV, REV, TEST. | `simulation/des_core.py` |
| **Validation Layer** | Performs comparative analysis vs. real metrics. | `docs/validation.md`, plots in `results/` |
| **Reporting & Presentation** | Consolidates findings for academic and project deliverables. | `docs/project_documentation.md`, `slides/` |

---

## 5 ▪ Figure Briefs (no graphics included)

1. **Figure 1 — ASF Project Pyramid**  
  *Depicts hierarchical layers from raw data (ETL) to reporting and academic presentation.*  

2. **Figure 2 — Developer State Evolution**  
  *Shows developer transitions OFF ↔ DEV ↔ REV ↔ TEST using probabilities \( P_{ij} \) and stint durations \( ℓ \).*  

3. **Figure 3 — ASF Processing Pipeline**  
  *Highlights interaction between Analytics → Simulation → Validation and feedback links.*  

4. **Figure 4 — Performance Metrics Loop**  
  *Illustrates how simulation outputs feed empirical comparison and model refinement.*

---

## 6 ▪ Integration Instructions

- Save this document as `docs/INTRO_OBJECTIVES_v1.3A.md`.  
- Reference it from `docs/project_documentation.md` under “Introduction & Objectives.”  
- Ensure consistency with `Intro_Overview_Refresh_v1.2.md` and `CONCEPTUAL_WORKFLOW_MODEL_v1.2.md`.  
- Reuse figure briefs when creating presentation slides for Meeting 1.3.  

---

## 7 ▪ Definition of Done (DoD)

1. Version header `// v1.3A-Intro-Objectives` present.  
2. Clearly states scientific, technical, and pedagogical objectives.  
3. Explicit integration of semi-Markov free-choice policy.  
4. Figure briefs complete and consistent with ASF architecture.  
5. Cross-references to subsequent sections validated.  
6. Markdown lint clean and links functional.  

---

**End of Document — Introduction & Objectives (v1.3A)**  
_Compliant with PMCSN ASF project standards and `GPT_INSTRUCTIONS.md`._
