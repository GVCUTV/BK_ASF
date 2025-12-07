## Codex Prompt — Make Backlog the Dev Queue of Record

**Goal**
Ensure the backlog buffer is the authoritative dev queue for both processing and metrics: dev enqueue/dequeue, service starts, queue lengths, and wait times must operate directly on backlog data, eliminating any shadow dev queue and preventing zeroed dev metrics.

---

### Context
- Current workflow uses `backlog_buffer` to supply work to the dev stage, but dev metrics are derived via normalization/aliasing rather than direct backlog accounting, leading to `avg_queue_length_dev` and `avg_wait_dev` sticking at zero.
- Review and testing already have dedicated queues and metrics; only the dev queue is proxy-backed by backlog.
- Backlog should remain the source of truth for dev scheduling and statistics; no separate dev queue should exist in `stage_queues`.
- Service-time parameters for dev/review/testing are already split (no `dev_review`), and routing probabilities must stay unchanged.

---

### Files to Read
- `simulation/simulate.py` (event loop, backlog enqueue/dequeue wiring)
- `simulation/workflow_logic.py` (arrival handling, `try_start_service`, service completion, backlog pulls)
- `simulation/entities.py` (SystemState definitions: backlog, stage queues, helper methods)
- `simulation/stats.py` (queue length/wait tracking, aggregation, CSV writers)
- `simulation/run_sweeps.py` and any experiment specs that assume queue columns
- Reference outputs: `simulation/output/summary_stats.csv`, `simulation/output/tickets_stats.csv`
- Docs: `docs/simulation/e2e_run_notes.md`, `simulation/output/spiegazione_legge_di_little.md`

---

### Objectives
- Make `backlog_buffer` the single dev queue: enqueue/dequeue, selection, and capacity checks for dev must read/write backlog directly; remove or alias any shadow `dev` entry in `stage_queues`.
- Track dev queue length/wait directly from backlog events (no post-hoc normalization). Update stats collection so `avg_queue_length_dev` and `avg_wait_dev` integrate backlog activity and respond when backlog accumulates.
- Remove redundant backlog-specific metrics/columns (e.g., `avg_queue_length_backlog`) and ensure dev metrics replace them consistently across CSV outputs and aggregation logic.
- Keep review/testing queue handling unchanged; ensure routing and service-time sampling remain identical aside from queue plumbing.
- Update documentation/run notes to explain backlog-as-dev-queue behavior and any schema changes.
- If reference CSVs are versioned, regenerate them after code changes so expected outputs reflect the new dev metrics.

---

### Output Requirements
- Provide unified diffs (or full file replacements) for all modified code/docs/outputs.
- Ensure stats/CSV writers include only dev/review/testing queue metrics with dev metrics sourced from backlog events.
- If outputs are regenerated (`summary_stats.csv`, `tickets_stats.csv`), include updated files in the diff.
- Document any breaking or renamed columns in the relevant docs/run notes.

---

### Formatting Rules
- Follow `AGENTS.md` and project code style.
- Do not introduce new workflow states or alter service-time/routing semantics beyond the queue/plumbing changes.
- Keep seeding behavior unchanged.

---

### Human Intervention
If large external experiments or additional CSVs beyond the repo need regeneration, insert:
```markdown
### PROMPT FOR THE USER
Provide or regenerate external experiment CSVs to align with the backlog-as-dev-queue metrics.
```

---

### Definition of Done (DoD)
- Backlog is the exclusive dev queue for scheduling and metrics; no shadow dev queue remains.
- `avg_queue_length_dev` and `avg_wait_dev` are calculated from backlog enqueue/dequeue timing and become non-zero when backlog grows.
- Review/testing queue behavior and metrics are unchanged.
- CSV outputs/docs reflect the backlog-as-dev-queue design; smoke/sanity checks run without errors.
