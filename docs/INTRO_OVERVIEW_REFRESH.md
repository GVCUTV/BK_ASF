# // v1.2-Intro-Overview-Refresh
### PMCSN ASF — Intro / Overview Update  
*(Compliant with `GPT_INSTRUCTIONS.md` and incorporating final semi-Markov, routing, and validation structure)*  

---

## 1 ▪ Updated Overview

The **PMCSN ASF** project models the internal workflow of a software foundation team as a **semi-Markov queueing system**.  
It combines real-world data (JIRA + Git) with simulation and analytical modeling to reproduce how a development team autonomously manages coding, review, and testing activities.

Each team member operates as a **semi-Markov agent**:
- The current working mode (OFF, DEV, REV, TEST) evolves probabilistically through a transition matrix \( P \).  
- The duration of continuous work in each state follows an empirical stint-length PMF \( f_i(ℓ) \).  
- Each queue stage (DEV, REV, TEST) represents a service center with log-normal service-time distributions \( T_s \).  

This paradigm provides a realistic and data-grounded model of developer autonomy, feedback loops, and workflow variability, replacing the deterministic patterns used in earlier phases.

---

## 2 ▪ Refined Objectives

1. **Model Developer Free-Choice Behavior**  
   - Implement and calibrate the semi-Markov decision logic from empirical data.  
   - Quantify how individual autonomy impacts global throughput and utilization.  

2. **Represent ASF as a Dynamic Queue Network**  
   - Treat each productive state as a service center with variable capacity (number of developers).  

3. **Enable Analytical Derivation and Simulation Alignment**  
   - Ensure that equations from 3.2 A (transition matrix P, stint PMFs, service laws) directly feed the simulation layer (4.x).  

4. **Support Validation and Experimentation**  
   - Reproduce historical workloads and evaluate deviations in state frequencies, throughput, and latency.  

5. **Maintain Transparency and Reproducibility**  
   - All derivations, parameters, and simulations are versioned and reproducible through deterministic ETL → Analytics → Simulation → Validation → Reporting stages.  

---

## 3 ▪ ASF System Architecture

| Layer | Function | Key Outputs / Files |
|-------|-----------|---------------------|
| **ETL / Data Preparation** | Extract developer timelines, ticket histories, and churn metrics. | `data/etl_outputs/*.csv` |
| **Analytics (3.x)** | Estimate transition matrix P, stint PMFs, and service-time parameters. | `simulation/state_equations.py`, `data/state_parameters/` |
| **Simulation Core (4.x)** | Execute discrete-event simulation using semi-Markov developer agents. | `simulation/des_core.py`, output logs & CSVs |
| **Validation (5.x–6.x)** | Compare simulated vs. empirical throughput and state occupation. | `docs/validation.md`, plots under `results/` |
| **Reporting (7–8)** | Assemble analysis, experiments, and presentation. | `docs/project_documentation.md`, `slides/` |

---

## 4 ▪ Glossary (v1.2, Finalized)

| Term | Definition |
|------|-------------|
| **Developer state** | One of four operational modes: OFF, DEV, REV, TEST. |
| **Semi-Markov policy** | Behavioral model where developers probabilistically transition between states, staying ℓ tasks in each (ℓ ∼ fᵢ(ℓ)). |
| **Transition matrix P** | Empirical probabilities \( P_{ij} \) of moving from i to j after stint completion. |
| **Stint PMF fᵢ(ℓ)** | Probability mass function of consecutive tickets handled in state i. |
| **Service-time law Tₛ** | Log-normal distribution of task durations for queue stage s ∈ {DEV, REV, TEST}. |
| **Queueing interpretation** | ASF represented as a 3-queue open network with dynamic server pools driven by developer states. |
| **Feedback loop** | Routing of tasks from TEST → DEV when validation fails, closing the system dynamics. |
| **Free-choice** | Autonomy property: next activity chosen by developer via P, not centrally assigned. |

---

## 5 ▪ Figure Captions (for Future Diagrams)

*(No diagrams included; these captions serve for future creation.)*

1. **Figure 1 — ASF Queueing Network (Dynamic Server Model)**  
   *Depicts DEV, REV, TEST queues connected sequentially with feedback paths and variable developer pools per state.*

2. **Figure 2 — Developer Semi-Markov Process**  
   *Shows developer state transitions governed by P and stint counter decrements from fᵢ(ℓ).*

3. **Figure 3 — Data-to-Simulation Flow**  
   *Represents the pipeline ETL → Analytics → Simulation → Validation → Reporting.*

4. **Figure 4 — Validation and Feedback Loop**  
   *Illustrates comparison between real and simulated metrics and how results feed improvements.*

---

## 6 ▪ Integration Instructions

- Replace the old introduction section in `docs/project_documentation.md` with this version (v1.2).  
- Maintain cross-references to:  
  - `docs/ASF_BK_overview.md` → general context.  
  - `docs/CONCEPTUAL_WORKFLOW_MODEL.md` → formal state/queue structure.  
- Reuse figure captions when drawing diagrams in Draw.io or Mermaid.  
- Keep the version header `// v1.2-Intro-Overview-Refresh` in all derived copies for traceability.  

---

## 7 ▪ Definition of Done (DoD)

1. Document header version updated to v1.2 and ASF compliance noted.  
2. Overview, objectives, and glossary reflect finalized semi-Markov queueing paradigm.  
3. Figure captions harmonized with conceptual model v1.2.  
4. Cross-references and integration paths verified.  
5. Document passes Markdown linting and internal link checks.  

---

**End of Document — Intro / Overview Refresh (v1.2)**  
_Compliant with PMCSN ASF project conventions and `GPT_INSTRUCTIONS.md`._
