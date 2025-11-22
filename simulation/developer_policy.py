# v2
# file: simulation/developer_policy.py

"""
Semi-Markov developer policy module for the BookKeeper DES.

Loads the transition matrix and stint-length PMFs, manages developer agents,
tracks state-time diagnostics, and exposes a calibration harness to validate
occupancy and productive hours.
"""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .config import (
    CHURN_WEIGHT_ADD,
    CHURN_WEIGHT_DEL,
    CHURN_WEIGHT_MOD,
    STATE_PARAMETER_PATHS,
    STATE_TRANSITION_STREAM_SEED,
)

STATES = ["OFF", "DEV", "REV", "TEST"]
STATE_TO_STAGE = {"DEV": "dev", "REV": "review", "TEST": "testing"}


@dataclass
class DeveloperAgent:
    """Represents a single developer following the semi-Markov policy."""

    agent_id: int
    current_state: str
    remaining_stint: float
    busy: bool = False


class DeveloperPool:
    """Manages developer state transitions and capacity exposure."""

    def __init__(self, matrix_path: str, stint_paths: Dict[str, str]):
        self.matrix_path = matrix_path
        self.stint_paths = stint_paths
        self.transition_matrix = self._load_transition_matrix(matrix_path)
        self.stint_pmfs = self._load_stint_pmfs(stint_paths)
        self.agents: Dict[int, DeveloperAgent] = {}
        self.last_update_time: float = 0.0
        self.state_time: Dict[str, float] = {state: 0.0 for state in STATES}
        self.stint_samples: Dict[str, List[float]] = {state: [] for state in STATES}
        self.rng = np.random.default_rng(STATE_TRANSITION_STREAM_SEED)

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    def _load_transition_matrix(self, path: str) -> np.ndarray:
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Transition matrix not found at {path}. Confirm data/state_parameters/matrix_P.csv is available.")
        logging.info("Loading transition matrix P from %s", path)
        rows: List[List[float]] = []
        with open(path, "r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row or row[0].startswith("#"):
                    continue
                if row[0].upper() == "":
                    continue
                if row[0].upper() == "OFF":
                    rows.append([float(x) for x in row[1:]])
                elif row[0].upper() in {"DEV", "REV", "TEST"}:
                    rows.append([float(x) for x in row[1:]])
        matrix = np.array(rows, dtype=float)
        if matrix.shape != (4, 4):
            raise ValueError(
                f"Transition matrix P must be 4x4 for states {STATES}; found shape {matrix.shape} from {path}.")
        logging.info("Loaded transition matrix with shape %s", matrix.shape)
        return matrix

    def _load_stint_pmfs(self, stint_paths: Dict[str, str]) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        pmfs: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        for state, path in stint_paths.items():
            if not os.path.isfile(path):
                raise FileNotFoundError(
                    f"Stint PMF for {state} not found at {path}. Ensure data/state_parameters/stint_PMF_{state}.csv exists.")
            logging.info("Loading stint PMF for %s from %s", state, path)
            lengths: List[float] = []
            probs: List[float] = []
            with open(path, "r", encoding="utf-8") as handle:
                reader = csv.DictReader(filter(lambda line: not line.startswith("#"), handle))
                for row in reader:
                    try:
                        lengths.append(float(row["length"]))
                        probs.append(float(row["prob"]))
                    except (KeyError, TypeError, ValueError) as exc:  # noqa: PERF203 - explicit parsing safety
                        raise ValueError(f"Invalid stint PMF row in {path}: {row}") from exc
            if not lengths or not probs:
                raise ValueError(f"Empty stint PMF for {state} loaded from {path}")
            pmfs[state] = (np.array(lengths, dtype=float), np.array(probs, dtype=float))
            logging.info("Loaded %d stint entries for %s", len(lengths), state)
        return pmfs

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------
    def initialize_agents(self, total_agents: int, stats=None) -> None:
        logging.info("Initializing %d developer agents from stationary distribution.", total_agents)
        stationary = self.stationary_distribution()
        logging.info("Stationary distribution estimate: %s", stationary)
        for idx in range(total_agents):
            state = str(self.rng.choice(STATES, p=stationary))
            stint = self._draw_stint(state)
            self.agents[idx] = DeveloperAgent(agent_id=idx, current_state=state, remaining_stint=stint)
            self._record_stint(state, stint, stats)
        self.last_update_time = 0.0
        logging.info("Developer pool ready with counts: %s", self._counts_by_state())

    def stationary_distribution(self) -> np.ndarray:
        eigvals, eigvecs = np.linalg.eig(self.transition_matrix.T)
        stat_idx = np.argmin(np.abs(eigvals - 1.0))
        stationary = np.real(eigvecs[:, stat_idx])
        stationary = stationary / stationary.sum()
        if (stationary < 0).any():
            stationary = np.abs(stationary)
            stationary = stationary / stationary.sum()
        return stationary

    # ------------------------------------------------------------------
    # Capacity helpers
    # ------------------------------------------------------------------
    def current_capacity_by_stage(self) -> Dict[str, int]:
        counts = self._counts_by_state()
        return {"DEV": counts.get("DEV", 0), "REV": counts.get("REV", 0), "TEST": counts.get("TEST", 0)}

    def available_agent_for_stage(self, stage: str) -> Optional[DeveloperAgent]:
        target_states = [state for state, mapped_stage in STATE_TO_STAGE.items() if mapped_stage == stage]
        for agent in self.agents.values():
            if agent.current_state in target_states and not agent.busy and agent.remaining_stint > 0:
                return agent
        return None

    # ------------------------------------------------------------------
    # Time advancement and transitions
    # ------------------------------------------------------------------
    def advance_time(self, current_time: float, stats=None) -> set[str]:
        delta = max(0.0, current_time - self.last_update_time)
        if delta <= 0:
            return set()
        changed_stages: set[str] = set()
        for agent in self.agents.values():
            if agent.busy:
                continue
            agent.remaining_stint -= delta
            self._record_state_time(agent.current_state, delta, stats)
            if agent.remaining_stint <= 0:
                changed_stages.update(self._transition_agent(agent, current_time, stats))
        self.last_update_time = current_time
        return changed_stages

    def on_service_completion(self, agent_id: int, stage: str, service_time: float, event_time: float, stats=None) -> set[str]:
        agent = self.agents.get(agent_id)
        if agent is None:
            logging.error("Unknown agent %s at completion of %s.", agent_id, stage)
            return set()
        agent.busy = False
        agent.remaining_stint -= service_time
        self._record_state_time(agent.current_state, service_time, stats)
        changed_stages: set[str] = set()
        if agent.remaining_stint <= 0:
            changed_stages = self._transition_agent(agent, event_time, stats)
        return changed_stages

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _transition_agent(self, agent: DeveloperAgent, event_time: float, stats=None) -> set[str]:
        current_idx = STATES.index(agent.current_state)
        probs = self.transition_matrix[current_idx]
        next_state = str(self.rng.choice(STATES, p=probs))
        old_stage = STATE_TO_STAGE.get(agent.current_state)
        agent.current_state = next_state
        agent.remaining_stint = self._draw_stint(next_state)
        self._record_stint(next_state, agent.remaining_stint, stats)
        logging.info(
            "Agent %s transitioned %s→%s at t=%.2f; new stint %.4f days.",
            agent.agent_id,
            STATES[current_idx],
            next_state,
            event_time,
            agent.remaining_stint,
        )
        new_stage = STATE_TO_STAGE.get(next_state)
        changed = set()
        if old_stage:
            changed.add(old_stage)
        if new_stage:
            changed.add(new_stage)
        return changed

    def _draw_stint(self, state: str) -> float:
        pmf = self.stint_pmfs.get(state)
        if pmf is None:
            raise ValueError(f"No stint PMF loaded for state {state}.")
        lengths, probs = pmf
        stint = float(self.rng.choice(lengths, p=probs))
        if stint <= 0:
            stint = 1e-6
        return stint

    def _counts_by_state(self) -> Dict[str, int]:
        counts: Dict[str, int] = {state: 0 for state in STATES}
        for agent in self.agents.values():
            counts[agent.current_state] = counts.get(agent.current_state, 0) + 1
        return counts

    def _record_state_time(self, state: str, delta: float, stats=None) -> None:
        self.state_time[state] = self.state_time.get(state, 0.0) + delta
        if stats is not None:
            stats.log_developer_state_time(state, delta)

    def _record_stint(self, state: str, stint: float, stats=None) -> None:
        self.stint_samples[state].append(stint)
        if stats is not None:
            stats.log_developer_stint(state, stint)


# ----------------------------------------------------------------------
# Churn-weighted allocator
# ----------------------------------------------------------------------
def churn_weight(ticket) -> Optional[float]:
    if ticket is None:
        return None
    adds = getattr(ticket, "churn_add", None)
    mods = getattr(ticket, "churn_mod", None)
    dels = getattr(ticket, "churn_del", None)
    if adds is None and mods is None and dels is None:
        return None
    adds = float(adds or 0.0)
    mods = float(mods or 0.0)
    dels = float(dels or 0.0)
    weight = (adds * CHURN_WEIGHT_ADD) + (mods * CHURN_WEIGHT_MOD) + (dels * CHURN_WEIGHT_DEL)
    return max(weight, 0.0)


def select_with_churn(queue: Iterable[Tuple[object, float]]) -> Optional[Tuple[object, float, int]]:
    items = list(queue)
    if not items:
        return None
    weights: List[float] = []
    for ticket, _ in items:
        w = churn_weight(ticket)
        if w is None:
            logging.debug("Churn metadata missing for ticket %s; reverting to FIFO.", getattr(ticket, "ticket_id", "?"))
            return (items[0][0], items[0][1], 0)
        weights.append(w)
    total = sum(weights)
    if total <= 0:
        return (items[0][0], items[0][1], 0)
    probs = [w / total for w in weights]
    idx = int(np.random.choice(len(items), p=probs))
    return items[idx][0], items[idx][1], idx


# ----------------------------------------------------------------------
# Calibration harness
# ----------------------------------------------------------------------
def run_calibration(sim_days: float = 60.0, total_agents: int = 44) -> None:
    """Simulate the developer process alone to report occupancy and productivity."""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "developer_policy.log"), mode="w"),
            logging.StreamHandler(),
        ],
    )
    matrix_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", STATE_PARAMETER_PATHS["matrix_P"]))
    stint_paths = {
        "OFF": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", STATE_PARAMETER_PATHS["stint_pmfs"][1])),
        "DEV": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", STATE_PARAMETER_PATHS["stint_pmfs"][0])),
        "REV": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", STATE_PARAMETER_PATHS["stint_pmfs"][2])),
        "TEST": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", STATE_PARAMETER_PATHS["stint_pmfs"][3])),
    }
    pool = DeveloperPool(matrix_path, stint_paths)
    pool.initialize_agents(total_agents)

    current_time = 0.0
    while current_time < sim_days:
        next_stint_end = min(agent.remaining_stint for agent in pool.agents.values())
        step = max(1e-3, min(next_stint_end, sim_days - current_time))
        current_time += step
        pool.advance_time(current_time)
        for agent in pool.agents.values():
            if not agent.busy and agent.remaining_stint <= 0:
                pool._transition_agent(agent, current_time)

    counts = pool._counts_by_state()
    occupancy = {state: pool.state_time[state] / (sim_days * total_agents) for state in STATES}
    productive_time = pool.state_time.get("DEV", 0.0) + pool.state_time.get("REV", 0.0) + pool.state_time.get("TEST", 0.0)
    avg_productive_hours = (productive_time / max(total_agents, 1)) * 24.0 / max(sim_days, 1e-6)

    stationary = pool.stationary_distribution()
    logging.info("Calibration complete over %.1f days with %d agents.", sim_days, total_agents)
    logging.info("Empirical occupancy: %s", occupancy)
    logging.info("Stationary distribution from P: %s", stationary)
    logging.info("Average productive hours/agent/day: %.2f", avg_productive_hours)
    print("Calibration summary")
    print(f"Occupancy (empirical): {occupancy}")
    print(f"Stationary from P: {stationary}")
    print(f"Average productive hours/agent/day: {avg_productive_hours:.2f}")


if __name__ == "__main__":
    run_calibration()
