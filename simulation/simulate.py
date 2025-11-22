# v4
# file: simulation/simulate.py

"""
Main entry point for the BookKeeper workflow event-driven simulation.
Initializes logging, wires together the DES components, and runs until
no more events remain or the horizon is exceeded.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from datetime import datetime

import numpy as np

if __package__ is None or __package__ == "":  # pragma: no cover - runtime path fix
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulation.config import (  # type: ignore
    ARRIVAL_RATE,
    GLOBAL_RANDOM_SEED,
    LOG_FILE,
    N_DEVS,
    N_TESTERS,
    SEED_OVERRIDE_ENV_VAR,
    SIM_DURATION,
    STATE_PARAMETER_PATHS,
)
from simulation.entities import SystemState  # type: ignore
from simulation.events import EventQueue  # type: ignore
from simulation.stats import StatsCollector  # type: ignore

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _configure_logging():
    log_dir = os.path.dirname(LOG_FILE) or "."
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("Simulation logging initialized at %s", datetime.now().isoformat())


def _resolve_repo_path(rel_or_abs: str) -> str:
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.abspath(os.path.join(PROJECT_ROOT, rel_or_abs))


def _validate_state_inputs() -> None:
    matrix_path = STATE_PARAMETER_PATHS.get("matrix_P")
    service_params_path = STATE_PARAMETER_PATHS.get("service_params")
    stint_paths = STATE_PARAMETER_PATHS.get("stint_pmfs", [])

    required = [
        ("matrix_P", matrix_path),
        ("service_params", service_params_path),
    ]
    for idx, entry in enumerate(stint_paths):
        required.append((f"stint_pmfs[{idx}]", entry))

    missing = []
    for label, rel_path in required:
        if not rel_path:
            missing.append((label, "<undefined>"))
            continue
        abs_path = _resolve_repo_path(rel_path)
        if not os.path.isfile(abs_path):
            missing.append((label, abs_path))
        else:
            logging.info("Confirmed %s at %s", label, abs_path)

    if missing:
        for label, abs_path in missing:
            logging.error("Missing state parameter %s (expected at %s)", label, abs_path)
        raise FileNotFoundError("Required state parameter inputs are missing; aborting simulation startup.")

    logging.info(
        "State parameter verification complete: 1 matrix file, 1 service param JSON, %d stint PMFs.",
        len(stint_paths),
    )


def _initialize_random_seed():
    env_var = SEED_OVERRIDE_ENV_VAR or ""
    override_val = os.environ.get(env_var) if env_var else None
    seed = GLOBAL_RANDOM_SEED
    override_source = None

    if override_val is not None:
        try:
            seed = int(override_val)
            override_source = env_var
        except ValueError:
            logging.warning(
                "Env override %s=%r is not an integer; falling back to default seed %d.",
                env_var,
                override_val,
                seed,
            )

    random.seed(seed)
    np.random.seed(seed)
    logging.info(
        "Random generators initialized with seed %d (override source: %s).",
        seed,
        override_source or "config",
    )
    return seed, override_source


def _log_config_summary(seed: int, override_source: str | None) -> None:
    logging.info(
        "Simulation configuration — duration=%.2f days, λ=%.6f/day, N_DEVS=%d, N_TESTERS=%d",
        SIM_DURATION,
        ARRIVAL_RATE,
        N_DEVS,
        N_TESTERS,
    )
    if override_source:
        logging.info("Random seed %d provided via %s", seed, override_source)
    else:
        logging.info("Random seed %d from config (env var %s can override).", seed, SEED_OVERRIDE_ENV_VAR)


def main():
    _configure_logging()
    _validate_state_inputs()
    seed, override_source = _initialize_random_seed()
    _log_config_summary(seed, override_source)

    state = SystemState()
    state.sim_duration = SIM_DURATION
    stats = StatsCollector(state)

    event_queue = EventQueue()
    event_queue.schedule_initial_arrivals(state, stats)

    logging.info("Starting simulation loop. Target horizon: %.2f", SIM_DURATION)
    while not event_queue.empty():
        next_time = event_queue.next_event_time()
        if next_time > SIM_DURATION:
            logging.info("Next event occurs at %.2f beyond horizon; exiting loop.", next_time)
            break
        event = event_queue.pop()
        logging.info("Processing event: %s", event)
        try:
            event.process(event_queue, state, stats)
        except Exception as exc:  # noqa: BLE001 - explicit logging required
            logging.exception("Error while processing %s: %s", event, exc)
            break

    stats.final_report()
    logging.info("Simulation complete.")


if __name__ == "__main__":
    main()
