# v3.2A-001
# file: simulation/state_equations.py
"""Compute state transition matrix, stint-length PMFs, and service time fits."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from path_config import PROJECT_ROOT

STATES = ["OFF", "DEV", "REV", "TEST"]
STAGE_COLUMNS = {
    "DEV": ("dev_start_ts", "dev_end_ts"),
    "REV": ("review_start_ts", "review_end_ts"),
    "TEST": ("test_start_ts", "test_end_ts"),
}
LOG_PATH = Path("output/logs/state_equations.log")
DATA_DIR = Path("data/state_parameters")
ETL_DATA = Path("etl/output/csv/tickets_prs_merged.csv")
PRECISION = 3


def setup_logging() -> None:
    """Configure logging to stdout and file for reproducibility."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handlers = []

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handlers.append(stream_handler)

    file_handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handlers.append(file_handler)

    root = logging.getLogger()
    root.handlers[:] = []
    root.setLevel(logging.INFO)
    for handler in handlers:
        root.addHandler(handler)
    logging.info("Logging initialized. Project root: %s", PROJECT_ROOT)


def load_developer_events(etl_path: Path) -> pd.DataFrame:
    """Load ETL output with developer-stage timestamps."""
    logging.info("Loading developer stage data from %s", etl_path)
    df = pd.read_csv(etl_path)
    if "dev_user" not in df.columns:
        raise ValueError("Expected 'dev_user' column in ETL dataset.")
    usable = df.dropna(subset=["dev_user"]).copy()
    logging.info("Loaded %d records with developer assignments.", len(usable))
    return usable


def parse_event_times(df: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    """Convert timestamp columns into chronological events per developer."""
    events_by_dev: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]] = defaultdict(list)
    for state, (start_col, end_col) in STAGE_COLUMNS.items():
        for _, row in df.iterrows():
            dev = row["dev_user"]
            if pd.isna(dev):
                continue
            start = row.get(start_col)
            end = row.get(end_col)
            if pd.isna(start) or pd.isna(end):
                continue
            start_ts = pd.to_datetime(start, utc=True, errors="coerce")
            end_ts = pd.to_datetime(end, utc=True, errors="coerce")
            if pd.isna(start_ts) or pd.isna(end_ts):
                continue
            if end_ts <= start_ts:
                continue
            events_by_dev[str(dev)].append((start_ts.tz_convert(None), end_ts.tz_convert(None), state))
    logging.info("Parsed events for %d developers.", len(events_by_dev))
    return events_by_dev


def compute_transition_counts(events_by_dev: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]) -> tuple[np.ndarray, dict[str, list[float]]]:
    """Compute empirical transition counts and stint durations."""
    transition_counts = np.zeros((len(STATES), len(STATES)), dtype=float)
    stints: dict[str, list[float]] = {state: [] for state in STATES}

    for dev, events in events_by_dev.items():
        events.sort(key=lambda e: e[0])
        last_state = "OFF"
        last_end = None
        for start, end, state in events:
            if last_end is None:
                transition_counts[STATES.index("OFF"), STATES.index(state)] += 1
            else:
                idle_days = (start - last_end).total_seconds() / 86400.0
                if idle_days > 0:
                    transition_counts[STATES.index(last_state), STATES.index("OFF")] += 1
                    stints["OFF"].append(idle_days)
                    transition_counts[STATES.index("OFF"), STATES.index(state)] += 1
                else:
                    transition_counts[STATES.index(last_state), STATES.index(state)] += 1
            duration_days = (end - start).total_seconds() / 86400.0
            if duration_days > 0:
                stints[state].append(duration_days)
            last_state = state
            last_end = end
        if last_state != "OFF":
            transition_counts[STATES.index(last_state), STATES.index("OFF")] += 1
    logging.info("Computed transition counts with shape %s", transition_counts.shape)
    return transition_counts, stints


def compute_transition_matrix(counts: np.ndarray, alpha: float = 1.0) -> pd.DataFrame:
    """Compute Laplace-smoothed transition matrix P where P_ij = (n_ij + α) / Σ_j (n_i· + α)."""
    smoothed = counts + alpha
    row_sums = smoothed.sum(axis=1, keepdims=True)
    probabilities = smoothed / row_sums
    matrix = pd.DataFrame(probabilities, index=STATES, columns=STATES)
    logging.info("Transition matrix derived with Laplace smoothing α=%.2f", alpha)
    return matrix


