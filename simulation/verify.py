"""Verification CLI for simulation outputs.

This module inspects simulation output artifacts (summary and ticket stats),
performs consistency checks, writes a Markdown report, and exits with a
machine-friendly status code (0 on success, non-zero on failures).

Example:
    python -m simulation.verify --input simulation/output
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from simulation.run_sweeps import SUMMARY_METRICS, parse_value
from validation import checks as validation_checks

SUMMARY_FILENAME = "summary_stats.csv"
TICKETS_FILENAME = "tickets_stats.csv"
REPORT_FILENAME = "verification_report.md"
AGGREGATE_FILENAME = "aggregate_summary.csv"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_PATH = REPO_ROOT / "validation" / "baseline_metrics.csv"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class CheckResult:
    """Represents a single verification check."""

    name: str
    passed: bool
    details: str


@dataclass
class RunReport:
    """Collects the results for a single run or experiment."""

    label: str
    results: List[CheckResult]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)


@dataclass
class StageSamples:
    """Ticket-level samples for a single stage."""

    waits: List[float]
    services: List[float]
    parse_failures: int


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify simulation outputs and generate a report.")
    parser.add_argument(
        "--input",
        default=os.path.join(os.path.dirname(__file__), "output"),
        help="Path to a simulation output directory or sweep root (default: simulation/output).",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing check.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-6,
        help="Tolerance for floating-point comparisons.",
    )
    parser.add_argument(
        "--mean-jobs-rel-tolerance",
        type=float,
        default=0.02,
        help="Relative tolerance for Little mean-jobs identity checks (default: 0.02).",
    )
    parser.add_argument(
        "--baseline-metrics",
        help="Path to validation baseline_metrics.csv to include ETL comparisons in the report.",
    )
    parser.add_argument(
        "--etl-dir",
        help="Path to the ETL directory; used to locate validation/baseline_metrics.csv for ETL comparisons.",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "sweep"],
        default="single",
        help="Verify a single run directory or sweep experiments contained within the input path.",
    )
    parser.add_argument(
        "--sweep",
        dest="mode",
        action="store_const",
        const="sweep",
        help="Alias for --mode sweep.",
    )
    return parser.parse_args(argv)


def _resolve_baseline_path(etl_dir: str | None, baseline_metrics: str | None) -> str | None:
    if baseline_metrics:
        return baseline_metrics
    if not etl_dir:
        return None
    etl_path = Path(etl_dir).resolve()
    candidates = [
        etl_path / "baseline_metrics.csv",
        etl_path.parent / "validation" / "baseline_metrics.csv",
        etl_path.parent.parent / "validation" / "baseline_metrics.csv",
        DEFAULT_BASELINE_PATH,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return str(candidates[-1])


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------
def _ensure_exists(path: str, label: str, results: List[CheckResult]) -> bool:
    if os.path.isfile(path):
        results.append(CheckResult(label, True, f"Found {os.path.basename(path)}."))
        return True
    results.append(CheckResult(label, False, f"Missing required file: {path}"))
    return False


def detect_sweep_experiments(input_dir: str) -> List[str]:
    """Detect sweep experiment directories containing required output files.

    A directory qualifies as an experiment when it is an immediate child of
    ``input_dir`` and contains both ``summary_stats.csv`` and
    ``tickets_stats.csv``.
    """

    if not os.path.isdir(input_dir):
        return []

    experiments: List[str] = []
    for name in sorted(os.listdir(input_dir)):
        candidate = os.path.join(input_dir, name)
        if not os.path.isdir(candidate):
            continue

        summary_path = os.path.join(candidate, SUMMARY_FILENAME)
        tickets_path = os.path.join(candidate, TICKETS_FILENAME)
        if os.path.isfile(summary_path) and os.path.isfile(tickets_path):
            experiments.append(candidate)

    return experiments


def _load_summary(summary_path: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    with open(summary_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            metric = (row.get("metric") or "").strip()
            if not metric:
                continue
            value_raw = row.get("value", "")
            try:
                metrics[metric] = float(value_raw)
            except (TypeError, ValueError):
                # Preserve non-numeric values when present.
                continue
    return metrics


def _load_summary_with_parsing(summary_path: str) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    with open(summary_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            metric = (row.get("metric") or "").strip()
            if not metric:
                continue
            metrics[metric] = parse_value(row.get("value", ""))
    return metrics


def _load_aggregate_summary(aggregate_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    with open(aggregate_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Aggregate file {aggregate_path} is missing headers.")
        rows: List[Dict[str, Any]] = []
        for row in reader:
            parsed = {key: parse_value(value or "") for key, value in row.items()}
            rows.append(parsed)
    return rows, list(reader.fieldnames)


def _load_tickets(tickets_path: str) -> List[Dict[str, str]]:
    with open(tickets_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _load_baseline_rows(baseline_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(baseline_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed = dict(row)
            for key in ["value", "ci_low", "ci_high"]:
                parsed[key] = parse_value(parsed.get(key, ""))
            rows.append(parsed)
    return rows


def _baseline_checks(
    summary_metrics: Dict[str, float],
    ticket_rows: List[Dict[str, str]],
    baseline_rows: Sequence[Dict[str, Any]],
) -> List[CheckResult]:
    baseline_metrics = {
        (row.get("metric") or "").strip(): row.get("value")
        for row in baseline_rows
        if (row.get("metric") or "").strip()
    }
    if not baseline_metrics:
        return []
    ticket_parsed = [{k: parse_value(v or "") for k, v in row.items()} for row in ticket_rows]
    baseline_results = validation_checks.check_baseline(
        summary_metrics,
        baseline_metrics,
        rel_tol=0.1,
        abs_tol=1e-6,
        ticket_rows=ticket_parsed,
    )
    return [CheckResult(result.name, result.passed, result.details) for result in baseline_results]


# ---------------------------------------------------------------------------
# Numeric utilities
# ---------------------------------------------------------------------------
def _approx_equal(a: float, b: float, tolerance: float) -> bool:
    scale = max(1.0, abs(a), abs(b))
    return abs(a - b) <= tolerance * scale


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Check routines
# ---------------------------------------------------------------------------
def _required_metrics_check(summary_metrics: Dict[str, float], required: Iterable[str], tolerance: float) -> CheckResult:
    missing = [metric for metric in required if metric not in summary_metrics]
    if missing:
        return CheckResult(
            "Required summary metrics present",
            False,
            f"Missing metrics: {', '.join(sorted(missing))}",
        )
    return CheckResult(
        "Required summary metrics present",
        True,
        f"Found all required metrics: {', '.join(sorted(required))}",
    )


def _arrival_count_check(arrivals_reported: float, ticket_rows: int, tolerance: float) -> CheckResult:
    if _approx_equal(arrivals_reported, ticket_rows, tolerance):
        return CheckResult(
            "Tickets arrived count",
            True,
            f"summary_stats.csv reports {arrivals_reported}, tickets_stats.csv contains {ticket_rows} rows.",
        )
    return CheckResult(
        "Tickets arrived count",
        False,
        f"Mismatch: summary reports {arrivals_reported}, tickets_stats.csv rows {ticket_rows}.",
    )


def _closure_count_check(closures_reported: float, closed_rows: int, tolerance: float) -> CheckResult:
    if _approx_equal(closures_reported, closed_rows, tolerance):
        return CheckResult(
            "Tickets closed count",
            True,
            f"summary_stats.csv reports {closures_reported}, detected {closed_rows} closed tickets.",
        )
    return CheckResult(
        "Tickets closed count",
        False,
        f"Mismatch: summary reports {closures_reported}, detected {closed_rows} closed tickets.",
    )


def _closure_rate_check(closure_rate_reported: float, arrivals: float, closures: float, tolerance: float) -> CheckResult:
    if arrivals <= 0:
        return CheckResult("Closure rate", True, "No arrivals recorded; skipping closure rate check.")
    computed = closures / arrivals
    if _approx_equal(closure_rate_reported, computed, tolerance):
        return CheckResult(
            "Closure rate",
            True,
            f"Reported {closure_rate_reported:.6f} vs computed {computed:.6f}.",
        )
    return CheckResult(
        "Closure rate",
        False,
        f"Mismatch: reported {closure_rate_reported:.6f} vs computed {computed:.6f}.",
    )


def _mean_time_check(summary_value: float | None, ticket_rows: List[Dict[str, str]], tolerance: float) -> CheckResult:
    closed_times: List[float] = []
    for row in ticket_rows:
        if not row.get("closed_time"):
            continue
        try:
            closed_times.append(float(row.get("time_in_system", 0.0)))
        except (TypeError, ValueError):
            continue

    if not closed_times:
        return CheckResult("Mean time in system", True, "No closed tickets to evaluate mean time in system.")

    computed = sum(closed_times) / len(closed_times)
    if summary_value is None:
        return CheckResult(
            "Mean time in system",
            False,
            "summary_stats.csv missing mean_time_in_system; cannot validate against ticket data.",
        )
    if _approx_equal(summary_value, computed, tolerance):
        return CheckResult(
            "Mean time in system",
            True,
            f"Reported {summary_value:.6f} vs computed {computed:.6f} from closed tickets.",
        )
    return CheckResult(
        "Mean time in system",
        False,
        f"Mismatch: reported {summary_value:.6f} vs computed {computed:.6f} from closed tickets.",
    )


def _ticket_bounds_check(ticket_rows: List[Dict[str, str]], tolerance: float) -> CheckResult:
    fields = [
        "wait_dev",
        "wait_review",
        "wait_testing",
        "service_time_dev",
        "service_time_review",
        "service_time_testing",
        "total_wait",
        "time_in_system",
    ]

    violations: List[str] = []
    for row in ticket_rows:
        ticket_id = row.get("ticket_id", "<unknown>")
        parsed: Dict[str, float] = {}
        for field in fields:
            try:
                parsed[field] = float(row.get(field, 0.0))
            except (TypeError, ValueError):
                violations.append(f"ticket {ticket_id}: unable to parse {field}")
                continue

        for field, value in parsed.items():
            if value < -tolerance:
                violations.append(f"ticket {ticket_id}: {field}={value}")

        total_wait = parsed.get("total_wait")
        time_in_system = parsed.get("time_in_system")
        if total_wait is not None and time_in_system is not None:
            if time_in_system + tolerance < total_wait:
                violations.append(
                    f"ticket {ticket_id}: time_in_system {time_in_system} < total_wait {total_wait}"
                )

    if violations:
        joined = "; ".join(violations)
        return CheckResult("Ticket domain bounds", False, f"Violations detected: {joined}")
    return CheckResult("Ticket domain bounds", True, "All waits and service times non-negative; time_in_system ≥ total_wait.")


def _compare_metric_values(metric: str, aggregate_value: Any, summary_value: Any, tolerance: float) -> str | None:
    if aggregate_value is None:
        return f"{metric}: aggregate missing"
    if summary_value is None:
        return f"{metric}: summary missing"

    if _is_number(aggregate_value) and _is_number(summary_value):
        if _approx_equal(float(aggregate_value), float(summary_value), tolerance):
            return None
        return f"{metric}: aggregate {aggregate_value} vs summary {summary_value}"

    if str(aggregate_value) != str(summary_value):
        return f"{metric}: aggregate {aggregate_value} vs summary {summary_value}"

    return None


def _stage_cycle_consistency_check(ticket_rows: List[Dict[str, str]], tolerance: float) -> CheckResult:
    stages = [
        ("dev", "dev_cycles", "wait_dev", "service_time_dev"),
        ("review", "review_cycles", "wait_review", "service_time_review"),
        ("testing", "test_cycles", "wait_testing", "service_time_testing"),
    ]

    violations: List[str] = []
    for row in ticket_rows:
        ticket_id = row.get("ticket_id", "<unknown>")
        for _, cycles_field, wait_field, service_field in stages:
            try:
                cycles = float(row.get(cycles_field, 0.0))
                wait_value = float(row.get(wait_field, 0.0))
                service_value = float(row.get(service_field, 0.0))
            except (TypeError, ValueError):
                violations.append(f"ticket {ticket_id}: unable to parse cycle data for {cycles_field}")
                continue

            if _approx_equal(cycles, 0.0, tolerance):
                if abs(wait_value) > tolerance:
                    violations.append(f"ticket {ticket_id}: {wait_field}={wait_value} with {cycles_field}=0")
                if abs(service_value) > tolerance:
                    violations.append(f"ticket {ticket_id}: {service_field}={service_value} with {cycles_field}=0")

    if violations:
        return CheckResult("Stage cycle consistency", False, "; ".join(violations))
    return CheckResult("Stage cycle consistency", True, "Zero-cycle stages have zero wait and service time.")


def _wait_decomposition_check(ticket_rows: List[Dict[str, str]], tolerance: float) -> CheckResult:
    violations: List[str] = []
    for row in ticket_rows:
        ticket_id = row.get("ticket_id", "<unknown>")
        try:
            wait_dev = float(row.get("wait_dev", 0.0))
            wait_review = float(row.get("wait_review", 0.0))
            wait_testing = float(row.get("wait_testing", 0.0))
            total_wait = float(row.get("total_wait", 0.0))
        except (TypeError, ValueError):
            violations.append(f"ticket {ticket_id}: unable to parse wait components")
            continue

        if not _approx_equal(total_wait, wait_dev + wait_review + wait_testing, tolerance):
            violations.append(
                f"ticket {ticket_id}: total_wait {total_wait} != waits sum {wait_dev + wait_review + wait_testing}"
            )

    if violations:
        return CheckResult("Total wait decomposition", False, "; ".join(violations))
    return CheckResult("Total wait decomposition", True, "total_wait aligns with component waits.")


def _collect_stage_samples(ticket_rows: List[Dict[str, str]], tolerance: float) -> Dict[str, StageSamples]:
    """Gather waits and services for each stage using the stage-entry rule.

    Inclusion rule: tickets count toward stage means only when they entered the stage,
    defined as having strictly positive cycles or service time (within tolerance).
    """

    stages = {
        "dev": ("dev_cycles", "wait_dev", "service_time_dev"),
        "review": ("review_cycles", "wait_review", "service_time_review"),
        "testing": ("test_cycles", "wait_testing", "service_time_testing"),
    }

    samples: Dict[str, StageSamples] = {
        name: StageSamples([], [], 0) for name in stages
    }

    for row in ticket_rows:
        for stage, (cycles_field, wait_field, service_field) in stages.items():
            try:
                cycles = float(row.get(cycles_field, 0.0))
                wait_value = float(row.get(wait_field, 0.0))
                service_value = float(row.get(service_field, 0.0))
            except (TypeError, ValueError):
                samples[stage].parse_failures += 1
                continue

            if cycles > tolerance or service_value > tolerance:
                samples[stage].waits.append(wait_value)
                samples[stage].services.append(service_value)
            elif cycles < -tolerance or service_value < -tolerance or wait_value < -tolerance:
                samples[stage].parse_failures += 1
                continue
            else:
                continue

    return samples


def _avg_wait_alignment_check(
    summary_metrics: Dict[str, float],
    stage_samples: Dict[str, StageSamples],
    tolerance: float,
) -> List[CheckResult]:
    """Compare per-stage wait means from microdata against reported summaries."""

    checks: List[CheckResult] = []
    summary_keys = {
        "dev": "avg_wait_dev",
        "review": "avg_wait_review",
        "testing": "avg_wait_testing",
    }

    inclusion_rule = (
        "Averages computed only over tickets that entered the stage (service_time>0 or cycles>0)."
    )

    for stage, summary_key in summary_keys.items():
        summary_value = summary_metrics.get(summary_key)
        samples = stage_samples.get(stage, StageSamples([], [], 0))
        waits = samples.waits

        if summary_value is None:
            checks.append(
                CheckResult(
                    f"{stage} wait summary present",
                    False,
                    f"Missing {summary_key} in summary_stats.csv. {inclusion_rule}",
                )
            )
            continue

        if not waits:
            if _approx_equal(summary_value, 0.0, tolerance):
                details = (
                    f"No tickets entered {stage}; summary {summary_key}={summary_value:.6f}. {inclusion_rule}"
                )
                checks.append(CheckResult(f"{stage} average wait", True, details))
            else:
                details = (
                    f"No stage entries for {stage} under inclusion rule, but summary {summary_key}={summary_value:.6f}."
                    f" {inclusion_rule}"
                )
                checks.append(CheckResult(f"{stage} average wait", False, details))
            continue

        micro_mean = sum(waits) / len(waits)
        if _approx_equal(summary_value, micro_mean, tolerance):
            details = (
                f"Summary {summary_key}={summary_value:.6f} vs micro mean {micro_mean:.6f} ({len(waits)} samples)."
                f" {inclusion_rule}"
            )
            checks.append(CheckResult(f"{stage} average wait", True, details))
        else:
            details = (
                f"Mismatch for {stage}: summary {summary_key}={summary_value:.6f}, micro mean {micro_mean:.6f}"
                f" ({len(waits)} samples). {inclusion_rule}"
            )
            checks.append(CheckResult(f"{stage} average wait", False, details))

        if samples.parse_failures:
            checks[-1].details += f" Parse issues for {samples.parse_failures} rows (excluded)."

    return checks


def _stage_identity_checks(
    stage_samples: Dict[str, StageSamples],
    tolerance: float,
) -> List[CheckResult]:
    """Validate Little-family identity E[T]=E[wait]+E[service] per stage."""

    checks: List[CheckResult] = []
    for stage, samples in stage_samples.items():
        waits = samples.waits
        services = samples.services

        if not waits or not services:
            details = (
                f"No stage entries for {stage} under inclusion rule (service_time>0 or cycles>0); skipping identity check."
            )
            checks.append(CheckResult(f"{stage} Little identity", True, details))
            continue

        mean_wait = sum(waits) / len(waits)
        mean_service = sum(services) / len(services)
        mean_total = sum(w + s for w, s in zip(waits, services)) / len(waits)

        if _approx_equal(mean_total, mean_wait + mean_service, tolerance):
            details = (
                f"E[T]={mean_total:.6f} vs E[wait]+E[service]={mean_wait + mean_service:.6f} for {len(waits)} tickets."
                " Inclusion rule: service_time>0 or cycles>0."
            )
            checks.append(CheckResult(f"{stage} Little identity", True, details))
        else:
            details = (
                f"Mismatch for {stage}: E[T]={mean_total:.6f} vs E[wait]+E[service]={mean_wait + mean_service:.6f}"
                f" ({len(waits)} tickets). Inclusion rule: service_time>0 or cycles>0."
            )
            checks.append(CheckResult(f"{stage} Little identity", False, details))

        if samples.parse_failures:
            checks[-1].details += f" Parse issues for {samples.parse_failures} rows (excluded)."

    return checks


def _mean_jobs_identity_check(summary_metrics: Dict[str, float], rel_tolerance: float) -> CheckResult:
    stages = ["dev", "review", "testing"]
    missing_segments: List[str] = []
    comparisons: List[str] = []
    passed = True

    for stage in stages:
        queue_key = f"avg_queue_length_{stage}"
        servers_key = f"avg_servers_{stage}"
        util_key = f"utilization_{stage}"
        system_key = f"avg_system_length_{stage}"

        queue_length = summary_metrics.get(queue_key)
        avg_servers = summary_metrics.get(servers_key)
        utilization = summary_metrics.get(util_key)
        system_length = summary_metrics.get(system_key)

        missing_keys = [
            key
            for key, value in [
                (queue_key, queue_length),
                (servers_key, avg_servers),
                (util_key, utilization),
                (system_key, system_length),
            ]
            if value is None
        ]
        if missing_keys:
            passed = False
            missing_segments.append(f"{stage} missing: {', '.join(missing_keys)}")
            continue

        ls_value = avg_servers * utilization
        expected = queue_length + ls_value
        if _approx_equal(system_length, expected, rel_tolerance):
            comparisons.append(
                (
                    f"{stage}: {system_key}={system_length:.6f}, expected {expected:.6f}"
                    f" from queue {queue_length:.6f} + Ls {ls_value:.6f}"
                    f" (avg_servers={avg_servers:.6f}, utilization={utilization:.6f})"
                    f" within ±{rel_tolerance * 100:.2f}%"
                )
            )
        else:
            passed = False
            comparisons.append(
                (
                    f"{stage}: {system_key}={system_length:.6f} vs expected {expected:.6f}"
                    f" from queue {queue_length:.6f} + Ls {ls_value:.6f}"
                    f" (avg_servers={avg_servers:.6f}, utilization={utilization:.6f});"
                    f" outside ±{rel_tolerance * 100:.2f}%"
                )
            )

    details_parts: List[str] = []
    if comparisons:
        details_parts.append("; ".join(comparisons))
    if missing_segments:
        details_parts.append("; ".join(missing_segments))
    details = " ".join(details_parts) if details_parts else "No stage data available."

    return CheckResult("Mean jobs identity (Little)", passed, details)


def _summary_bounds_check(summary_metrics: Dict[str, float], tolerance: float) -> CheckResult:
    violations: List[str] = []

    for metric, value in summary_metrics.items():
        if metric.startswith(("avg_wait_", "avg_queue_length_", "throughput_")):
            if value < -tolerance:
                violations.append(f"{metric}={value}")
        if metric.startswith("utilization_"):
            if value < -tolerance or value > 1 + tolerance:
                violations.append(f"{metric}={value}")

    if violations:
        return CheckResult("Summary metric bounds", False, f"Out-of-bounds metrics: {', '.join(violations)}")
    return CheckResult("Summary metric bounds", True, "Throughput, waits, queue lengths non-negative; utilizations within [0, 1].")


# ---------------------------------------------------------------------------
# Verification runners
# ---------------------------------------------------------------------------
def verify_single_run(
    base_dir: str,
    tolerance: float,
    mean_jobs_rel_tolerance: float,
    fail_fast: bool,
    baseline_rows: Sequence[Dict[str, Any]] | None = None,
    baseline_note: str | None = None,
) -> RunReport:
    results: List[CheckResult] = []
    if baseline_note:
        results.append(CheckResult("ETL baseline metrics present", False, baseline_note))
    if not os.path.isdir(base_dir):
        results.append(CheckResult("Input directory present", False, f"Directory not found: {base_dir}"))
        return RunReport(base_dir, results)

    summary_path = os.path.join(base_dir, SUMMARY_FILENAME)
    tickets_path = os.path.join(base_dir, TICKETS_FILENAME)

    if not _ensure_exists(summary_path, "summary_stats.csv present", results) and fail_fast:
        return RunReport(base_dir, results)
    if not _ensure_exists(tickets_path, "tickets_stats.csv present", results) and fail_fast:
        return RunReport(base_dir, results)

    try:
        summary_metrics = _load_summary(summary_path)
        results.append(CheckResult("summary_stats.csv parsed", True, f"Loaded {len(summary_metrics)} metrics."))
    except Exception as exc:  # noqa: BLE001 - explicit failure reporting required
        results.append(CheckResult("summary_stats.csv parsed", False, f"Failed to load summary file: {exc}"))
        return RunReport(base_dir, results)

    try:
        ticket_rows = _load_tickets(tickets_path)
        results.append(CheckResult("tickets_stats.csv parsed", True, f"Loaded {len(ticket_rows)} rows."))
    except Exception as exc:  # noqa: BLE001 - explicit failure reporting required
        results.append(CheckResult("tickets_stats.csv parsed", False, f"Failed to load tickets file: {exc}"))
        return RunReport(base_dir, results)

    stage_samples = _collect_stage_samples(ticket_rows, tolerance)

    checks: List[CheckResult] = [
        CheckResult(
            "Stage entry inclusion rule",
            True,
            "Per-stage means use only tickets with service_time>0 or cycles>0, matching queue_wait_records aggregation.",
        ),
        _required_metrics_check(summary_metrics, ["tickets_arrived", "tickets_closed", "closure_rate"], tolerance),
        _summary_bounds_check(summary_metrics, tolerance),
        _mean_jobs_identity_check(summary_metrics, mean_jobs_rel_tolerance),
    ]

    arrivals_reported = summary_metrics.get("tickets_arrived")
    closures_reported = summary_metrics.get("tickets_closed")
    closure_rate_reported = summary_metrics.get("closure_rate")

    if arrivals_reported is not None:
        checks.append(_arrival_count_check(arrivals_reported, len(ticket_rows), tolerance))
    if closures_reported is not None:
        closed_rows = sum(1 for row in ticket_rows if row.get("closed_time"))
        checks.append(_closure_count_check(closures_reported, closed_rows, tolerance))
    if closure_rate_reported is not None and arrivals_reported is not None and closures_reported is not None:
        checks.append(_closure_rate_check(closure_rate_reported, arrivals_reported, closures_reported, tolerance))

    checks.append(_mean_time_check(summary_metrics.get("mean_time_in_system"), ticket_rows, tolerance))
    checks.append(_ticket_bounds_check(ticket_rows, tolerance))
    checks.append(_stage_cycle_consistency_check(ticket_rows, tolerance))
    checks.append(_wait_decomposition_check(ticket_rows, tolerance))
    checks.extend(_avg_wait_alignment_check(summary_metrics, stage_samples, tolerance))
    checks.extend(_stage_identity_checks(stage_samples, tolerance))
    if baseline_rows:
        checks.extend(_baseline_checks(summary_metrics, ticket_rows, baseline_rows))

    for check in checks:
        results.append(check)
        if fail_fast and not check.passed:
            break

    return RunReport(base_dir, results)


def verify_aggregate_summary(
    base_dir: str, experiments: Sequence[str], tolerance: float, fail_fast: bool
) -> RunReport:
    label = os.path.join(base_dir, AGGREGATE_FILENAME)
    results: List[CheckResult] = []

    if not _ensure_exists(label, "aggregate_summary.csv present", results) and fail_fast:
        return RunReport(label, results)

    try:
        aggregate_rows, fieldnames = _load_aggregate_summary(label)
        results.append(CheckResult("aggregate_summary.csv parsed", True, f"Loaded {len(aggregate_rows)} rows."))
    except Exception as exc:  # noqa: BLE001 - explicit failure reporting required
        results.append(CheckResult("aggregate_summary.csv parsed", False, f"Failed to load aggregate file: {exc}"))
        return RunReport(label, results)

    required_columns = {"experiment_id", *SUMMARY_METRICS}
    missing_columns = required_columns - set(fieldnames or [])
    if missing_columns:
        results.append(
            CheckResult(
                "Aggregate columns present",
                False,
                f"Missing columns: {', '.join(sorted(missing_columns))}",
            )
        )
        if fail_fast:
            return RunReport(label, results)
    else:
        results.append(CheckResult("Aggregate columns present", True, "All required columns found."))

    expected_ids = [os.path.basename(path.rstrip(os.sep)) for path in experiments]
    rows_by_id: Dict[str, Dict[str, Any]] = {}
    duplicate_ids: List[str] = []
    blank_ids = 0
    for row in aggregate_rows:
        exp_id = str(row.get("experiment_id") or "").strip()
        if not exp_id:
            blank_ids += 1
            continue
        if exp_id in rows_by_id:
            duplicate_ids.append(exp_id)
            continue
        rows_by_id[exp_id] = row

    missing_ids = [exp_id for exp_id in expected_ids if exp_id not in rows_by_id]
    extra_ids = [exp_id for exp_id in rows_by_id if exp_id not in expected_ids]

    coverage_parts: List[str] = []
    if missing_ids:
        coverage_parts.append(f"Missing rows: {', '.join(sorted(missing_ids))}")
    if extra_ids:
        coverage_parts.append(f"Unexpected rows: {', '.join(sorted(extra_ids))}")
    if duplicate_ids:
        coverage_parts.append(f"Duplicate experiment_ids: {', '.join(sorted(set(duplicate_ids)))}")
    if blank_ids:
        coverage_parts.append(f"Blank experiment_id entries: {blank_ids}")

    coverage_passed = not coverage_parts and len(rows_by_id) == len(expected_ids)
    coverage_details = "; ".join(coverage_parts) if coverage_parts else "One row per experiment directory detected."
    results.append(CheckResult("Aggregate experiment coverage", coverage_passed, coverage_details))
    if fail_fast and not coverage_passed:
        return RunReport(label, results)

    for experiment_dir in experiments:
        exp_id = os.path.basename(experiment_dir.rstrip(os.sep))
        aggregate_row = rows_by_id.get(exp_id)
        if aggregate_row is None:
            continue

        summary_path = os.path.join(experiment_dir, SUMMARY_FILENAME)
        try:
            summary_metrics = _load_summary_with_parsing(summary_path)
        except Exception as exc:  # noqa: BLE001 - explicit failure reporting required
            results.append(
                CheckResult(
                    f"Aggregate alignment: {exp_id}",
                    False,
                    f"Failed to parse summary_stats.csv for {exp_id}: {exc}",
                )
            )
            if fail_fast:
                return RunReport(label, results)
            continue

        mismatches: List[str] = []
        for metric in SUMMARY_METRICS:
            discrepancy = _compare_metric_values(metric, aggregate_row.get(metric), summary_metrics.get(metric), tolerance)
            if discrepancy:
                mismatches.append(discrepancy)

        if mismatches:
            results.append(
                CheckResult(
                    f"Aggregate alignment: {exp_id}",
                    False,
                    "; ".join(mismatches),
                )
            )
            if fail_fast:
                return RunReport(label, results)
        else:
            results.append(
                CheckResult(
                    f"Aggregate alignment: {exp_id}",
                    True,
                    f"All {len(SUMMARY_METRICS)} metrics match summary_stats.csv.",
                )
            )

    return RunReport(label, results)


def verify_sweep(
    input_dir: str,
    tolerance: float,
    mean_jobs_rel_tolerance: float,
    fail_fast: bool,
    experiment_dirs: Sequence[str] | None = None,
    baseline_rows: Sequence[Dict[str, Any]] | None = None,
    baseline_note: str | None = None,
) -> Tuple[List[RunReport], bool]:
    run_reports: List[RunReport] = []
    if not os.path.isdir(input_dir):
        return [RunReport(input_dir, [CheckResult("Sweep directory present", False, f"Directory not found: {input_dir}")])], False

    experiments = list(experiment_dirs) if experiment_dirs is not None else detect_sweep_experiments(input_dir)
    if not experiments:
        message = (
            "No experiment subdirectories found containing summary_stats.csv and tickets_stats.csv."
        )
        return [RunReport(input_dir, [CheckResult("Sweep contents", False, message)])], False

    overall_passed = True
    for subdir in experiments:
        report = verify_single_run(
            subdir,
            tolerance,
            mean_jobs_rel_tolerance,
            fail_fast,
            baseline_rows,
            baseline_note,
        )
        run_reports.append(report)
        overall_passed = overall_passed and report.passed

        per_experiment_content = build_report(
            subdir,
            "single",
            tolerance,
            mean_jobs_rel_tolerance,
            [report],
            report.passed,
        )
        write_report(subdir, per_experiment_content)

        if fail_fast and not report.passed:
            break

    aggregate_report = verify_aggregate_summary(input_dir, experiments, tolerance, fail_fast)
    run_reports.append(aggregate_report)
    overall_passed = overall_passed and aggregate_report.passed

    return run_reports, overall_passed


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def _render_table(results: List[CheckResult]) -> List[str]:
    lines = ["| Status | Check | Details |", "| --- | --- | --- |"]
    for result in results:
        status = "✅" if result.passed else "❌"
        lines.append(f"| {status} | {result.name} | {result.details} |")
    return lines


def build_report(
    input_dir: str,
    mode: str,
    tolerance: float,
    mean_jobs_rel_tolerance: float,
    run_reports: Sequence[RunReport],
    overall_passed: bool,
) -> str:
    def _format_heading(base: str, path: str) -> str:
        if os.path.exists(base) and os.path.exists(path):
            try:
                if os.path.samefile(base, path):
                    return path
            except FileNotFoundError:
                pass
        try:
            return os.path.relpath(path, base)
        except ValueError:
            return path

    lines: List[str] = [
        "# Verification Report",
        f"*Generated: {dt.datetime.utcnow().isoformat()}Z*",
        "",
        f"- Input directory: `{input_dir}`",
        f"- Mode: {mode}",
        f"- Tolerance: {tolerance}",
        f"- Mean-jobs relative tolerance: {mean_jobs_rel_tolerance}",
        "",
    ]

    overall_status = "✅ PASS" if overall_passed else "❌ FAIL"
    lines.append(f"## Overall Status: {overall_status}")
    lines.append("")

    if mode == "sweep":
        lines.append("## Experiment Summary")
        lines.append("| Experiment | Status | Checks |")
        lines.append("| --- | --- | --- |")
        for report in run_reports:
            heading = _format_heading(input_dir, report.label)
            total_checks = len(report.results)
            passed_checks = sum(1 for result in report.results if result.passed)
            first_failure = next((result for result in report.results if not result.passed), None)
            details = f"{passed_checks}/{total_checks} checks passed"
            if first_failure:
                details += f"; first failure: {first_failure.name}"
            status = "✅ PASS" if report.passed else "❌ FAIL"
            lines.append(f"| {heading} | {status} | {details} |")
        lines.append("")

    for report in run_reports:
        heading = _format_heading(input_dir, report.label)
        lines.append(f"### Run: {heading}")
        lines.extend(_render_table(report.results))
        lines.append("")

    return "\n".join(lines)


def write_report(input_dir: str, content: str) -> str:
    report_path = os.path.join(input_dir, REPORT_FILENAME)
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return report_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode = args.mode
    experiment_dirs = None
    baseline_path = _resolve_baseline_path(args.etl_dir, args.baseline_metrics)
    baseline_rows: List[Dict[str, Any]] = []
    baseline_note = None
    if baseline_path:
        try:
            baseline_rows = _load_baseline_rows(baseline_path)
        except FileNotFoundError:
            baseline_note = f"Missing baseline metrics file at {baseline_path}"
    if args.mode == "single":
        experiment_dirs = detect_sweep_experiments(args.input)
        if experiment_dirs:
            mode = "sweep"

    if mode == "sweep":
        run_reports, overall_passed = verify_sweep(
            args.input,
            args.tolerance,
            args.mean_jobs_rel_tolerance,
            args.fail_fast,
            experiment_dirs,
            baseline_rows,
            baseline_note,
        )
    else:
        run_report = verify_single_run(
            args.input,
            args.tolerance,
            args.mean_jobs_rel_tolerance,
            args.fail_fast,
            baseline_rows,
            baseline_note,
        )
        run_reports = [run_report]
        overall_passed = run_report.passed

    report_content = build_report(
        args.input,
        mode,
        args.tolerance,
        args.mean_jobs_rel_tolerance,
        run_reports,
        overall_passed,
    )
    report_path = write_report(args.input, report_content)
    print(f"Verification report written to {report_path}")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
