// v2.2A-001
// file: docs/JIRA_WORKFLOW_MAPPING_2.2A.md

# Meeting 2.2A — JIRA ↔ Queue/Developer-State Mapping

## Overview
This document aligns the Jira workflow used in Apache BookKeeper with the queue-centric conceptual model (`BACKLOG → DEV → REV → TEST → DONE`) and the semi-Markov developer states (`OFF / DEV / REV / TEST`). Statuses were extracted from `etl/output/csv/jira_issues_clean.csv` and `data/exploration/jira_issues.csv` to guarantee complete coverage of the available snapshots.

**Distinct Jira statuses (sorted):** `Closed`, `In Progress`, `Open`, `Patch Available`, `Reopened`, `Resolved`.

The mapping below treats each status as an observation of where a ticket sits inside the queueing network and which developer state is supplying service. Ambiguous statuses include explicit notes and assumptions so that ETL, analytics, and simulation code can consume the same deterministic mapping.

## Status to Queue/State Mapping
| Jira status | Queue stage | Developer state | Notes |
| --- | --- | --- | --- |
| Open | BACKLOG | OFF | Ticket accepted by the community but still waiting for a volunteer; no developer stint is active, so the ticket resides entirely in the backlog queue. |
| In Progress | DEV | DEV | Active implementation or bug fixing. The assignee is consuming work from the DEV queue while staying in the DEV state for the duration of the stint. |
| Patch Available | REV | REV | Code submitted for peer review. Reviewers in the REV state drain the REV queue; repeated review cycles keep the ticket here until approvals land. |
| Resolved | TEST | TEST | Fix verified by the author and now waiting on QA/release validation. Tickets with non-code resolutions (e.g., Won't Fix/Do) still pass through this stage but are assumed to incur negligible TEST service time. |
| Reopened | DEV | DEV | Jira automatically moves the issue back to a working state. The ticket re-enters the DEV queue, and a developer in DEV must pick it up again. This captures both failed tests and review-based rework. |
| Closed | DONE | OFF | The ticket exits the operational queues. Developers return to OFF because the effort no longer consumes project capacity. |

## Transition Alignment
1. **Open → In Progress:** backlog dispatch; developer leaves OFF and begins a DEV stint.
2. **In Progress → Patch Available:** implementation completes and the ticket migrates to the REV queue for peer review.
3. **Patch Available → Resolved:** successful review emits a TEST stint to cover integration and release validation.
4. **Resolved → Closed:** QA/release complete; ticket leaves the system. Tickets resolved with "Won't Fix/Do" short-circuit this phase but still register a `Resolved → Closed` transition to maintain chronological ordering.
5. **Reopened loops:** any failure during REV or TEST triggers `Reopened → In Progress`, represented as a return to the DEV queue with the developer re-entering DEV.

This deterministic ordering ensures that queue statistics and developer state measurements remain synchronized, even when Jira allows manual jumps (e.g., Open → Resolved). When such shortcuts occur in the data, we insert the implied queue stages during ETL analytics to preserve conservation of flow.

## Edge Cases and Assumptions
- **Reopened tickets:** Always treated as DEV queue items regardless of whether Jira labels them as Open or Reopened in subsequent transitions. This prevents under-counting DEV rework.
- **Won't Fix / Won't Do resolutions:** These values appear as `fields.resolution.name` while the status remains `Resolved`. We treat them as `TEST` queue entries with near-zero service time, immediately followed by `Closed`. This captures the decision without consuming DEV or REV capacity.
- **Direct Closed statuses:** If Jira records a ticket as `Closed` without a preceding `Resolved`, we infer that QA was implicit and still map it to DONE/OFF. ETL notes such events so simulation inputs can insert a synthetic `Resolved` timestamp if timing data is needed.
- **Patch Available after reopening:** Tickets can move from `Patch Available` back to `In Progress` without Jira explicitly saying "Reopened". ETL records those transitions as REV→DEV, mirroring the same developer-state change as an explicit reopen.

These assumptions will be revisited whenever new Jira exports introduce additional statuses; future updates must expand the table above and adjust ETL logic accordingly to keep the queues and developer states consistent.
