# v4
# file: simulation/events.py

"""
Defines event classes and priority event queue for the BookKeeper simulation.
Events remain policy-agnostic by delegating workflow semantics to WorkflowLogic.
"""

from __future__ import annotations

import heapq
import logging
from typing import Optional, Type

from .workflow_logic import WorkflowLogic


class Event:
    """Base event storing the time and target ticket identifier."""

    def __init__(self, time: float, ticket_id: Optional[int]):
        self.time = time
        self.ticket_id = ticket_id

    def __lt__(self, other: "Event") -> bool:
        return self.time < other.time

    def process(self, event_queue, state, stats):  # pragma: no cover - interface only
        raise NotImplementedError("Subclasses must implement process().")

    def __str__(self) -> str:
        ticket = self.ticket_id if self.ticket_id is not None else "-"
        return f"{self.__class__.__name__}(t={self.time:.2f}, ticket={ticket})"


class TicketArrivalEvent(Event):
    """Arrival event that forwards all queueing logic to WorkflowLogic."""

    def process(self, event_queue, state, stats):
        logic = WorkflowLogic(state, stats)
        logic.handle_ticket_arrival(self.ticket_id, self.time, event_queue, ServiceCompletionEvent)
        logic.schedule_next_arrival(event_queue, self.time, TicketArrivalEvent)


class ServiceCompletionEvent(Event):
    """Service completion event — routing handled in WorkflowLogic."""

    def __init__(self, time: float, ticket_id: int, stage: str):
        super().__init__(time, ticket_id)
        self.stage = stage

    def process(self, event_queue, state, stats):
        logic = WorkflowLogic(state, stats)
        ticket = state.tickets.get(self.ticket_id)
        if ticket is None:
            logging.error(
                "ServiceCompletionEvent for missing ticket %s at t=%.2f (stage=%s)",
                self.ticket_id,
                self.time,
                self.stage,
            )
            return
        logic.handle_service_completion(ticket, self.stage, self.time, event_queue, ServiceCompletionEvent)


class EventQueue:
    """Min-heap priority queue for chronological DES execution."""

    def __init__(self):
        self._q: list[Event] = []

    def push(self, event: Event):
        heapq.heappush(self._q, event)
        logging.debug("Event queued: %s", event)

    def pop(self) -> Event:
        event = heapq.heappop(self._q)
        logging.debug("Event dequeued: %s", event)
        return event

    def empty(self) -> bool:
        return len(self._q) == 0

    def next_event_time(self) -> float:
        return self._q[0].time if self._q else float("inf")

    def schedule_initial_arrivals(
        self,
        state,
        stats=None,
        arrival_event_cls: Type[TicketArrivalEvent] = TicketArrivalEvent,
    ):
        """Seed the queue with the first arrival at time zero."""
        first_ticket_id = state.issue_ticket_id()
        self.push(arrival_event_cls(0.0, first_ticket_id))
        logging.info("Initial arrival for ticket %s scheduled at t=0.00", first_ticket_id)
        if stats is not None:
            stats.log_scheduled_arrival(first_ticket_id, 0.0)
