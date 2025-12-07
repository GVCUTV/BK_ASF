# v1
# file: simulation/run_sweeps.py

"""
Parameter sweep runner for Meeting Step 5.2 B.

Reads a sweep specification (CSV/JSON-style via CSV with optional comment lines),
executes simulations with per-row overrides, and persists outputs into
experiment-specific folders. Each experiment is isolated under the provided
output base (default ``experiments/5_2B``), and an aggregate CSV can be
produced for quick analysis. Example usage:

    python -m simulation.run_sweeps --spec simulation/sweeps/5_2B_sweeps.csv
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_SPEC_PATH = os.path.join("sweeps", "5_2B_sweeps.csv")
DEFAULT_OUTDIR = os.path.join("experiments", "5_2B")
SUMMARY_FILENAME = "summary_stats.csv"
TICKETS_FILENAME = "tickets_stats.csv"
CONFIG_FILENAME = "config_used.json"
AGGREGATE_FILENAME = "aggregate_summary.csv"
LOG_FILENAME = "sweep.log"

SPEC_KEY_MAP = {
    "arrival_rate": "ARRIVAL_RATE",
    "feedback_dev": "FEEDBACK_P_DEV",
    "feedback_test": "FEEDBACK_P_TEST",
    "global_seed": "GLOBAL_RANDOM_SEED",
    "sim_duration": "SIM_DURATION",
}

SUMMARY_METRICS = [
    "closure_rate",
    "throughput_dev",
    "throughput_review",
    "throughput_testing",
    "avg_wait_dev",
    "avg_wait_review",
    "avg_wait_testing",
    "avg_queue_length_dev",
    "avg_queue_length_review",
    "avg_queue_length_testing",
    "utilization_dev",
    "utilization_review",
    "utilization_testing",
    "markov_time_in_states",
    "markov_stint_means",
    "markov_stint_counts",
]


@dataclass
class SweepExperiment:
    """Container for a single experiment specification."""

    experiment_id: str
    parameters: Dict[str, Any]
    spec_values: Dict[str, Any]


def configure_logging(base_outdir: str) -> None:
    """Configure stdout and file logging for sweep execution."""
    os.makedirs(base_outdir, exist_ok=True)
    logfile = os.path.join(base_outdir, LOG_FILENAME)
    handlers: List[logging.Handler] = [
        logging.FileHandler(logfile, mode="w"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("Sweep logging initialized. Output dir: %s", base_outdir)


def parse_value(raw: str) -> Any:
    """Convert CSV string fields into Python literals when possible."""
    text = raw.strip()
    if text == "":
        return None
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def _iter_non_comment_lines(filepath: str) -> Iterable[str]:
    with open(filepath, "r", newline="") as handle:
        for line in handle:
            if line.lstrip().startswith("#"):
                continue
            if line.strip() == "":
                continue
            yield line


def load_sweep_spec(filepath: str) -> Tuple[List[SweepExperiment], List[str]]:
    """Load sweep experiments from a CSV specification file."""
    experiments: List[SweepExperiment] = []
    reader = csv.DictReader(_iter_non_comment_lines(filepath))
    if reader.fieldnames is None:
        raise ValueError(f"Spec file {filepath} is missing headers.")
    param_columns = [field for field in reader.fieldnames if field != "experiment_id"]
    for row in reader:
        experiment_id = (row.get("experiment_id") or "").strip()
        if not experiment_id:
            logging.warning("Skipping unnamed experiment row: %s", row)
            continue
        raw_params = {key: row.get(key, "") for key in param_columns}
        spec_values: Dict[str, Any] = {}
        overrides: Dict[str, Any] = {}
        for key, raw_val in raw_params.items():
            value = parse_value(raw_val)
            if value is None:
                continue
            spec_values[key] = value
            config_key = SPEC_KEY_MAP.get(key, key.upper())
            overrides[config_key] = value
        experiments.append(SweepExperiment(experiment_id, overrides, spec_values))
    return experiments, param_columns


def apply_config_overrides(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Reload config and apply overrides so dependent modules see updates."""
    from simulation import config as sim_config
    from simulation import developer_policy
    from simulation import workflow_logic
    from simulation import simulate

    importlib.reload(sim_config)
    applied = sim_config.apply_overrides(overrides)
    importlib.reload(developer_policy)
    importlib.reload(workflow_logic)
    importlib.reload(simulate)
    return applied


