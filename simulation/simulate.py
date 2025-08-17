# v1
# file: simulate.py

"""
Main entry point for BookKeeper workflow event-driven simulation.
Handles simulation loop, initial event scheduling, and coordination of all modules.
Logs every operation to stdout and to logs/simulation.log.
"""

import logging
import os
import sys
from datetime import datetime
from events import EventQueue, TicketArrivalEvent
from entities import SystemState
from config import SIM_DURATION, LOG_FILE
from stats import StatsCollector

# Setup logging: to file and stdout
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.info("Simulation started at %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

def main():
    # Initialize system state and statistics collector
    state = SystemState()
    stats = StatsCollector(state)

    # Initialize event queue and schedule first ticket arrivals
    event_queue = EventQueue()
    event_queue.schedule_initial_arrivals(SIM_DURATION, state, stats)

    # Simulation main loop
    while not event_queue.empty() and event_queue.next_event_time() < SIM_DURATION:
        event = event_queue.pop()
        logging.info(f"Processing event: {event}")
        event.process(event_queue, state, stats)

    # Wrap up, output results
    stats.final_report()
    logging.info("Simulation complete.")

if __name__ == "__main__":
    main()
