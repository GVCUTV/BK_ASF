# v4
# file: simulation/entities.py

"""
Defines ticket entity and the shared SystemState for the BookKeeper workflow simulation.
Queues, servers, ticket state, and closure logic live here; routing belongs to WorkflowLogic.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from .config import N_DEVS, N_TESTERS


class Ticket:
    """Represents a single workflow ticket."""

    def __init__(self, ticket_id: int, arrival_time: float):
        self.ticket_id = ticket_id
        self.arrival_time = arrival_time
        self.current_stage = "backlog"
        self.history: List[Tuple[str, float]] = [("arrival", arrival_time)]
        self.dev_review_cycles = 0
        self.test_cycles = 0


class SystemState:
    """Holds queues, servers, and book-keeping data for the simulation run."""

    def __init__(self):
        self.sim_duration: float = 0.0
        self._next_ticket_id = 1
        self.closed_tickets: List[Ticket] = []
        self.tickets: Dict[int, Ticket] = {}
        self.backlog_buffer: Deque[Tuple[Ticket, float]] = deque()

        self.stage_queues: Dict[str, Deque[Tuple[Ticket, float]]] = {
            "dev_review": deque(),
            "testing": deque(),
        }
        self.stage_servers: Dict[str, List[Optional[int]]] = {
            "dev_review": [None] * N_DEVS,
            "testing": [None] * N_TESTERS,
        }

    # ---- Backlog helpers ------------------------------------------------
    def enqueue_backlog(self, ticket: Ticket, event_time: float):
        self.backlog_buffer.append((ticket, event_time))
        logging.debug("Ticket %s enqueued in backlog at t=%.2f", ticket.ticket_id, event_time)

    def dequeue_backlog(self) -> Optional[Tuple[Ticket, float]]:
        if len(self.backlog_buffer) == 0:
            return None
        return self.backlog_buffer.popleft()

    # ---- Ticket helpers -------------------------------------------------
    def issue_ticket_id(self) -> int:
        ticket_id = self._next_ticket_id
        self._next_ticket_id += 1
        return ticket_id

    def create_ticket(self, ticket_id: int, arrival_time: float) -> Ticket:
        ticket = Ticket(ticket_id, arrival_time)
        self.tickets[ticket_id] = ticket
        logging.info("Ticket %s created at t=%.2f", ticket_id, arrival_time)
        return ticket

    def close_ticket(self, ticket: Ticket, time: float, stats):
        logging.info("Ticket %s closed at t=%.2f", ticket.ticket_id, time)
        ticket.history.append(("closed", time))
        self.closed_tickets.append(ticket)
        stats.log_closure(ticket, time)

    # ---- Queue helpers --------------------------------------------------
    def enqueue(self, stage: str, ticket: Ticket, event_time: float):
        if stage not in self.stage_queues:
            logging.error("Unknown stage %s for enqueue.", stage)
            return
        self.stage_queues[stage].append((ticket, event_time))
        logging.debug("Ticket %s enqueued in %s at t=%.2f", ticket.ticket_id, stage, event_time)

    def dequeue(self, stage: str) -> Optional[Tuple[Ticket, float]]:
        queue = self.stage_queues.get(stage)
        if queue is None or len(queue) == 0:
            return None
        return queue.popleft()

    # ---- Server helpers -------------------------------------------------
    def get_free_server(self, stage: str) -> Optional[int]:
        servers = self.stage_servers.get(stage)
        if servers is None:
            logging.error("Unknown stage %s for server lookup.", stage)
            return None
        for idx, ticket_id in enumerate(servers):
            if ticket_id is None:
                return idx
        return None

    def occupy_server(self, stage: str, server_idx: int, ticket_id: int):
        servers = self.stage_servers.get(stage)
        if servers is None:
            logging.error("Unknown stage %s for occupy.", stage)
            return
        servers[server_idx] = ticket_id

    def release_server(self, stage: str, ticket_id: int) -> Optional[int]:
        servers = self.stage_servers.get(stage)
        if servers is None:
            logging.error("Unknown stage %s for release.", stage)
            return None
        for idx, current_id in enumerate(servers):
            if current_id == ticket_id:
                servers[idx] = None
                return idx
        logging.error("Ticket %s not found on %s servers during release.", ticket_id, stage)
        return None
