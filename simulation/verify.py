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

    checks: List[CheckResult] = [
        _required_metrics_check(summary_metrics, ["tickets_arrived", "tickets_closed", "closure_rate"], tolerance),
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
