# v6
# file: simulation/workflow_logic.py

"""
WorkflowLogic encapsulates the workflow semantics for BookKeeper DES runs.
All routing, feedback, and queue/server transitions are handled here to keep
other layers focused on plumbing and instrumentation.
"""

from __future__ import annotations

import logging
from typing import Deque, Optional

import numpy as np

from .config import ARRIVAL_RATE, FEEDBACK_P_DEV, FEEDBACK_P_TEST, SERVICE_TIME_PARAMS
from .developer_policy import select_with_churn
from .service_distributions import sample_service_time


class WorkflowLogic:
    """Orchestrates arrivals, service completions, and feedback loops."""

    def __init__(self, state, stats):
        self.state = state
        self.stats = stats
        self.developer_pool = state.developer_pool
        known_service_stages = {"dev", "review", "testing"}
        if {"dev", "review"}.isdisjoint(SERVICE_TIME_PARAMS.keys()):
            legacy_keys = [key for key in SERVICE_TIME_PARAMS.keys() if key not in known_service_stages]
            if legacy_keys:
                legacy_key = legacy_keys[0]
                legacy_params = SERVICE_TIME_PARAMS.pop(legacy_key)
                SERVICE_TIME_PARAMS["dev"] = dict(legacy_params)
                SERVICE_TIME_PARAMS["review"] = dict(legacy_params)
                logging.info(
                    "Translated legacy %s service params into dev and review entries.",
                    legacy_key,
                )

    # ------------------------------------------------------------------
    def handle_ticket_arrival(self, ticket_id: int, event_time: float, event_queue, completion_event_cls):
        """Register an arrival, queue it, and start work when capacity is free."""
        ticket = self.state.create_ticket(ticket_id, event_time)
        ticket.current_stage = "backlog"
        self.stats.log_arrival_event(ticket.ticket_id, event_time, "backlog")
        self.stats.log_enqueue(ticket.ticket_id, "backlog", event_time, source="arrival")
        logging.info("Ticket %s arrived at t=%.2f; queued to backlog", ticket.ticket_id, event_time)
        self.state.enqueue_backlog(ticket, event_time)
        self.try_start_service("dev", event_queue, event_time, completion_event_cls)

    def schedule_next_arrival(self, event_queue, current_time: float, arrival_event_cls):
        """Poisson arrivals based on ARRIVAL_RATE until sim horizon."""
        if ARRIVAL_RATE <= 0:
            logging.warning("ARRIVAL_RATE not positive; no additional arrivals scheduled.")
            return
        interarrival = np.random.exponential(1 / ARRIVAL_RATE)
        next_time = current_time + interarrival
        if next_time > self.state.sim_duration:
            logging.info("Reached simulation horizon; no more arrivals after t=%.2f", current_time)
            return
        next_ticket_id = self.state.issue_ticket_id()
        event_queue.push(arrival_event_cls(next_time, next_ticket_id))
        logging.info("Scheduled ticket %s arrival at t=%.2f", next_ticket_id, next_time)
        self.stats.log_scheduled_arrival(next_ticket_id, next_time)

    # ------------------------------------------------------------------
    def handle_service_completion(self, ticket, stage: str, event_time: float, event_queue, completion_event_cls, service_time: float):
        """Release servers, determine routing, and continue processing."""
        ticket.history.append((f"complete_{stage}", event_time))
        logging.info("Ticket %s completed %s at t=%.2f", ticket.ticket_id, stage, event_time)
        self.stats.log_service_completion(ticket.ticket_id, stage, event_time)

        released_agent = self.state.release_server(stage, ticket.ticket_id)
        if released_agent is None:
            logging.error("Ticket %s not found on %s servers at completion.", ticket.ticket_id, stage)
        changed_stages = self.developer_pool.on_service_completion(
            released_agent if released_agent is not None else -1, stage, service_time, event_time, self.stats
        )

        if stage == "dev":
            self.stats.log_feedback(ticket.ticket_id, stage, "progress", event_time)
            self.state.enqueue("review", ticket, event_time)
            self.stats.log_enqueue(ticket.ticket_id, "review", event_time, source="dev_complete")
            self.try_start_service("review", event_queue, event_time, completion_event_cls)
        elif stage == "review":
            ticket.dev_review_cycles += 1
            ticket.review_cycles += 1
            if np.random.rand() < FEEDBACK_P_DEV:
                logging.info(
                    "Ticket %s receives review feedback; routing back to dev queue.",
                    ticket.ticket_id,
                )
                self.stats.log_feedback(ticket.ticket_id, stage, "feedback", event_time)
                self.state.enqueue("dev", ticket, event_time)
                self.stats.log_enqueue(ticket.ticket_id, "dev", event_time, source="review_feedback")
                self.try_start_service("dev", event_queue, event_time, completion_event_cls)
            else:
                self.stats.log_feedback(ticket.ticket_id, stage, "progress", event_time)
                self.state.enqueue("testing", ticket, event_time)
                self.stats.log_enqueue(ticket.ticket_id, "testing", event_time, source="review_complete")
                self.try_start_service("testing", event_queue, event_time, completion_event_cls)
        elif stage == "testing":
            ticket.test_cycles += 1
            if np.random.rand() < FEEDBACK_P_TEST:
                logging.info(
                    "Ticket %s receives testing feedback; routing to dev queue.",
                    ticket.ticket_id,
                )
                self.stats.log_feedback(ticket.ticket_id, stage, "feedback", event_time)
                self.state.enqueue("dev", ticket, event_time)
                self.stats.log_enqueue(ticket.ticket_id, "dev", event_time, source="test_feedback")
                self.try_start_service("dev", event_queue, event_time, completion_event_cls)
            else:
                self.stats.log_feedback(ticket.ticket_id, stage, "complete", event_time)
                self.state.close_ticket(ticket, event_time, self.stats)
        else:
            logging.error("Unknown stage %s encountered during completion for ticket %s.", stage, ticket.ticket_id)

        self.try_start_service(stage, event_queue, event_time, completion_event_cls)
        for affected in changed_stages:
            self.try_start_service(affected, event_queue, event_time, completion_event_cls)

    # ------------------------------------------------------------------
    def try_start_service(self, stage: str, event_queue, current_time: float, completion_event_cls):
        """Start as many tickets as possible on available servers for a stage."""
        while True:
            agent = self.state.available_agent(stage)
            if agent is None:
                break

            selected = self._select_next_ticket(stage, current_time)
            if selected is None:
                break

            ticket, queued_time, source_queue = selected
            self.state.occupy_server(stage, agent, ticket.ticket_id)
            ticket.current_stage = stage
            wait_time = max(0.0, current_time - queued_time)
            self.stats.log_queue_wait(ticket.ticket_id, stage, wait_time, current_time)
            service_time = sample_service_time(stage)
            completion_time = current_time + service_time
            event_queue.push(completion_event_cls(completion_time, ticket.ticket_id, stage, service_time))
            self.stats.log_service_start(
                ticket.ticket_id,
                stage,
                agent.agent_id,
                current_time,
                wait_time,
                service_time,
                completion_time,
                source_queue,
            )
            logging.info(
                "Ticket %s started %s on server %s at t=%.2f (wait %.2f, svc %.2f, completes %.2f) from %s",
                ticket.ticket_id,
                stage,
                agent.agent_id,
                current_time,
                wait_time,
                service_time,
                completion_time,
                source_queue,
            )

    # ------------------------------------------------------------------
    def _candidate_sources_for_stage(self, stage: str) -> list[str]:
        """Ordered list of queues/backlogs to pull from for a given stage."""
        if stage == "dev":
            return ["dev", "backlog"]
        if stage == "review":
            return ["review"]
        if stage == "testing":
            return ["testing"]
        return []

    def _select_next_ticket(self, stage: str, current_time: float):
        """Select the next ticket using a prioritized, overridable queue policy."""
        for source in self._candidate_sources_for_stage(stage):
            queue_item = self._dequeue_from_source(source, stage)
            if queue_item is not None:
                ticket, queued_time = queue_item
                self.stats.log_dequeue(ticket.ticket_id, source, current_time)
                self.stats.log_routing_decision(ticket.ticket_id, source, stage)
                return ticket, queued_time, source
        return None

    def _dequeue_from_source(self, source: str, stage: str):
        queue_ref: Optional[Deque]
        if source == "backlog":
            queue_ref = self.state.backlog_buffer
        else:
            queue_ref = self.state.stage_queues.get(source)
        if queue_ref is None or len(queue_ref) == 0:
            return None

        if stage in {"dev", "review", "testing"} and len(queue_ref) > 1:
            selected = select_with_churn(queue_ref)
            if selected:
                ticket, queued_time, idx = selected
                try:
                    item = queue_ref[idx]
                    del queue_ref[idx]
                    return item
                except Exception:  # noqa: BLE001 - defensive against deque index issues
                    logging.warning("Failed weighted selection pop; defaulting to FIFO.")
        return queue_ref.popleft()
