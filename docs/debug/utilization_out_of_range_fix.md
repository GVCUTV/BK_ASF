# Utilization Out-of-Range Debug Note

## Root cause
- **Capacity time undercounted for busy agents.** The developer pool only accrued state-time for agents when they were idle. Busy agents contributed service time to `service_busy_time` at start, but their time in the corresponding state was only recorded upon service completion. Any services still in progress at the simulation horizon (or spanning long gaps between events) inflated the busy numerator without contributing to the capacity-time denominator, allowing utilization to exceed 1.
- The issue was most visible in sweeps with heavier arrival or feedback because long-running testing/review work near the horizon left a large portion of busy time unrecorded in state totals.

## Fix
- Track state exposure for **all agents (busy or idle)** on every time advance so state-time matches elapsed time in their current state.
- Finalize residual state time at the simulation horizon to include any in-progress stints.
- Compute utilization as `busy_time / capacity_time` with a safety check that raises if busy time ever exceeds capacity time beyond a numerical tolerance.

## Before vs. after (DEV / REVIEW / TESTING utilization)
- **Before (from issue report):**
  - `higher_arrival`: 1.9906 / 1.4054 / 1.2810
  - `feedback_heavy`: DEV/REVIEW < 1, TESTING = 1.2348
- **After (rerun sweeps `baseline`, `higher_arrival`, `feedback_heavy`):**
  - `baseline`: 0.2384 / 0.5827 / 0.0370
  - `higher_arrival`: 0.5593 / 0.6455 / 0.4253
  - `feedback_heavy`: 0.3943 / 0.6375 / 0.7671

## Notes and assumptions
- Each developer’s semi-Markov state (DEV/REV/TEST/OFF) represents capacity for that stage. Utilization is defined as **busy server time divided by available state time** for that stage over the observation horizon.
- No clamping is applied; utilizations remain within [0, 1] by construction, and a guard fails fast if busy time exceeds capacity time.
- Validation is covered by an automated sweep-based test that asserts utilizations stay within bounds for the three core experiments.
