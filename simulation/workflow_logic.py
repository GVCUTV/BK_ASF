# v1
# file: simulation/workflow_logic.py

"""
Manages ticket arrival, state transitions, and feedback cycles for BookKeeper simulation.
All main workflow logic is here—event classes call these as needed.
"""

import logging
import numpy as np
from config import ARRIVAL_RATE, FEEDBACK_P_DEV, FEEDBACK_P_TEST
from service_distributions import sample_service_time

class WorkflowLogic:
    def __init__(self, state, stats):
        self.state = state
        self.stats = stats

    def handle_ticket_arrival(self, ticket, event_time, event_queue):
        """
        On ticket arrival: put in dev/review queue, schedule next arrival, try to start service.
        """
        logging.info(f"Ticket {ticket.ticket_id} arrived at {event_time:.2f}")
        self.state.dev_review_queue.append((ticket, event_time))
        self.try_start_service('dev_review', event_queue, event_time)

    def schedule_next_arrival(self, event_queue, current_time, ticket_id, sim_duration, TicketArrivalEvent):
        """
        Schedules the next ticket arrival event.
        """
        next_time = current_time + np.random.exponential(1/ARRIVAL_RATE)
        if next_time < self.state.sim_duration:
            event_queue.push(TicketArrivalEvent(next_time, ticket_id + 1))
            logging.info(f"Scheduled ticket {ticket_id + 1} arrival at {next_time:.2f}")

    def handle_service_completion(self, ticket, stage, event_time, event_queue, ServiceCompletionEvent):
        """
        On service completion, check for feedback or progression to next stage or closure.
        """
        ticket.history.append((f'complete_{stage}', event_time))
        if stage == 'dev_review':
            ticket.dev_review_cycles += 1
            # Free server
            idx = self.state.dev_review_servers.index(ticket.ticket_id)
            self.state.dev_review_servers[idx] = None
            if np.random.rand() < FEEDBACK_P_DEV:
                logging.info(f"Ticket {ticket.ticket_id} receives feedback at dev/review (loop back).")
                self.state.dev_review_queue.append((ticket, event_time))
                self.try_start_service('dev_review', event_queue, event_time)
            else:
                self.state.testing_queue.append((ticket, event_time))
                self.try_start_service('testing', event_queue, event_time)
            self.try_start_service('dev_review', event_queue, event_time)
        elif stage == 'testing':
            ticket.test_cycles += 1
            idx = self.state.testing_servers.index(ticket.ticket_id)
            self.state.testing_servers[idx] = None
            if np.random.rand() < FEEDBACK_P_TEST:
                logging.info(f"Ticket {ticket.ticket_id} receives feedback at testing (loop to dev/review).")
                self.state.dev_review_queue.append((ticket, event_time))
                self.try_start_service('dev_review', event_queue, event_time)
            else:
                self.state.close_ticket(ticket, event_time, self.stats)
            self.try_start_service('testing', event_queue, event_time)

    def try_start_service(self, stage, event_queue, time):
        """
        Starts service for tickets if a server is free.
        """
        if stage == 'dev_review':
            for idx, server in enumerate(self.state.dev_review_servers):
                if server is None and self.state.dev_review_queue:
                    ticket, queued_time = self.state.dev_review_queue.pop(0)
                    self.state.dev_review_servers[idx] = ticket.ticket_id
                    service_time = sample_service_time('dev_review')
                    event_time = time + service_time
                    from events import ServiceCompletionEvent
                    event_queue.push(ServiceCompletionEvent(event_time, ticket.ticket_id, 'dev_review'))
                    logging.info(f"Ticket {ticket.ticket_id} started dev/review on server {idx} (t={time:.2f}), will finish at t={event_time:.2f}")
                    self.stats.log_queue_wait(ticket.ticket_id, stage, time - queued_time)
        elif stage == 'testing':
            for idx, server in enumerate(self.state.testing_servers):
                if server is None and self.state.testing_queue:
                    ticket, queued_time = self.state.testing_queue.pop(0)
                    self.state.testing_servers[idx] = ticket.ticket_id
                    service_time = sample_service_time('testing')
                    event_time = time + service_time
                    from events import ServiceCompletionEvent
                    event_queue.push(ServiceCompletionEvent(event_time, ticket.ticket_id, 'testing'))
                    logging.info(f"Ticket {ticket.ticket_id} started testing on server {idx} (t={time:.2f}), will finish at t={event_time:.2f}")
                    self.stats.log_queue_wait(ticket.ticket_id, stage, time - queued_time)
