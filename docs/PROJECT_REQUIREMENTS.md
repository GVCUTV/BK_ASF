# PROJECT_REQUIREMENTS.md — BK_ASF PMCSN Project

## General Project Structure

- **Project:** Academic (PMCSN, "Performance Modeling and Simulation of Computer Systems and Networks").
- **Topic:** Modeling and simulation of the real workflow of Apache BookKeeper, focusing on the ASF community-driven, volunteer-based process. Data sources are BookKeeper's Jira and GitHub. Not a classic company/PM pipeline.
- **Repo for code:** https://github.com/GVCUTV/BK_ASF.git

## Study Goals

- Map, model, and simulate the complete lifecycle of feature and bug tickets, from Jira creation to actual production release, **explicitly including all feedback loops (test/review/fix cycles)**.
- Use queueing theory and event-driven simulation for analysis. **Critically, service times are empirically heavy-tailed (lognormal, hyperexponential, Weibull, etc.)**, so product-form Jackson network solutions are not valid; all results must be validated by simulation and real data.
- Analyze both steady-state and transient behaviors; identify bottlenecks, measure iteration cycles, and propose improvements that fit the ASF volunteer/open source context.

## ASF & BookKeeper Workflow (With Feedback Loop Highlighted)

- **No formal manager, no forced task assignment:** Contributors self-select tasks based on interest and availability.
- **Jira "Priority" is advisory only** ([Mockus et al. 2002], ASF docs): ticket order is not enforced.
- **Workflow includes:**
  1. Ticket creation (feature, bug, improvement)
  2. Voluntary assignment (may remain unassigned)
  3. Development & PR (GitHub), referencing Jira
  4. **Code review (peer, PR review):**
      - **At this stage, bugs or requests for changes can trigger a feedback loop. The ticket may be reopened or updated, requiring new code changes, followed by re-review and re-testing.**
  5. **Testing (CI, QA, user, post-merge):**
      - **Here, further failures or bugs can again trigger a feedback loop: the issue may be reopened or a new sub-task created. The cycle returns to development/review/testing as needed.**
  6. Final merge/release/closure
- **Crucial:**  
  - **These feedback loops (review/test/fix cycles) can repeat multiple times. Only after all such cycles are completed, and the fix or feature is released to production, is the issue truly considered “closed.”**
  - **Backlog and “in progress” states can persist for long periods due to the iterative and volunteer-driven nature of the process.**

## Modeling & Queueing System Approach

- **System modeled as a network of general queues with feedback:**
    - **Stage 1:** Development + Review (service times: empirically fitted, e.g., lognormal/Weibull)
    - **Stage 2:** Testing/QA (service times: empirically fitted)
    - **Routing:** After each review or test, with probability *p*, the ticket cycles back to development; with probability *1-p*, it proceeds. Loops can occur both after review and testing.
- **No Jackson network (M/M/1) assumptions:** All service time distributions must be fitted to real data (heavy-tailed). Performance analysis is via event-driven simulation (see Harchol-Balter Ch.17.7, Ch.18.5).
- **Key metrics:** mean/median resolution time, #iterations, backlog size over time, phase durations, utilization per stage, bottleneck identification.

## Data Handling & Experiment Plan

- **Extract and unify data from Jira and GitHub:**
    - Track every ticket’s state changes, PRs, reviews, reopens, sub-task bugs, feedback cycles, with timestamps.
    - Build a dataset mapping: ticket → all transitions → all associated PRs → review cycles → test/fail/fix cycles → closure.
    - Clean data: exclude non-relevant (infra, duplicate, won’t fix), unify formats, ensure mapping ticket ↔ PR is correct.
    - Compute base stats: #tickets by type, %reopens, mean/median times in each state, iteration counts.
- **Parametrize simulation:** Use fitted empirical distributions for service times, measure feedback probability p, and estimate arrival rates.
- **Simulation:** Run for both finite and infinite horizons; validate all metrics (resolution time, queue length, etc.) against measured data.
- **Experimental scenarios:** Analyze both steady-state and transients, parameter sweeps (e.g., more reviewers, less feedback), measure improvement impact.

## Meeting Schedule (Reference)

- **Meeting 1:** Kickoff, docs review, initial conceptual modeling (all)
- **Meeting 2:** Finalize conceptual/queue model, workflow mapping, first diagrams (A: model, B: diagrams, C: data)
- **Meeting 3:** Analytical queueing model (empirical fits, routing matrix, metric definition; split tasks)
- **Meeting 4:** Simulation architecture/coding (event logic, stats output), peer review
- **Meeting 5:** Full simulation, debug, parameter sweeps, validation (Little’s Law, empirical checks)
- **Meeting 6:** Design and execute experiments, transient/steady-state, bottleneck analysis, draft results
- **Meeting 7:** Simulate improvements (test automation, review, etc.), compare results, finalize recommendations
- **Meeting 8:** Final report assembly, collaborative editing, slides prep by topic (A: intro/model, B: experiments, C: improvements), full rehearsal

## Code Generation Guidelines

- Always output full files (copy-pasteable, replace actual files), unless told otherwise.
- Always add the file version as **first comment** (vN+1 of previous version), and the filename as **second comment**.
- Code must be thoroughly, naturally commented as by a human (no AI references).
- If a design/usage decision is made, explain in natural language after the code.
- **All code must log every operation** (to logfile and stdout) at runtime.
- Always use: https://github.com/GVCUTV/BK_ASF.git as repo reference.

## Other Project Notes

- Every modeling, coding, and reporting choice must be justified with theory, empirical fits, or cited literature (“Performance Modeling and Design of Computer Systems”, M. Harchol-Balter, chapter/page).
- The “resolutive strategy” is: fully map/model the feedback-based workflow, and track every ticket (feature or bug) from creation to final release, capturing every possible iterative path (with all cycles).
- All code, diagrams, and reports must remain consistent with real observed BookKeeper data and workflow.

---

**END OF PROJECT REQUIREMENTS — Use this as the canonical reference for analysis, coding, and reporting in this project.**
