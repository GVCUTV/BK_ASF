# v7
# file: simulation/entities.py

"""
Defines ticket entity and the shared SystemState for the BookKeeper workflow simulation.
Queues, servers, ticket state, and closure logic live here; routing belongs to WorkflowLogic.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from .developer_policy import DeveloperAgent


class Ticket:
    """Represents a single workflow ticket."""

    def __init__(self, ticket_id: int, arrival_time: float):
        self.ticket_id = ticket_id
        self.arrival_time = arrival_time
        self.current_stage = "backlog"
        self.history: List[Tuple[str, float]] = [("arrival", arrival_time)]
        self.dev_cycles = 0
        self.review_cycles = 0
        self.test_cycles = 0
        self.churn_add: Optional[float] = None
        self.churn_mod: Optional[float] = None
        self.churn_del: Optional[float] = None


class SystemState:
    """Holds queues, servers, and book-keeping data for the simulation run."""

    def __init__(self, developer_pool):
        self.sim_duration: float = 0.0
        self._next_ticket_id = 1
        self.closed_tickets: List[Ticket] = []
        self.tickets: Dict[int, Ticket] = {}
        self.stage_names: Tuple[str, str, str] = ("dev", "review", "testing")
        self.backlog_buffer: Deque[Tuple[Ticket, float]] = deque()
        self.developer_pool = developer_pool

        # Review and testing keep dedicated queues; backlog_buffer is the dev queue of record.
        self.stage_queues: Dict[str, Deque[Tuple[Ticket, float]]] = {
            "review": deque(),
            "testing": deque(),
        }
        self.stage_assignments: Dict[str, Dict[int, int]] = {
            "dev": {},
            "review": {},
            "testing": {},
        }
        self.ticket_agent: Dict[int, int] = {}

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
    def available_agent(self, stage: str) -> Optional[DeveloperAgent]:
        agent = self.developer_pool.available_agent_for_stage(stage)
        if agent is None:
            logging.debug("No available agent for stage %s at this time.", stage)
        return agent

    def occupy_server(self, stage: str, agent: DeveloperAgent, ticket_id: int):
        assignments = self.stage_assignments.get(stage)
        if assignments is None:
            logging.error("Unknown stage %s for occupy.", stage)
            return
        assignments[agent.agent_id] = ticket_id
        self.ticket_agent[ticket_id] = agent.agent_id
        agent.busy = True

    def release_server(self, stage: str, ticket_id: int) -> Optional[int]:
        assignments = self.stage_assignments.get(stage)
        if assignments is None:
            logging.error("Unknown stage %s for release.", stage)
            return None
        agent_id = self.ticket_agent.pop(ticket_id, None)
        if agent_id is None:
            logging.error("Ticket %s not tracked for release on stage %s.", ticket_id, stage)
            return None
        assignments.pop(agent_id, None)
        return agent_id

    def capacity_for_stage(self, stage: str) -> int:
        capacity = 0
        snapshot = self.developer_pool.current_capacity_by_stage()
        if stage == "dev":
            capacity = snapshot.get("DEV", 0)
        elif stage == "review":
            capacity = snapshot.get("REV", 0)
        elif stage == "testing":
            capacity = snapshot.get("TEST", 0)
        return capacity