def run_single_experiment(exp: SweepExperiment, base_outdir: str) -> bool:
    """Execute one experiment and persist outputs. Returns success status."""
    logging.info("\n--- Running experiment %s ---", exp.experiment_id)
    experiment_dir = os.path.join(base_outdir, exp.experiment_id)
    os.makedirs(experiment_dir, exist_ok=True)

    applied = apply_config_overrides(exp.parameters)
    logging.info("Applied overrides for %s: %s", exp.experiment_id, applied)

    from simulation import config as sim_config
    from simulation import simulate

    try:
        simulate.main()
    except Exception as exc:  # noqa: BLE001 - explicit logging and continuation required
        logging.exception("Experiment %s failed: %s", exp.experiment_id, exc)
        return False

    persist_outputs(sim_config, experiment_dir)
    logging.info("Completed experiment %s", exp.experiment_id)
    return True


def persist_outputs(sim_config: Any, experiment_dir: str) -> None:
    """Copy run outputs into an experiment-specific folder."""
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    summary_src = os.path.join(output_dir, SUMMARY_FILENAME)
    tickets_src = os.path.join(output_dir, TICKETS_FILENAME)
    log_src = os.path.join(os.path.dirname(__file__), "logs", "simulation.log")

    for src, name in [
        (summary_src, SUMMARY_FILENAME),
        (tickets_src, TICKETS_FILENAME),
        (log_src, "run.log"),
    ]:
        if not os.path.isfile(src):
            logging.warning("Expected output %s not found; skipping copy.", src)
            continue
        dest = os.path.join(experiment_dir, name)
        shutil.copy2(src, dest)
        logging.info("Copied %s -> %s", src, dest)

    config_snapshot = sim_config.current_config()
    config_path = os.path.join(experiment_dir, CONFIG_FILENAME)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(config_snapshot, handle, indent=2, sort_keys=True)
    logging.info("Wrote config snapshot to %s", config_path)


def read_summary_metrics(summary_path: str) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    with open(summary_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            metric = row.get("metric")
            value = row.get("value", "")
            if metric:
                metrics[metric] = parse_value(value)
    return metrics


def build_aggregate(
    experiments: List[SweepExperiment],
    param_columns: List[str],
    base_outdir: str,
) -> None:
    """Combine per-experiment parameters and metrics into one CSV."""
    aggregate_rows: List[Dict[str, Any]] = []
    for exp in experiments:
        summary_path = os.path.join(base_outdir, exp.experiment_id, SUMMARY_FILENAME)
        if not os.path.isfile(summary_path):
            logging.warning("No summary for %s; skipping aggregation.", exp.experiment_id)
            continue
        metrics = read_summary_metrics(summary_path)
        row: Dict[str, Any] = {"experiment_id": exp.experiment_id}
        for col in param_columns:
            row[col] = exp.spec_values.get(col)
        for metric in SUMMARY_METRICS:
            row[metric] = metrics.get(metric)
        aggregate_rows.append(row)

    if not aggregate_rows:
        logging.warning("No experiments produced summaries; aggregate not written.")
        return

    aggregate_path = os.path.join(base_outdir, AGGREGATE_FILENAME)
    fieldnames = ["experiment_id", *param_columns, *SUMMARY_METRICS]
    with open(aggregate_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(aggregate_rows)
    logging.info("Aggregate summary written to %s", aggregate_path)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run simulation parameter sweeps.")
    parser.add_argument("--spec", default=DEFAULT_SPEC_PATH, help="Path to sweep spec CSV.")
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR, help="Base output directory.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Optional limit on number of experiments to run."
    )
    parser.add_argument(
        "--skip-aggregate",
        action="store_true",
        help="Skip writing aggregate summary even if runs succeed.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(args.outdir)

    logging.info("Loading sweep spec from %s", args.spec)
    experiments, param_columns = load_sweep_spec(args.spec)
    if args.limit is not None:
        experiments = experiments[: args.limit]
        logging.info("Limiting to first %d experiments", args.limit)

    completed: List[SweepExperiment] = []
    for exp in experiments:
        success = run_single_experiment(exp, args.outdir)
        if success:
            completed.append(exp)

    logging.info("Completed %d/%d experiments", len(completed), len(experiments))
    if not args.skip_aggregate:
        build_aggregate(completed, param_columns, args.outdir)


if __name__ == "__main__":
    main()
