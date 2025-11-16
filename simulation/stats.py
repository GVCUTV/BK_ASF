# v3
# file: simulation/stats.py

"""
Collects statistics and outputs results for the BookKeeper workflow simulation.
Logs queue waits, cycle counts, time in system, feedback cycles, and outputs detailed per-ticket CSV and summary stats.
All logs go to file and stdout.
"""

import csv
import logging
import os

class StatsCollector:
    def __init__(self, state):
        self.state = state
        self.ticket_stats = {}
        base_dir = os.path.dirname(__file__)
        self.output_dir = os.path.join(base_dir, "output")
        self.logs_dir = os.path.join(base_dir, "logs")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        self.csvfile = os.path.join(self.output_dir, "ticket_stats.csv")
        self.logfile = os.path.join(self.logs_dir, "simulation_stats.log")

        # Setup a dedicated file handler for stats logging
        fh = logging.FileHandler(self.logfile, mode='w')
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(fh)

    def log_queue_wait(self, ticket_id, stage, wait_time):
        """
        Log the time a ticket waited in a stage's queue.
        Keeps per-stage and total queue waits.
        """
        stats = self.ticket_stats.setdefault(ticket_id, {
            'queue_waits': {}, 'cycles': {}, 'final_time': None,
            'arrival_time': None, 'closed_time': None
        })
        if stats['arrival_time'] is None and ticket_id in self.state.tickets:
            stats['arrival_time'] = self.state.tickets[ticket_id].arrival_time
        if stage not in stats['queue_waits']:
            stats['queue_waits'][stage] = []
        stats['queue_waits'][stage].append(wait_time)
        logging.info(f"Ticket {ticket_id} waited {wait_time:.2f} in {stage} queue.")

    def log_closure(self, ticket, close_time):
        """
        When a ticket is closed, store all stats: cycles, times, queues.
        """
        stats = self.ticket_stats.setdefault(ticket.ticket_id, {
            'queue_waits': {}, 'cycles': {}, 'final_time': None,
            'arrival_time': ticket.arrival_time, 'closed_time': close_time
        })
        stats['cycles']['dev_review'] = ticket.dev_review_cycles
        stats['cycles']['testing'] = ticket.test_cycles
        stats['final_time'] = close_time - ticket.arrival_time
        stats['closed_time'] = close_time
        stats['arrival_time'] = ticket.arrival_time
        logging.info(
            f"Ticket {ticket.ticket_id} closed in {close_time - ticket.arrival_time:.2f} units. "
            f"DevReview cycles: {ticket.dev_review_cycles}, Test cycles: {ticket.test_cycles}"
        )

    def final_report(self):
        """
        At simulation end, write all per-ticket stats to CSV and log/print aggregate summary.
        """
        with open(self.csvfile, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "ticket_id", "arrival_time", "closed_time", "total_time",
                "dev_review_cycles", "test_cycles",
                "wait_dev_review", "wait_testing"
            ])
            for ticket_id, stat in self.ticket_stats.items():
                wait_dev_review = sum(stat['queue_waits'].get('dev_review', []))
                wait_testing = sum(stat['queue_waits'].get('testing', []))
                writer.writerow([
                    ticket_id,
                    stat.get('arrival_time', None),
                    stat.get('closed_time', None),
                    stat.get('final_time', None),
                    stat.get('cycles', {}).get('dev_review', 0),
                    stat.get('cycles', {}).get('testing', 0),
                    wait_dev_review,
                    wait_testing
                ])
        logging.info(f"Statistics written to {self.csvfile}")

        # Aggregate statistics
        all_times = [s['final_time'] for s in self.ticket_stats.values() if s['final_time'] is not None]
        dev_cycles = [s['cycles'].get('dev_review', 0) for s in self.ticket_stats.values()]
        test_cycles = [s['cycles'].get('testing', 0) for s in self.ticket_stats.values()]

        if all_times:
            import numpy as np
            logging.info("------ SIMULATION SUMMARY ------")
            logging.info(f"Closed tickets: {len(all_times)}")
            logging.info(f"Mean resolution time: {np.mean(all_times):.2f}")
            logging.info(f"Median resolution time: {np.median(all_times):.2f}")
            logging.info(f"95th percentile: {np.percentile(all_times, 95):.2f}")
            logging.info(f"Mean dev/review cycles: {np.mean(dev_cycles):.2f}")
            logging.info(f"Mean test cycles: {np.mean(test_cycles):.2f}")
            print("------ SIMULATION SUMMARY ------")
            print(f"Closed tickets: {len(all_times)}")
            print(f"Mean resolution time: {np.mean(all_times):.2f}")
            print(f"Median resolution time: {np.median(all_times):.2f}")
            print(f"95th percentile: {np.percentile(all_times, 95):.2f}")
            print(f"Mean dev/review cycles: {np.mean(dev_cycles):.2f}")
            print(f"Mean test cycles: {np.mean(test_cycles):.2f}")
        else:
            logging.info("No closed tickets to report.")
            print("No closed tickets to report.")

