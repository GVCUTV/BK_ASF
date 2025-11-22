# v4
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
        self.event_counters = {
            'scheduled_arrivals': 0,
            'arrivals': 0,
            'service_starts': {'dev_review': 0, 'testing': 0},
            'service_completions': {'dev_review': 0, 'testing': 0},
            'feedback': {'dev_review': 0, 'testing': 0},
            'routes': {'dev_review': 0, 'testing': 0, 'backlog': 0},
            'closures': 0,
        }
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

    def _ensure_ticket(self, ticket_id, arrival_time=None):
        stats = self.ticket_stats.setdefault(ticket_id, {
            'queue_waits': {}, 'cycles': {}, 'final_time': None,
            'arrival_time': arrival_time, 'closed_time': None
        })
        if stats['arrival_time'] is None and arrival_time is not None:
            stats['arrival_time'] = arrival_time
        return stats

    def log_scheduled_arrival(self, ticket_id, arrival_time):
        self.event_counters['scheduled_arrivals'] += 1
        logging.info(f"Scheduled arrival for ticket {ticket_id} at t={arrival_time:.2f}")

    def log_arrival_event(self, ticket_id, arrival_time, initial_queue):
        self.event_counters['arrivals'] += 1
        self.event_counters['routes'][initial_queue] = self.event_counters['routes'].get(initial_queue, 0) + 1
        stats = self._ensure_ticket(ticket_id, arrival_time)
        stats['arrival_time'] = arrival_time
        logging.info(
            f"Ticket {ticket_id} arrived at t={arrival_time:.2f} and entered {initial_queue}.")

    def log_queue_wait(self, ticket_id, stage, wait_time):
        """
        Log the time a ticket waited in a stage's queue.
        Keeps per-stage and total queue waits.
        """
        stats = self._ensure_ticket(ticket_id)
        if stats['arrival_time'] is None and ticket_id in self.state.tickets:
            stats['arrival_time'] = self.state.tickets[ticket_id].arrival_time
        if stage not in stats['queue_waits']:
            stats['queue_waits'][stage] = []
        stats['queue_waits'][stage].append(wait_time)
        logging.info(f"Ticket {ticket_id} waited {wait_time:.2f} in {stage} queue.")

    def log_enqueue(self, ticket_id, stage, event_time, source="unknown"):
        self.event_counters['routes'][stage] = self.event_counters['routes'].get(stage, 0) + 1
        stats = self._ensure_ticket(ticket_id)
        enqueue_list = stats.setdefault('enqueue_events', [])
        enqueue_list.append({'stage': stage, 'time': event_time, 'source': source})
        logging.info(
            "Ticket %s enqueued to %s at t=%.2f via %s", ticket_id, stage, event_time, source,
        )

    def log_routing_decision(self, ticket_id, source_queue, stage):
        logging.info("Routing decision: ticket %s pulled from %s for stage %s", ticket_id, source_queue, stage)

    def log_service_start(self, ticket_id, stage, server_idx, start_time, wait_time, service_time, completion_time, source_queue):
        self.event_counters['service_starts'][stage] = self.event_counters['service_starts'].get(stage, 0) + 1
        start_list = self._ensure_ticket(ticket_id).setdefault('service_starts', [])
        start_list.append({
            'stage': stage,
            'server': server_idx,
            'start_time': start_time,
            'wait_time': wait_time,
            'service_time': service_time,
            'completion_time': completion_time,
            'source_queue': source_queue,
        })
        logging.info(
            "Ticket %s start %s on server %s at t=%.2f (wait %.2f, svc %.2f, completes %.2f) from %s",
            ticket_id,
            stage,
            server_idx,
            start_time,
            wait_time,
            service_time,
            completion_time,
            source_queue,
        )

    def log_service_completion(self, ticket_id, stage, event_time):
        self.event_counters['service_completions'][stage] = self.event_counters['service_completions'].get(stage, 0) + 1
        completion_list = self._ensure_ticket(ticket_id).setdefault('service_completions', [])
        completion_list.append({'stage': stage, 'time': event_time})

    def log_feedback(self, ticket_id, stage, outcome, event_time):
        self.event_counters['feedback'][stage] = self.event_counters['feedback'].get(stage, 0) + 1
        feedback_list = self._ensure_ticket(ticket_id).setdefault('feedback', [])
        feedback_list.append({'stage': stage, 'outcome': outcome, 'time': event_time})
        logging.info("Ticket %s feedback at %s: %s", ticket_id, stage, outcome)

    def log_closure(self, ticket, close_time):
        """
        When a ticket is closed, store all stats: cycles, times, queues.
        """
        stats = self._ensure_ticket(ticket.ticket_id, ticket.arrival_time)
        stats['cycles']['dev_review'] = ticket.dev_review_cycles
        stats['cycles']['testing'] = ticket.test_cycles
        stats['final_time'] = close_time - ticket.arrival_time
        stats['closed_time'] = close_time
        stats['arrival_time'] = ticket.arrival_time
        self.event_counters['closures'] += 1
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
            logging.info("Event counters: %s", self.event_counters)
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