def compute_stint_pmfs(stints: dict[str, list[float]], precision: int = PRECISION) -> dict[str, pd.DataFrame]:
    """Derive empirical stint-length PMF f_i(ℓ) by rounding lengths to the given precision."""
    pmfs: dict[str, pd.DataFrame] = {}
    for state, durations in stints.items():
        arr = np.array(durations, dtype=float)
        arr = arr[np.isfinite(arr) & (arr > 0)]
        if arr.size == 0:
            pmfs[state] = pd.DataFrame(columns=["length", "prob"])
            continue
        rounded = np.round(arr, precision)
        unique, counts = np.unique(rounded, return_counts=True)
        probs = counts / counts.sum()
        pmfs[state] = pd.DataFrame({"length": unique, "prob": probs})
        logging.info("State %s: computed PMF over %d unique stint lengths.", state, len(unique))
    return pmfs


def fit_service_times(stints: dict[str, list[float]]) -> dict:
    """Fit log-normal service-time distributions T_s for DEV/REV/TEST states."""
    params = {}
    for state in ["DEV", "REV", "TEST"]:
        arr = np.array(stints[state], dtype=float)
        arr = arr[np.isfinite(arr) & (arr > 0)]
        if arr.size == 0:
            logging.warning("No data available to fit service time for %s", state)
            params[state] = {"distribution": "lognormal", "mu": None, "sigma": None, "n": 0}
            continue
        shape, loc, scale = stats.lognorm.fit(arr, floc=0)
        mu = float(np.log(scale))
        sigma = float(shape)
        params[state] = {"distribution": "lognormal", "mu": mu, "sigma": sigma, "n": int(arr.size)}
        logging.info("Fitted lognormal for %s with mu=%.6f sigma=%.6f n=%d", state, mu, sigma, arr.size)
    return params


def save_matrix(matrix: pd.DataFrame, path: Path) -> None:
    """Persist transition matrix with version header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("# v3.2A-001\n")
        f.write(f"# file: {path.as_posix()}\n")
        matrix.to_csv(f)
    logging.info("Saved transition matrix to %s", path)


def save_pmfs(pmfs: dict[str, pd.DataFrame], directory: Path) -> None:
    """Persist state stint PMFs with version headers."""
    directory.mkdir(parents=True, exist_ok=True)
    for state, df in pmfs.items():
        path = directory / f"stint_PMF_{state}.csv"
        with path.open("w", encoding="utf-8") as f:
            f.write("# v3.2A-001\n")
            f.write(f"# file: {path.as_posix()}\n")
            df.to_csv(f, index=False)
        logging.info("Saved PMF for %s to %s", state, path)


def save_service_params(params: dict, path: Path) -> None:
    """Persist fitted service-time parameters."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": "v3.2A-001", "parameters": params}
    with path.open("w", encoding="utf-8") as f:
        f.write("// v3.2A-001\n")
        f.write(f"// file: {path.as_posix()}\n")
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    logging.info("Saved service-time parameters to %s", path)


def validate_transitions(real, sim):
    """Placeholder for χ² goodness-of-fit between observed and simulated transition counts."""
    raise NotImplementedError("Validation stub to compare empirical vs. simulated transitions.")


def validate_stint(real, sim):
    """Placeholder for Kolmogorov-Smirnov test between observed and simulated stint lengths."""
    raise NotImplementedError("Validation stub to compare empirical vs. simulated stints.")


def main() -> None:
    """Entry point computing P_ij, f_i(ℓ), and T_s then persisting the outputs."""
    setup_logging()
    df = load_developer_events(ETL_DATA)
    events = parse_event_times(df)
    counts, stints = compute_transition_counts(events)
    matrix = compute_transition_matrix(counts)
    pmfs = compute_stint_pmfs(stints)
    service_params = fit_service_times(stints)

    save_matrix(matrix, DATA_DIR / "matrix_P.csv")
    save_pmfs(pmfs, DATA_DIR)
    save_service_params(service_params, DATA_DIR / "service_params.json")

    logging.info("State equation artifacts generated in %s", DATA_DIR)
    print("✅ State equation artifacts generated.")


if __name__ == "__main__":
    main()
# Generated by Codex Meeting 3.2A
