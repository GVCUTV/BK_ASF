# v1
# file: simulation/events.py

"""
Defines event classes and priority event queue for BookKeeper simulation.
Handles ticket arrival, service completions, and feedback cycles.
"""

import heapq
import numpy as np
import logging
from config import ARRIVAL_RATE

class Event:
    def __init__(self, time, ticket_id):
        self.time = time
        self.ticket_id = ticket_id

    def __lt__(self, other):
        # For heapq: events are ordered by scheduled time
        return self.time < other.time

    def process(self, event_queue, state, stats):
        raise NotImplementedError("Subclasses must implement process method.")

    def __str__(self):
        return f"{self.__class__.__name__}(t={self.time:.2f}, ticket={self.ticket_id})"

class TicketArrivalEvent(Event):
    def __init__(self, time, ticket_id):
        super().__init__(time, ticket_id)

    def process(self, event_queue, state, stats):
        logging.info(f"Ticket {self.ticket_id} arrived at time {self.time:.2f}")
        ticket = state.create_ticket(self.ticket_id, self.time)
        # Try to add ticket to dev/review queue (may be idle or wait)
        state.enter_dev_review(ticket, self.time, event_queue, stats)
        # Schedule next arrival
        next_arrival = self.time + np.random.exponential(1/ARRIVAL_RATE)
        if next_arrival < state.sim_duration:
            event_queue.push(TicketArrivalEvent(next_arrival, self.ticket_id + 1))

class ServiceCompletionEvent(Event):
    def __init__(self, time, ticket_id, stage):
        super().__init__(time, ticket_id)
        self.stage = stage  # 'dev_review' or 'testing'

    def process(self, event_queue, state, stats):
        logging.info(f"Ticket {self.ticket_id} completed {self.stage} at {self.time:.2f}")
        state.complete_service(self.ticket_id, self.stage, self.time, event_queue, stats)

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
        # Start with ticket 1 at t=0
        self.push(TicketArrivalEvent(0.0, 1))
        state.sim_duration = sim_duration
        logging.info("Initial arrival event scheduled at t=0.")

