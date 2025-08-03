# v1
# file: simulation/stats.py

"""
Collects statistics and outputs results for the BookKeeper workflow simulation.
Logs queue waits, cycle counts, time in system, and outputs final CSV/summary.
"""

import logging
import csv
import os

class StatsCollector:
    def __init__(self, state):
        self.state = state
        self.ticket_stats = {}
        os.makedirs("simulation/output", exist_ok=True)

    def log_queue_wait(self, ticket_id, stage, wait_time):
        if ticket_id not in self.ticket_stats:
            self.ticket_stats[ticket_id] = {'queue_waits': {}, 'cycles': {}, 'final_time': None}
        if stage not in self.ticket_stats[ticket_id]['queue_waits']:
            self.ticket_stats[ticket_id]['queue_waits'][stage] = []
        self.ticket_stats[ticket_id]['queue_waits'][stage].append(wait_time)
        logging.info(f"Ticket {ticket_id} waited {wait_time:.2f} in {stage} queue.")

    def log_closure(self, ticket, close_time):
        stats = self.ticket_stats.setdefault(ticket.ticket_id, {'queue_waits': {}, 'cycles': {}, 'final_time': None})
        stats['cycles']['dev_review'] = ticket.dev_review_cycles
        stats['cycles']['testing'] = ticket.test_cycles
        stats['final_time'] = close_time - ticket.arrival_time
        logging.info(f"Ticket {ticket.ticket_id} closed in {close_time - ticket.arrival_time:.2f} time units.")

    def final_report(self):
        # Output a CSV with per-ticket stats
        csvfile = "simulation/output/ticket_stats.csv"
        with open(csvfile, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["ticket_id", "total_time", "dev_review_cycles", "test_cycles"])
            for ticket_id, stat in self.ticket_stats.items():
                writer.writerow([
                    ticket_id,
                    stat.get('final_time', None),
                    stat.get('cycles', {}).get('dev_review', 0),
                    stat.get('cycles', {}).get('testing', 0)
                ])
        logging.info(f"Statistics written to {csvfile}")

        # Print aggregate statistics to log
        all_times = [s['final_time'] for s in self.ticket_stats.values() if s['final_time'] is not None]
        if all_times:
            import numpy as np
            logging.info(f"Closed tickets: {len(all_times)}")
            logging.info(f"Mean resolution time: {np.mean(all_times):.2f}")
            logging.info(f"Median resolution time: {np.median(all_times):.2f}")
            logging.info(f"95th percentile: {np.percentile(all_times, 95):.2f}")
        else:
            logging.info("No closed tickets to report.")

