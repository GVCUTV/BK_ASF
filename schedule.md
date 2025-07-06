[comment]: # "v0"
## **Project Schedule**

---

### **Meeting 1 [8/7/2025] – Kickoff & System Familiarization**

* **1.1** (All): Rapid reading & discussion of the chosen paper and Alibaba trace data docs.
* **1.2** (All): Outline the system’s structure, workflow, and conceptual model together.
* **1.3** (Split):

  * Person A: Start drafting introduction & goals for the report.
  * Person B: Sketch first draft of the system/conceptual diagrams (whiteboard/Miro/Figma).
  * Person C: List data needs, begin exploring Alibaba dataset.
* **End:** 15-min wrap-up, share findings, adjust plan.

---

### **Meeting 2 [13/7/2025] – Conceptual Model & Data Exploration**

* **2.1** (All): Finalize conceptual and event model (define classes of jobs, states, events, resources).
* **2.2** (Split):

  * A: Start writing conceptual model/event list section.
  * B: Develop the first event diagrams/flow charts for the report.
  * C: Continue data preprocessing, share parameter statistics for model inputs.
* **All:** Review each other’s partial results, feedback, synchronize.

---

### **Meeting 3 [15/7/2025] – Analytical Model Construction**

* **3.1** (All): Build and discuss the analytical queueing model together.
* **3.2** (Split):

  * A: Write up analytical traffic equations and state/routing matrix for report.
  * B: Start parameter estimation from trace data.
  * C: Draft explanation of metrics (utilization, queue time, response time, etc.).
* **All:** Review, cross-check each other’s draft contributions.

---

### **Meeting 4 [29/7/2025] – Simulation Architecture & Coding Start**

* **4.1** (All): Design high-level architecture and agree on simulation flow (pseudo-code/whiteboard).
* **4.2** (Split):

  * A: Set up simulation repo/project structure.
  * B: Start coding event management and arrival processes.
  * C: Implement initial service and departure logic.
* **All:** Mini peer code review at end, update documentation.

---

### **Meeting 5 [3/8/2025] – Verification, First Runs, Debugging**

* **5.1** (All): Integrate, test, and run first full-system simulation.
* **5.2** (Split):

  * A: Document and check consistency (Little’s Law, utilization, mean times).
  * B: Run several parameter sweeps for initial results.
  * C: Debug and optimize simulation code, keep notes for the report’s “Model Validation” and “Verification” sections.
* **All:** Discuss anomalies, collectively refine model/logic.

---

### **Meeting 6 [19/8/2025] – Experimental Design & Result Analysis**

* **6.1** (All): Define experimental scenarios—what variables to vary, what outputs to collect.
* **6.2** (Split):

  * A: Run and document transient (startup) vs steady-state simulations.
  * B: Generate and polish graphs/tables.
  * C: Begin drafting “Design of Experiments” and “Bottleneck Analysis” sections.
* **All:** Cross-check data, select best plots/tables for report.

---

### **Meeting 7 [26/8/2025] – Optimization & Improved Model**

* **7.1** (All): Brainstorm and select improvement(s) (e.g., new scheduling, dynamic resource allocation).
* **7.2** (All):

  * Implement improvement in simulation.
  * Run comparative simulations and extract results.
  * Draft the improved model, highlight differences, update relevant report sections.
* **All:** Interpret comparative results together, discuss findings, prepare for final report.

---

### **Meeting 8 [TBD] – Report Completion & Presentation Prep**

* **8.1** (All): Assemble the report in sections, collaboratively edit, polish, and add references.
* **8.2** (Split):

  * A: Prepare slides for introduction/model sections.
  * B: Prepare slides for experiments/results.
  * C: Prepare slides for improvements/conclusions.
* **All:** Full mock presentation (each practices their part), group Q\&A, finalize code and deliverables.

