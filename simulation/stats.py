# v8
# file: simulation/stats.py

"""
Collects statistics and outputs results for the BookKeeper workflow simulation.
Logs queue waits, cycle counts, time in system, feedback cycles, and outputs detailed per-ticket CSV and summary stats.
All logs go to file and stdout.
"""

from __future__ import annotations

import csv
import logging
import os
from statistics import mean
from typing import Any, Dict, List, Optional

import numpy as np


class StatsCollector:
    """Tracks per-ticket histories, queue metrics, and aggregate KPIs."""

    def __init__(self, state):
        self.state = state
        self.ticket_stats: Dict[int, Dict[str, Any]] = {}
        self.stage_names: List[str] = list(getattr(self.state, "stage_names", []))
        if not self.stage_names:
            self.stage_names = ["dev"] + sorted(self.state.stage_queues.keys())
        self.event_counters: Dict[str, Any] = {
            "scheduled_arrivals": 0,
            "arrivals": 0,
            "service_starts": {stage: 0 for stage in self.stage_names},
            "service_completions": {stage: 0 for stage in self.stage_names},
            "feedback": {stage: 0 for stage in self.stage_names},
            "routes": {"backlog": 0, **{stage: 0 for stage in self.stage_names}},
            "closures": 0,
        }

        self.queue_tracking: Dict[str, Dict[str, float]] = {
            stage: {"length": 0.0, "last_time": 0.0, "area": 0.0} for stage in self.stage_names
        }
        self.queue_wait_records: Dict[str, List[float]] = {stage: [] for stage in self.stage_names}
        self.service_busy_time: Dict[str, float] = {stage: 0.0 for stage in self.stage_names}
        self.stage_throughput: Dict[str, int] = {stage: 0 for stage in self.stage_names}
        self.service_time_records: Dict[str, List[float]] = {stage: [] for stage in self.stage_names}
        self.developer_state_time: Dict[str, float] = {state: 0.0 for state in ["OFF", "DEV", "REV", "TEST"]}
        self.developer_stints: Dict[str, List[float]] = {state: [] for state in ["OFF", "DEV", "REV", "TEST"]}

        base_dir = os.path.dirname(__file__)
        self.output_dir = os.path.join(base_dir, "output")
        self.logs_dir = os.path.join(base_dir, "logs")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        self.ticket_csvfile = os.path.join(self.output_dir, "tickets_stats.csv")
        self.summary_csvfile = os.path.join(self.output_dir, "summary_stats.csv")
        self.logfile = os.path.join(self.logs_dir, "simulation_stats.log")

        # Dedicated file handler so stats are persisted independently of main log.
        fh = logging.FileHandler(self.logfile, mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(fh)

    # ------------------------------------------------------------------
    # Ticket state helpers
    # ------------------------------------------------------------------
    def _ensure_ticket(self, ticket_id: int, arrival_time: Optional[float] = None) -> Dict[str, Any]:
        stats = self.ticket_stats.setdefault(
            ticket_id,
            {
                "queue_waits": {},
                "cycles": {},
                "final_time": None,
                "arrival_time": arrival_time,
                "closed_time": None,
                "timeline": [],
                "service_starts": [],
                "service_completions": [],
            },
        )
        if stats["arrival_time"] is None and arrival_time is not None:
            stats["arrival_time"] = arrival_time
        return stats

    def _record_event(
        self,
        ticket_id: int,
        label: str,
        event_time: float,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        stats = self._ensure_ticket(ticket_id)
        entry = {"label": label, "time": event_time}
        if stage:
            entry["stage"] = stage
        if details:
            entry.update(details)
        stats.setdefault("timeline", []).append(entry)

    # ------------------------------------------------------------------
    # Queue length tracking helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _tracking_stage(stage: str) -> str:
        """Normalize backlog events so the dev queue metric reflects the backlog."""

        return "dev" if stage == "backlog" else stage

    def _update_queue_length(self, stage: str, event_time: float, delta: float) -> None:
        stage = self._tracking_stage(stage)
        record = self.queue_tracking.setdefault(stage, {"length": 0.0, "last_time": event_time, "area": 0.0})
        elapsed = event_time - record["last_time"]
        if elapsed > 0:
            record["area"] += record["length"] * elapsed
        record["length"] = max(0.0, record["length"] + delta)
        record["last_time"] = event_time

    def _finalize_queue_areas(self, sim_end_time: float) -> None:
        for record in self.queue_tracking.values():
            elapsed = sim_end_time - record["last_time"]
            if elapsed > 0:
                record["area"] += record["length"] * elapsed
                record["last_time"] = sim_end_time

    # ------------------------------------------------------------------
    # Logging hooks invoked by workflow
    # ------------------------------------------------------------------
    def log_scheduled_arrival(self, ticket_id: int, arrival_time: float) -> None:
        self.event_counters["scheduled_arrivals"] += 1
        logging.info("Scheduled arrival for ticket %s at t=%.2f", ticket_id, arrival_time)

    def log_arrival_event(self, ticket_id: int, arrival_time: float, initial_queue: str) -> None:
        self.event_counters["arrivals"] += 1
        self.event_counters["routes"][initial_queue] = self.event_counters["routes"].get(initial_queue, 0) + 1
        stats = self._ensure_ticket(ticket_id, arrival_time)
        stats["arrival_time"] = arrival_time
        self._record_event(ticket_id, "arrival", arrival_time, stage=initial_queue)
        logging.info("Ticket %s arrived at t=%.2f and entered %s.", ticket_id, arrival_time, initial_queue)

    def log_enqueue(self, ticket_id: int, stage: str, event_time: float, source: str = "unknown") -> None:
        self.event_counters["routes"][stage] = self.event_counters["routes"].get(stage, 0) + 1
        self._update_queue_length(stage, event_time, delta=1)
        stats = self._ensure_ticket(ticket_id)
        enqueue_list = stats.setdefault("enqueue_events", [])
        enqueue_list.append({"stage": stage, "time": event_time, "source": source})
        self._record_event(ticket_id, "enqueue", event_time, stage=stage, details={"source": source})
        logging.info("Ticket %s enqueued to %s at t=%.2f via %s", ticket_id, stage, event_time, source)

    def log_dequeue(self, ticket_id: int, stage: str, event_time: float) -> None:
        self._update_queue_length(stage, event_time, delta=-1)
        self._record_event(ticket_id, "dequeue", event_time, stage=stage)
        logging.debug("Ticket %s dequeued from %s at t=%.2f", ticket_id, stage, event_time)

    def log_queue_wait(self, ticket_id: int, stage: str, wait_time: float, event_time: float) -> None:
        """Log the time a ticket waited in a stage's queue."""
        stats = self._ensure_ticket(ticket_id)
        if stats["arrival_time"] is None and ticket_id in self.state.tickets:
            stats["arrival_time"] = self.state.tickets[ticket_id].arrival_time
        stats.setdefault("queue_waits", {}).setdefault(stage, []).append(wait_time)
        self.queue_wait_records.setdefault(stage, []).append(wait_time)
        self._record_event(ticket_id, "queue_wait", event_time, stage=stage, details={"wait_time": wait_time})
        logging.info("Ticket %s waited %.2f in %s queue.", ticket_id, wait_time, stage)

    def log_routing_decision(self, ticket_id: int, source_queue: str, stage: str) -> None:
        logging.info("Routing decision: ticket %s pulled from %s for stage %s", ticket_id, source_queue, stage)

    def log_service_start(
        self,
        ticket_id: int,
        stage: str,
        server_idx: int,
        start_time: float,
        wait_time: float,
        service_time: float,
        completion_time: float,
        source_queue: str,
    ) -> None:
        self.event_counters["service_starts"][stage] = self.event_counters["service_starts"].get(stage, 0) + 1
        start_list = self._ensure_ticket(ticket_id).setdefault("service_starts", [])
        start_list.append(
            {
                "stage": stage,
                "server": server_idx,
                "start_time": start_time,
                "wait_time": wait_time,
                "service_time": service_time,
                "completion_time": completion_time,
                "source_queue": source_queue,
            }
        )
        usable_time = max(0.0, min(service_time, self.state.sim_duration - start_time))
        self.service_busy_time[stage] += usable_time
        self.service_time_records[stage].append(service_time)
        self._record_event(
            ticket_id,
            "service_start",
            start_time,
            stage=stage,
            details={
                "server": server_idx,
                "wait_time": wait_time,
                "service_time": service_time,
                "completion_time": completion_time,
                "source_queue": source_queue,
            },
        )
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

    def log_service_completion(self, ticket_id: int, stage: str, event_time: float) -> None:
        self.event_counters["service_completions"][stage] = self.event_counters["service_completions"].get(stage, 0) + 1
        self.stage_throughput[stage] += 1
        completion_list = self._ensure_ticket(ticket_id).setdefault("service_completions", [])
        completion_list.append({"stage": stage, "time": event_time})
        self._record_event(ticket_id, "service_completion", event_time, stage=stage)

    def log_feedback(self, ticket_id: int, stage: str, outcome: str, event_time: float) -> None:
        self.event_counters["feedback"][stage] = self.event_counters["feedback"].get(stage, 0) + 1
        feedback_list = self._ensure_ticket(ticket_id).setdefault("feedback", [])
        feedback_list.append({"stage": stage, "outcome": outcome, "time": event_time})
        self._record_event(ticket_id, "feedback", event_time, stage=stage, details={"outcome": outcome})
        logging.info("Ticket %s feedback at %s: %s", ticket_id, stage, outcome)

    def log_closure(self, ticket, close_time: float) -> None:
        """Persist ticket closure details and cycle counts."""
        stats = self._ensure_ticket(ticket.ticket_id, ticket.arrival_time)
        stats["cycles"]["dev"] = ticket.dev_cycles
        stats["cycles"]["review"] = ticket.review_cycles
        stats["cycles"]["testing"] = ticket.test_cycles
        stats["final_time"] = close_time - ticket.arrival_time
        stats["closed_time"] = close_time
        stats["arrival_time"] = ticket.arrival_time
        self.event_counters["closures"] += 1
        self._record_event(ticket.ticket_id, "closed", close_time)
        logging.info(
            "Ticket %s closed in %.2f units. Dev cycles: %s, Review cycles: %s, Test cycles: %s",
            ticket.ticket_id,
            close_time - ticket.arrival_time,
            ticket.dev_cycles,
            ticket.review_cycles,
            ticket.test_cycles,
        )

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------
    def _calculate_ticket_row(self, ticket_id: int, stat: Dict[str, Any]) -> Dict[str, Any]:
        wait_dev = sum(stat.get("queue_waits", {}).get("dev", []))
        wait_review = sum(stat.get("queue_waits", {}).get("review", []))
        wait_testing = sum(stat.get("queue_waits", {}).get("testing", []))
        service_dev = sum(
            start["service_time"] for start in stat.get("service_starts", []) if start.get("stage") == "dev"
        )
        service_review = sum(
            start["service_time"] for start in stat.get("service_starts", []) if start.get("stage") == "review"
        )
        service_test = sum(
            start["service_time"] for start in stat.get("service_starts", []) if start.get("stage") == "testing"
        )

        return {
            "ticket_id": ticket_id,
            "arrival_time": stat.get("arrival_time"),
            "closed_time": stat.get("closed_time"),
            "time_in_system": stat.get("final_time"),
            "dev_cycles": stat.get("cycles", {}).get("dev", 0),
            "review_cycles": stat.get("cycles", {}).get("review", 0),
            "test_cycles": stat.get("cycles", {}).get("testing", 0),
            "wait_dev": wait_dev,
            "wait_review": wait_review,
            "wait_testing": wait_testing,
            "total_wait": wait_dev + wait_review + wait_testing,
            "service_time_dev": service_dev,
            "service_time_review": service_review,
            "service_time_testing": service_test,
            "service_starts_dev": sum(1 for start in stat.get("service_starts", []) if start.get("stage") == "dev"),
            "service_starts_review": sum(1 for start in stat.get("service_starts", []) if start.get("stage") == "review"),
            "service_starts_testing": sum(1 for start in stat.get("service_starts", []) if start.get("stage") == "testing"),
            # Reserved Markov-aware fields for 4.3A compatibility
            "markov_time_dev": "",
            "markov_time_rev": "",
            "markov_time_test": "",
            "markov_time_off": "",
            "markov_stint_counts": "",
        }

    def _write_ticket_csv(self) -> None:
        fieldnames = [
            "ticket_id",
            "arrival_time",
            "closed_time",
            "time_in_system",
            "dev_cycles",
            "review_cycles",
            "test_cycles",
            "wait_dev",
            "wait_review",
            "wait_testing",
            "total_wait",
            "service_time_dev",
            "service_time_review",
            "service_time_testing",
            "service_starts_dev",
            "service_starts_review",
            "service_starts_testing",
            "markov_time_dev",
            "markov_time_rev",
            "markov_time_test",
            "markov_time_off",
            "markov_stint_counts",
        ]
        with open(self.ticket_csvfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for ticket_id, stat in sorted(self.ticket_stats.items()):
                writer.writerow(self._calculate_ticket_row(ticket_id, stat))
        logging.info("Per-ticket statistics written to %s", self.ticket_csvfile)

    def _aggregate_summary(self) -> List[Dict[str, Any]]:
        self._finalize_queue_areas(self.state.sim_duration)
        all_times = [s.get("final_time") for s in self.ticket_stats.values() if s.get("final_time") is not None]
        dev_cycles = [s.get("cycles", {}).get("dev", 0) for s in self.ticket_stats.values()]
        review_cycles = [s.get("cycles", {}).get("review", 0) for s in self.ticket_stats.values()]
        test_cycles = [s.get("cycles", {}).get("testing", 0) for s in self.ticket_stats.values()]

        summary_rows = [
            {
                "metric": "tickets_arrived",
                "value": self.event_counters.get("arrivals", 0),
                "units": "tickets",
                "description": "Total arrivals scheduled within the simulation horizon",
            },
            {
                "metric": "tickets_closed",
                "value": self.event_counters.get("closures", 0),
                "units": "tickets",
                "description": "Tickets processed to completion",
            },
        ]

        closure_rate = 0.0
        if self.event_counters.get("arrivals"):
            closure_rate = self.event_counters.get("closures", 0) / float(self.event_counters["arrivals"])
        summary_rows.append(
            {
                "metric": "closure_rate",
                "value": closure_rate,
                "units": "fraction",
                "description": "Closed tickets divided by arrivals",
            }
        )

        if all_times:
            summary_rows.extend(
                [
                    {
                        "metric": "mean_time_in_system",
                        "value": float(np.mean(all_times)),
                        "units": "days",
                        "description": "Average arrival-to-closure time",
                    },
                    {
                        "metric": "median_time_in_system",
                        "value": float(np.median(all_times)),
                        "units": "days",
                        "description": "Median arrival-to-closure time",
                    },
                    {
                        "metric": "p95_time_in_system",
                        "value": float(np.percentile(all_times, 95)),
                        "units": "days",
                        "description": "95th percentile of arrival-to-closure time",
                    },
                ]
            )

        if dev_cycles:
            summary_rows.append(
                {
                    "metric": "mean_dev_cycles",
                    "value": float(np.mean(dev_cycles)),
                    "units": "cycles",
                    "description": "Average dev cycles per ticket",
                }
            )
        if review_cycles:
            summary_rows.append(
                {
                    "metric": "mean_review_cycles",
                    "value": float(np.mean(review_cycles)),
                    "units": "cycles",
                    "description": "Average review cycles per ticket",
                }
            )
        if test_cycles:
            summary_rows.append(
                {
                    "metric": "mean_test_cycles",
                    "value": float(np.mean(test_cycles)),
                    "units": "cycles",
                    "description": "Average testing cycles per ticket",
                }
            )

        horizon = max(1e-9, float(self.state.sim_duration))
        for stage in self.stage_names:
            avg_wait = mean(self.queue_wait_records.get(stage, []) or [0.0])
            queue_area = self.queue_tracking.get(stage, {}).get("area", 0.0)
            avg_queue_len = queue_area / horizon
            queue_description = (
                "Time-weighted average backlog length (dev queue)" if stage == "dev" else f"Time-weighted average queue length for {stage}"
            )
            if stage == "dev":
                capacity_time = self.developer_state_time.get("DEV", 0.0)
            elif stage == "review":
                capacity_time = self.developer_state_time.get("REV", 0.0)
            else:
                capacity_time = self.developer_state_time.get("TEST", 0.0)

            busy_time = self.service_busy_time.get(stage, 0.0)
            utilization = 0.0
            if capacity_time > 0:
                utilization = busy_time / capacity_time
                tolerance = 1e-9
                if busy_time - capacity_time > tolerance:
                    raise ValueError(
                        f"Utilization exceeds capacity for {stage}: busy_time={busy_time}, capacity_time={capacity_time}, horizon={horizon}"
                    )
            throughput = self.stage_throughput.get(stage, 0) / horizon
            summary_rows.extend(
                [
                    {
                        "metric": f"throughput_{stage}",
                        "value": throughput,
                        "units": "tickets/day",
                        "description": f"Completed {stage} services per day",
                    },
                    {
                        "metric": f"avg_wait_{stage}",
                        "value": avg_wait,
                        "units": "days",
                        "description": f"Average queue wait before {stage} service",
                    },
                    {
                        "metric": f"avg_queue_length_{stage}",
                        "value": avg_queue_len,
                        "units": "tickets",
                        "description": queue_description,
                    },
                    {
                        "metric": f"utilization_{stage}",
                        "value": utilization,
                        "units": "fraction",
                        "description": f"Server utilization for {stage}",
                    },
                ]
            )

        for stage in self.stage_names:
            completions = self.event_counters["service_completions"].get(stage, 0)
            feedbacks = self.event_counters["feedback"].get(stage, 0)
            rework_rate = feedbacks / completions if completions else 0.0
            summary_rows.append(
                {
                    "metric": f"rework_rate_{stage}",
                    "value": rework_rate,
                    "units": "fraction",
                    "description": f"Feedback loops per completion for {stage}",
                }
            )

        summary_rows.append(
            {
                "metric": "markov_time_in_states",
                "value": self.developer_state_time,
                "units": "days",
                "description": "Aggregate time spent by all agents in each developer state",
            }
        )
        stint_counts = {state: len(values) for state, values in self.developer_stints.items()}
        stint_means = {
            state: (float(np.mean(values)) if values else 0.0) for state, values in self.developer_stints.items()
        }
        summary_rows.append(
            {
                "metric": "markov_stint_counts",
                "value": stint_counts,
                "units": "count",
                "description": "Number of stints observed per developer state during the run",
            }
        )
        summary_rows.append(
            {
                "metric": "markov_stint_means",
                "value": stint_means,
                "units": "days",
                "description": "Mean stint length per developer state (simulated)",
            }
        )

        return summary_rows

    def _write_summary_csv(self, summary_rows: List[Dict[str, Any]]) -> None:
        fieldnames = ["metric", "value", "units", "description"]
        with open(self.summary_csvfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in summary_rows:
                writer.writerow(row)
        logging.info("Summary statistics written to %s", self.summary_csvfile)

    # ------------------------------------------------------------------
    # Public report hook
    # ------------------------------------------------------------------
    def final_report(self) -> None:
        """Write per-ticket and summary CSVs, then log a concise summary."""
        self._write_ticket_csv()
        summary_rows = self._aggregate_summary()
        self._write_summary_csv(summary_rows)

        logging.info("------ SIMULATION SUMMARY ------")
        logging.info("Closed tickets: %s", self.event_counters.get("closures", 0))
        if summary_rows:
            for row in summary_rows:
                if row.get("metric") in {"throughput_dev", "throughput_review", "throughput_testing", "closure_rate"}:
                    logging.info("%s = %s %s", row["metric"], row["value"], row["units"])

        print("------ SIMULATION SUMMARY ------")
        print(f"Closed tickets: {self.event_counters.get('closures', 0)}")
        if summary_rows:
            for row in summary_rows:
                if row.get("metric") in {"throughput_dev", "throughput_review", "throughput_testing", "closure_rate"}:
                    print(f"{row['metric']}: {row['value']} {row['units']}")

        logging.info("Per-ticket CSV available at %s", self.ticket_csvfile)
        logging.info("Summary CSV available at %s", self.summary_csvfile)
        print(f"Per-ticket CSV: {self.ticket_csvfile}")
        print(f"Summary CSV: {self.summary_csvfile}")

    # ------------------------------------------------------------------
    # Developer policy tracking
    # ------------------------------------------------------------------
    def log_developer_state_time(self, state: str, delta: float) -> None:
        self.developer_state_time[state] = self.developer_state_time.get(state, 0.0) + delta
        logging.info("Developer pool accrued %.4f days in state %s", delta, state)

    def log_developer_stint(self, state: str, length: float) -> None:
        self.developer_stints.setdefault(state, []).append(length)
        logging.info("Developer stint sampled for %s: %.4f days", state, length)

