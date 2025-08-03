# v1
# file: entities.py

"""
Defines Ticket entity and SystemState for BookKeeper workflow simulation.
Handles queues, servers, ticket state, and transitions (including feedback loops).
"""

import logging
from service_distributions import sample_service_time
from config import N_DEVS, N_TESTERS, FEEDBACK_P_DEV, FEEDBACK_P_TEST

class Ticket:
    def __init__(self, ticket_id, arrival_time):
        self.ticket_id = ticket_id
        self.arrival_time = arrival_time
        self.current_stage = 'dev_review'
        self.history = [('arrival', arrival_time)]
        self.dev_review_cycles = 0
        self.test_cycles = 0

class SystemState:
    def __init__(self):
        self.sim_duration = None
        self.dev_review_queue = []
        self.dev_review_servers = [None] * N_DEVS
        self.testing_queue = []
        self.testing_servers = [None] * N_TESTERS
        self.closed_tickets = []
        self.tickets = {}

    def create_ticket(self, ticket_id, arrival_time):
        ticket = Ticket(ticket_id, arrival_time)
        self.tickets[ticket_id] = ticket
        return ticket

    def enter_dev_review(self, ticket, time, event_queue, stats):
        logging.info(f"Ticket {ticket.ticket_id} enters dev/review queue at {time:.2f}")
        self.dev_review_queue.append((ticket, time))
        self.try_start_service('dev_review', event_queue, time, stats)

    def try_start_service(self, stage, event_queue, time, stats):
        if stage == 'dev_review':
            for idx, server in enumerate(self.dev_review_servers):
                if server is None and self.dev_review_queue:
                    ticket, queued_time = self.dev_review_queue.pop(0)
                    self.dev_review_servers[idx] = ticket.ticket_id
                    service_time = sample_service_time('dev_review')
                    event_time = time + service_time
                    from events import ServiceCompletionEvent
                    event_queue.push(ServiceCompletionEvent(event_time, ticket.ticket_id, 'dev_review'))
                    logging.info(f"Ticket {ticket.ticket_id} started dev/review on server {idx} (t={time:.2f}), will finish at t={event_time:.2f}")
                    stats.log_queue_wait(ticket.ticket_id, stage, time - queued_time)
        elif stage == 'testing':
            for idx, server in enumerate(self.testing_servers):
                if server is None and self.testing_queue:
                    ticket, queued_time = self.testing_queue.pop(0)
                    self.testing_servers[idx] = ticket.ticket_id
                    service_time = sample_service_time('testing')
                    event_time = time + service_time
                    from events import ServiceCompletionEvent
                    event_queue.push(ServiceCompletionEvent(event_time, ticket.ticket_id, 'testing'))
                    logging.info(f"Ticket {ticket.ticket_id} started testing on server {idx} (t={time:.2f}), will finish at t={event_time:.2f}")
                    stats.log_queue_wait(ticket.ticket_id, stage, time - queued_time)

    def complete_service(self, ticket_id, stage, time, event_queue, stats):
        ticket = self.tickets[ticket_id]
        ticket.history.append((f'complete_{stage}', time))
        if stage == 'dev_review':
            ticket.dev_review_cycles += 1
            # Free server
            idx = self.dev_review_servers.index(ticket_id)
            self.dev_review_servers[idx] = None
            # Feedback or move to testing
            import numpy as np
            if np.random.rand() < FEEDBACK_P_DEV:
                logging.info(f"Ticket {ticket_id} receives feedback at dev/review, loop back.")
                self.enter_dev_review(ticket, time, event_queue, stats)
            else:
                self.enter_testing(ticket, time, event_queue, stats)
            self.try_start_service('dev_review', event_queue, time, stats)
        elif stage == 'testing':
            ticket.test_cycles += 1
            idx = self.testing_servers.index(ticket_id)
            self.testing_servers[idx] = None
            import numpy as np
            if np.random.rand() < FEEDBACK_P_TEST:
                logging.info(f"Ticket {ticket_id} receives feedback at testing, loop back to dev/review.")
                self.enter_dev_review(ticket, time, event_queue, stats)
            else:
                self.close_ticket(ticket, time, stats)
            self.try_start_service('testing', event_queue, time, stats)

    def enter_testing(self, ticket, time, event_queue, stats):
        logging.info(f"Ticket {ticket.ticket_id} enters testing queue at {time:.2f}")
        ticket.current_stage = 'testing'
        self.testing_queue.append((ticket, time))
        self.try_start_service('testing', event_queue, time, stats)

    def close_ticket(self, ticket, time, stats):
        logging.info(f"Ticket {ticket.ticket_id} closed at {time:.2f}")
        ticket.history.append(('closed', time))
        self.closed_tickets.append(ticket)
        stats.log_closure(ticket, time)

