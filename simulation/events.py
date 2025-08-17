# v2
# file: simulation/events.py

"""
Defines event classes and priority event queue for BookKeeper simulation.
Handles ticket arrival, service completions, and feedback cycles
by delegating to WorkflowLogic for all workflow transitions.
"""

import heapq
import numpy as np
import logging
from config import ARRIVAL_RATE
from workflow_logic import WorkflowLogic

class Event:
    def __init__(self, time, ticket_id):
        self.time = time
        self.ticket_id = ticket_id

    def __lt__(self, other):
        return self.time < other.time

    def process(self, event_queue, state, stats):
        raise NotImplementedError("Subclasses must implement process method.")

    def __str__(self):
        return f"{self.__class__.__name__}(t={self.time:.2f}, ticket={self.ticket_id})"

class TicketArrivalEvent(Event):
    def __init__(self, time, ticket_id):
        super().__init__(time, ticket_id)

    def process(self, event_queue, state, stats):
        logic = WorkflowLogic(state, stats)
        ticket = state.create_ticket(self.ticket_id, self.time)
        logic.handle_ticket_arrival(ticket, self.time, event_queue)
        # Schedule next arrival
        logic.schedule_next_arrival(event_queue, self.time, self.ticket_id, state.sim_duration, TicketArrivalEvent)

class ServiceCompletionEvent(Event):
    def __init__(self, time, ticket_id, stage):
        super().__init__(time, ticket_id)
        self.stage = stage  # 'dev_review' or 'testing'

    def process(self, event_queue, state, stats):
        logic = WorkflowLogic(state, stats)
        ticket = state.tickets[self.ticket_id]
        logic.handle_service_completion(ticket, self.stage, self.time, event_queue, ServiceCompletionEvent)

class EventQueue:
    def __init__(self):
        self._q = []

    def push(self, event):
        heapq.heappush(self._q, event)
        logging.debug(f"Event queued: {event}")

    def pop(self):
        return heapq.heappop(self._q)

    def empty(self):
        return len(self._q) == 0

    def next_event_time(self):
        return self._q[0].time if self._q else float('inf')

    def schedule_initial_arrivals(self, sim_duration, state, stats):
        self.push(TicketArrivalEvent(0.0, 1))
        state.sim_duration = sim_duration
        logging.info("Initial arrival event scheduled at t=0.")
