"""Validation helpers for simulation consistency checks."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from simulation.run_sweeps import parse_value

SUMMARY_FILENAME = "summary_stats.csv"
TICKETS_FILENAME = "tickets_stats.csv"


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


@dataclass
class ScenarioResult:
    name: str
    output_dir: str
    summary_path: str
    tickets_path: str
    config_snapshot: Dict[str, Any]
    summary_metrics: Dict[str, Any]
    ticket_rows: List[Dict[str, Any]]
    verification_report: str | None = None
    checks: List[CheckResult] | None = None

    @property
    def passed(self) -> bool:
        results = self.checks or []
        return all(r.passed for r in results)


def load_summary_metrics(summary_path: str) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    with open(summary_path, "r", encoding="utf-8") as handle:
        headers = handle.readline().strip().split(",")
        if not headers or "metric" not in headers:
            raise ValueError(f"summary_stats missing metric column: {summary_path}")
        metric_idx = headers.index("metric")
        value_idx = headers.index("value") if "value" in headers else None
        for line in handle:
            parts = [part.strip() for part in line.split(",")]
            if not parts or len(parts) <= metric_idx:
                continue
            metric = parts[metric_idx]
            raw_value = parts[value_idx] if value_idx is not None and len(parts) > value_idx else ""
            metrics[metric] = parse_value(raw_value)
    return metrics


def load_ticket_rows(tickets_path: str) -> List[Dict[str, Any]]:
    import csv

    with open(tickets_path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [{k: parse_value(v or "") for k, v in row.items()} for row in reader]


def _mean(values: Iterable[float]) -> float:
    vals = [v for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return float(sum(vals) / len(vals)) if vals else 0.0


def _approx_equal(a: float, b: float, rel: float, abs_tol: float) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(1.0, abs(a), abs(b)))


def check_boundedness(summary: Dict[str, Any]) -> List[CheckResult]:
    results: List[CheckResult] = []
    bounds_violations: List[str] = []
    for key, value in summary.items():
        if key.startswith("avg_wait") or key.startswith("avg_queue_length") or key.startswith("mean_time_in_system"):
            if value is not None and isinstance(value, (int, float)) and value < -1e-9:
                bounds_violations.append(f"{key}={value}")
        if key.startswith("utilization") or key == "closure_rate":
            if value is None or not isinstance(value, (int, float)):
                continue
            if value < -1e-9 or value > 1 + 1e-9:
                bounds_violations.append(f"{key}={value}")
    if bounds_violations:
        results.append(
            CheckResult(
                "Bounds", False, f"Found values outside expected ranges: {', '.join(sorted(bounds_violations))}"
            )
        )
    else:
        results.append(CheckResult("Bounds", True, "All waits/utilizations/closure_rate within expected ranges."))
    return results


def check_conservation(summary: Dict[str, Any], tickets: List[Dict[str, Any]], sim_duration: float) -> List[CheckResult]:
    results: List[CheckResult] = []
    tolerance_rel = 0.02
    tolerance_abs = 1e-6

    arrivals = summary.get("tickets_arrived")
    closures = summary.get("tickets_closed")
    closure_rate = summary.get("closure_rate")
    closed_rows = [row for row in tickets if row.get("closed_time") not in {None, ""}]

    if isinstance(arrivals, (int, float)):
        arrival_check = _approx_equal(arrivals, len(tickets), tolerance_rel, tolerance_abs)
        results.append(
            CheckResult(
                "Arrivals vs ticket rows",
                arrival_check,
                f"summary_arrivals={arrivals}, ticket_rows={len(tickets)}",
            )
        )
    if isinstance(closures, (int, float)):
        closure_check = _approx_equal(closures, len(closed_rows), tolerance_rel, tolerance_abs)
        results.append(
            CheckResult(
                "Closures vs closed rows",
                closure_check,
                f"summary_closures={closures}, closed_rows={len(closed_rows)}",
            )
        )
    if isinstance(arrivals, (int, float)) and isinstance(closures, (int, float)) and isinstance(closure_rate, (int, float)):
        computed_rate = closures / arrivals if arrivals else 0.0
        results.append(
            CheckResult(
                "Closure rate recomputed",
                _approx_equal(closure_rate, computed_rate, tolerance_rel, tolerance_abs),
                f"reported={closure_rate:.6f}, computed={computed_rate:.6f}",
            )
        )

    # Throughput ~= completions / horizon using per-ticket cycle counts
    for stage, throughput_key, starts_field, completions_field in [
        ("dev", "throughput_dev", "service_starts_dev", "service_completions_dev"),
        ("review", "throughput_review", "service_starts_review", "service_completions_review"),
        ("testing", "throughput_testing", "service_starts_testing", "service_completions_testing"),
    ]:
        throughput = summary.get(throughput_key)
        completion_counts = [row.get(completions_field) for row in tickets]
        if any(count not in {None, ""} for count in completion_counts):
            cycle_total = _mean(float(row.get(completions_field, 0.0)) for row in tickets) * len(tickets)
        else:
            cycle_total = _mean(float(row.get(starts_field, 0.0)) for row in tickets) * len(tickets)
        computed = cycle_total / sim_duration if sim_duration else 0.0
        if isinstance(throughput, (int, float)):
            results.append(
                CheckResult(
                    f"Throughput conservation ({stage})",
                    _approx_equal(throughput, computed, 0.05, tolerance_abs),
                    f"reported={throughput:.6f}, derived={computed:.6f}",
                )
            )

        avg_queue = summary.get(f"avg_queue_length_{stage}")
        avg_servers = summary.get(f"avg_servers_{stage}")
        util = summary.get(f"utilization_{stage}")
        avg_system = summary.get(f"avg_system_length_{stage}")
        if all(isinstance(v, (int, float)) for v in [avg_queue, avg_servers, util, avg_system]):
            lhs = avg_queue + avg_servers * util
            results.append(
                CheckResult(
                    f"Little identity ({stage})",
                    _approx_equal(avg_system, lhs, 0.05, tolerance_abs),
                    f"avg_system={avg_system:.6f}, expected={lhs:.6f}",
                )
            )
    return results


def check_baseline(summary: Dict[str, Any], baseline: Dict[str, Any], rel_tol: float, abs_tol: float) -> List[CheckResult]:
    results: List[CheckResult] = []
    for metric, expected in baseline.items():
        observed = summary.get(metric)
        if expected is None or expected == "":
            continue
        if not isinstance(expected, (int, float)) or observed is None or not isinstance(observed, (int, float)):
            continue
        passed = _approx_equal(observed, expected, rel_tol, abs_tol)
        details = f"observed={observed}, expected={expected}"
        results.append(CheckResult(f"Baseline: {metric}", passed, details))
    return results


def aggregate_ticket_means(tickets: List[Dict[str, Any]]) -> Dict[str, float]:
    waits = [float(row.get("total_wait", 0.0)) for row in tickets if isinstance(row.get("total_wait"), (int, float))]
    times = [float(row.get("time_in_system", 0.0)) for row in tickets if isinstance(row.get("time_in_system"), (int, float))]
    return {
        "mean_total_wait": _mean(waits),
        "mean_time_in_system": _mean(times),
    }


def monotonicity_checks(scenarios: Dict[str, ScenarioResult]) -> List[CheckResult]:
    results: List[CheckResult] = []
    baseline = scenarios.get("baseline")
    arrival_high = scenarios.get("arrival_high")
    feedback_high = scenarios.get("feedback_high")
    service_slow = scenarios.get("service_slow")
    capacity_high = scenarios.get("capacity_high")

    if baseline and arrival_high:
        for metric in ["avg_wait_dev", "avg_wait_review", "avg_wait_testing", "mean_time_in_system"]:
            base_val = baseline.summary_metrics.get(metric)
            inc_val = arrival_high.summary_metrics.get(metric)
            if isinstance(base_val, (int, float)) and isinstance(inc_val, (int, float)):
                passed = inc_val >= base_val - 1e-9
                results.append(
                    CheckResult(
                        f"Monotonic arrival→{metric}",
                        passed,
                        f"baseline={base_val}, higher_arrival={inc_val}",
                    )
                )
    if baseline and feedback_high:
        base = aggregate_ticket_means(baseline.ticket_rows)
        fb = aggregate_ticket_means(feedback_high.ticket_rows)
        if isinstance(baseline.summary_metrics.get("closure_rate"), (int, float)) and isinstance(
            feedback_high.summary_metrics.get("closure_rate"), (int, float)
        ):
            passed = feedback_high.summary_metrics["closure_rate"] <= baseline.summary_metrics["closure_rate"] + 1e-9
            results.append(
                CheckResult(
                    "Monotonic feedback→closure_rate",
                    passed,
                    f"baseline={baseline.summary_metrics['closure_rate']}, feedback_high={feedback_high.summary_metrics['closure_rate']}",
                )
            )
        results.append(
            CheckResult(
                "Monotonic feedback→wait/time_in_system",
                fb["mean_total_wait"] >= base["mean_total_wait"] - 1e-9
                and fb["mean_time_in_system"] >= base["mean_time_in_system"] - 1e-9,
                f"baseline_wait={base['mean_total_wait']}, feedback_wait={fb['mean_total_wait']}; baseline_time={base['mean_time_in_system']}, feedback_time={fb['mean_time_in_system']}",
            )
        )

    if baseline and service_slow:
        for metric in ["avg_wait_dev", "avg_wait_review", "avg_wait_testing", "mean_time_in_system"]:
            base_val = baseline.summary_metrics.get(metric)
            slow_val = service_slow.summary_metrics.get(metric)
            if isinstance(base_val, (int, float)) and isinstance(slow_val, (int, float)):
                results.append(
                    CheckResult(
                        f"Service scale→{metric}",
                        slow_val >= base_val - 1e-9,
                        f"baseline={base_val}, scaled={slow_val}",
                    )
                )

    if baseline and capacity_high:
        for metric in ["avg_wait_dev", "avg_wait_review", "avg_wait_testing"]:
            base_val = baseline.summary_metrics.get(metric)
            cap_val = capacity_high.summary_metrics.get(metric)
            if isinstance(base_val, (int, float)) and isinstance(cap_val, (int, float)):
                results.append(
                    CheckResult(
                        f"Capacity↑→{metric}",
                        cap_val <= base_val + 1e-9,
                        f"baseline={base_val}, capacity_high={cap_val}",
                    )
                )
        for metric in ["utilization_dev", "utilization_review", "utilization_testing"]:
            base_val = baseline.summary_metrics.get(metric)
            cap_val = capacity_high.summary_metrics.get(metric)
            if isinstance(base_val, (int, float)) and isinstance(cap_val, (int, float)):
                results.append(
                    CheckResult(
                        f"Capacity↑→{metric}",
                        cap_val <= base_val + 1e-9,
                        f"baseline={base_val}, capacity_high={cap_val}",
                    )
                )

    return results


def write_json_report(path: str, results: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
