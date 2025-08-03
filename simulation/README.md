# v1
# file: simulation/README.md

# BookKeeper Workflow Simulation – Architecture & Usage

## What does this code do?
This directory implements an event-driven simulation of the Apache BookKeeper development workflow,
including all feedback cycles as observed in the real ASF/Jira process.

- **Entities:** Tickets, queues, servers (dev/review, testing)
- **Events:** Ticket arrivals, service completions, feedback loops, ticket closure
- **Service times:** Drawn from empirically fitted heavy-tailed distributions
- **Routing:** Feedback probability after each phase (parameterized)
- **Stats:** Per-ticket and aggregate output, fully logged

## File Structure

- `simulate.py` – Main runner (schedules, runs simulation loop, coordinates everything)
- `events.py` – Event and EventQueue classes (arrival, service, feedback)
- `entities.py` – Ticket entity and overall SystemState (queues, servers, feedback logic)
- `service_distributions.py` – Utilities for sampling fitted service times
- `config.py` – All simulation parameters (arrival rate, feedback p, distribution params, etc.)
- `stats.py` – Collects stats, outputs CSVs and summary stats
- `logs/` – Simulation logs (stdout + file)
- `output/` – Simulation outputs (per-ticket CSV, more to be added)

## How to run

1. Install dependencies (see below).
2. Edit `config.py` to adjust parameters as needed.
3. Run the simulation:

    ```bash
    python simulate.py
    ```

4. Outputs:
   - Log: `logs/simulation.log`
   - Stats: `output/ticket_stats.csv`

## Requirements

- Python 3.x
- numpy

## Notes

- Service time distribution parameters are **examples**; update with your fitted values!
- Feedback probabilities (`FEEDBACK_P_DEV`, `FEEDBACK_P_TEST`) must be empirically set.
- Simulation is fully modular for further extensions (parallel servers, multiple queues, etc).

---

*See code comments for more on logic and usage.*
