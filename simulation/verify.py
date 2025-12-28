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
from typing import Dict, Iterable, List, Sequence, Tuple

SUMMARY_FILENAME = "summary_stats.csv"
TICKETS_FILENAME = "tickets_stats.csv"
REPORT_FILENAME = "verification_report.md"


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


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------
def _ensure_exists(path: str, label: str, results: List[CheckResult]) -> bool:
    if os.path.isfile(path):
        results.append(CheckResult(label, True, f"Found {os.path.basename(path)}."))
        return True
    results.append(CheckResult(label, False, f"Missing required file: {path}"))
    return False


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


def _load_tickets(tickets_path: str) -> List[Dict[str, str]]:
    with open(tickets_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


# ---------------------------------------------------------------------------
# Numeric utilities
# ---------------------------------------------------------------------------
def _approx_equal(a: float, b: float, tolerance: float) -> bool:
    scale = max(1.0, abs(a), abs(b))
    return abs(a - b) <= tolerance * scale


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
def verify_single_run(base_dir: str, tolerance: float, fail_fast: bool) -> RunReport:
    results: List[CheckResult] = []
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

    for check in checks:
        results.append(check)
        if fail_fast and not check.passed:
            break

    return RunReport(base_dir, results)


def verify_sweep(input_dir: str, tolerance: float, fail_fast: bool) -> Tuple[List[RunReport], bool]:
    run_reports: List[RunReport] = []
    if not os.path.isdir(input_dir):
        return [RunReport(input_dir, [CheckResult("Sweep directory present", False, f"Directory not found: {input_dir}")])], False

    subdirs = [
        os.path.join(input_dir, name)
        for name in sorted(os.listdir(input_dir))
        if os.path.isdir(os.path.join(input_dir, name))
    ]

    if not subdirs:
        return [RunReport(input_dir, [CheckResult("Sweep contents", False, "No experiment subdirectories found.")])], False

    overall_passed = True
    for subdir in subdirs:
        report = verify_single_run(subdir, tolerance, fail_fast)
        run_reports.append(report)
        overall_passed = overall_passed and report.passed
        if fail_fast and not report.passed:
            break

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
    run_reports: Sequence[RunReport],
    overall_passed: bool,
) -> str:
    lines: List[str] = [
        "# Verification Report",
        f"*Generated: {dt.datetime.utcnow().isoformat()}Z*",
        "",
        f"- Input directory: `{input_dir}`",
        f"- Mode: {mode}",
        f"- Tolerance: {tolerance}",
        "",
    ]

    overall_status = "✅ PASS" if overall_passed else "❌ FAIL"
    lines.append(f"## Overall Status: {overall_status}")
    lines.append("")

    for report in run_reports:
        heading = report.label if os.path.samefile(input_dir, report.label) else os.path.relpath(report.label, input_dir)
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
    if args.mode == "sweep":
        run_reports, overall_passed = verify_sweep(args.input, args.tolerance, args.fail_fast)
    else:
        run_report = verify_single_run(args.input, args.tolerance, args.fail_fast)
        run_reports = [run_report]
        overall_passed = run_report.passed

    report_content = build_report(args.input, args.mode, args.tolerance, run_reports, overall_passed)
    report_path = write_report(args.input, report_content)
    print(f"Verification report written to {report_path}")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
