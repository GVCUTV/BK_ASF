# v2
# file: simulation/entities.py

"""
Defines Ticket entity and SystemState for BookKeeper workflow simulation.
Queues, servers, ticket state, and closure logic only.
Workflow logic is now in workflow_logic.py.
"""

import logging
from config import N_DEVS, N_TESTERS

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

    def close_ticket(self, ticket, time, stats):
        logging.info(f"Ticket {ticket.ticket_id} closed at {time:.2f}")
        ticket.history.append(('closed', time))
        self.closed_tickets.append(ticket)
        stats.log_closure(ticket, time)
