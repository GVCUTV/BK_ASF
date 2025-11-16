# v2
# file: simulation/simulate.py

"""
Main entry point for the BookKeeper workflow event-driven simulation.
Initializes logging, wires together the DES components, and runs until
no more events remain or the horizon is exceeded.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

from .config import LOG_FILE, SIM_DURATION
from .entities import SystemState
from .events import EventQueue
from .stats import StatsCollector


def _configure_logging():
    log_dir = os.path.dirname(LOG_FILE) or "."
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("Simulation logging initialized at %s", datetime.now().isoformat())


def main():
    _configure_logging()

    state = SystemState()
    state.sim_duration = SIM_DURATION
    stats = StatsCollector(state)

    event_queue = EventQueue()
    event_queue.schedule_initial_arrivals(state)

    logging.info("Starting simulation loop. Target horizon: %.2f", SIM_DURATION)
    while not event_queue.empty():
        next_time = event_queue.next_event_time()
        if next_time > SIM_DURATION:
            logging.info("Next event occurs at %.2f beyond horizon; exiting loop.", next_time)
            break
        event = event_queue.pop()
        logging.info("Processing event: %s", event)
        try:
            event.process(event_queue, state, stats)
        except Exception as exc:  # noqa: BLE001 - explicit logging required
            logging.exception("Error while processing %s: %s", event, exc)
            break

    stats.final_report()
    logging.info("Simulation complete.")


if __name__ == "__main__":
    main()
