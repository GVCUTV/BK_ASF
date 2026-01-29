"""Validation harness for running seeded scenarios and consistency checks."""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from simulation import config as sim_config
from simulation import simulate
from simulation.run_sweeps import apply_config_overrides
from simulation.verify import main as verify_main
from validation import checks

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTDIR = REPO_ROOT / "simulation/experiments"
SCENARIO_PREFIX = "validation"
BASELINE_PATH = REPO_ROOT / "validation/baseline_metrics.csv"
SUMMARY_FILENAME = checks.SUMMARY_FILENAME
TICKETS_FILENAME = checks.TICKETS_FILENAME
RESULTS_JSON = "validation_results.json"
REPORT_MD = "validation_report.md"
DISTRIBUTION_JSON = "distribution_checks.json"


def _configure_logging(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    logfile = base_dir / "validation.log"

    file_handler = logging.FileHandler(logfile, mode="w")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.WARNING)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[file_handler, stream_handler],
        force=True,
    )
    logging.info("Validation logging initialized at %s", logfile)


def _load_baseline_metrics() -> Dict[str, Any]:
    if not BASELINE_PATH.exists():
        logging.warning("Baseline metrics file not found at %s", BASELINE_PATH)
        return {}
    baseline: Dict[str, Any] = {}
    with BASELINE_PATH.open("r", encoding="utf-8") as handle:
        headers = handle.readline().strip().split(",")
        if "metric" not in headers or "value" not in headers:
            logging.warning("Baseline metrics missing required columns.")
            return {}
        metric_idx = headers.index("metric")
        value_idx = headers.index("value")
        for line in handle:
            parts = [part.strip() for part in line.split(",")]
            if len(parts) <= max(metric_idx, value_idx):
                continue
            metric = parts[metric_idx]
            baseline[metric] = checks.parse_value(parts[value_idx]) if hasattr(checks, "parse_value") else parts[value_idx]
    return baseline


def _scenario_overrides(base_seed: int) -> List[Dict[str, Any]]:
    base_rate = sim_config.ARRIVAL_RATE
    scaled_service = {}
    for stage, params in sim_config.SERVICE_TIME_PARAMS.items():
        new_params = dict(params)
        if isinstance(params.get("params"), dict) and "scale" in params["params"]:
            inner = dict(params["params"])
            inner["scale"] = inner["scale"] * 1.5
            new_params["params"] = inner
        scaled_service[stage] = new_params

    return [
        {"id": "baseline", "description": "Current config", "overrides": {"GLOBAL_RANDOM_SEED": base_seed}},
        {
            "id": "arrival_high",
            "description": "Higher arrival rate to test queue pressure",
            "overrides": {"GLOBAL_RANDOM_SEED": base_seed + 1, "ARRIVAL_RATE": base_rate * 1.5},
        },
        {
            "id": "feedback_high",
            "description": "Increased review/testing feedback",
            "overrides": {"GLOBAL_RANDOM_SEED": base_seed + 2, "FEEDBACK_P_DEV": 0.2, "FEEDBACK_P_TEST": 0.2},
        },
        {
            "id": "service_slow",
            "description": "Service-time scales increased",
            "overrides": {"GLOBAL_RANDOM_SEED": base_seed + 3, "SERVICE_TIME_PARAMS": scaled_service},
        },
        {
            "id": "capacity_high",
            "description": "Higher developer availability",
            # Keep the seed aligned with the baseline so the directionality checks
            # measure the isolated impact of additional capacity rather than seed noise.
            "overrides": {"GLOBAL_RANDOM_SEED": base_seed, "TOTAL_CONTRIBUTORS": sim_config.TOTAL_CONTRIBUTORS + 10},
        },
    ]


def _copy_outputs(target_dir: Path) -> tuple[Path, Path]:
    output_dir = Path(__file__).resolve().parent / "output"
    summary_src = output_dir / SUMMARY_FILENAME
    tickets_src = output_dir / TICKETS_FILENAME
    if not summary_src.exists() or not tickets_src.exists():
        raise FileNotFoundError("Expected simulation outputs missing; ensure simulate.main wrote CSVs.")
    target_dir.mkdir(parents=True, exist_ok=True)
    summary_dst = target_dir / SUMMARY_FILENAME
    tickets_dst = target_dir / TICKETS_FILENAME
    shutil.copy2(summary_src, summary_dst)
    shutil.copy2(tickets_src, tickets_dst)
    return summary_dst, tickets_dst


def _persist_config_snapshot(config_path: Path) -> Dict[str, Any]:
    snapshot = sim_config.current_config()
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
    return snapshot


def _run_single_scenario(base_dir: Path, scenario: Dict[str, Any], baseline_metrics: Dict[str, Any]) -> checks.ScenarioResult:
    scenario_dir = base_dir / scenario["id"]
    logging.info("Running scenario %s", scenario["id"])
    applied = apply_config_overrides(scenario.get("overrides", {}))
    logging.info("Applied overrides: %s", applied)

    simulate.main()
    summary_path, tickets_path = _copy_outputs(scenario_dir)
    config_snapshot = _persist_config_snapshot(scenario_dir / "config_used.json")
    summary_metrics = checks.load_summary_metrics(str(summary_path))
    tickets = checks.load_ticket_rows(str(tickets_path))

    check_results: List[checks.CheckResult] = []
    check_results.extend(checks.check_boundedness(summary_metrics))
    check_results.extend(checks.check_conservation(summary_metrics, tickets, sim_config.SIM_DURATION))
    if baseline_metrics and scenario.get("id") == "baseline":
        check_results.extend(
            checks.check_baseline(
                summary_metrics,
                baseline_metrics,
                rel_tol=0.1,
                abs_tol=1e-6,
                ticket_rows=tickets,
            )
        )

    verification_report = None
    try:
        verify_exit = verify_main(["--input", str(scenario_dir)])
        logging.info("Verification exit code for %s: %s", scenario["id"], verify_exit)
        verification_report = str(Path(scenario_dir) / "verification_report.md")
    except SystemExit as exc:  # pragma: no cover - defensive
        logging.error("Verification terminated with %s", exc)

    return checks.ScenarioResult(
        name=scenario["id"],
        output_dir=str(scenario_dir),
        summary_path=str(summary_path),
        tickets_path=str(tickets_path),
        config_snapshot=config_snapshot,
        summary_metrics=summary_metrics,
        ticket_rows=tickets,
        verification_report=verification_report,
        checks=check_results,
    )


def _render_markdown(
    base_dir: Path,
    scenario_results: List[checks.ScenarioResult],
    monotonic_results: List[checks.CheckResult],
    plausibility_results: List[checks.CheckResult] | None = None,
    plausibility_stats: Dict[str, Any] | None = None,
) -> str:
    lines: List[str] = []
    lines.append("# Validation Summary")
    lines.append("")
    lines.append("| Scenario | Status | Key Details |")
    lines.append("| --- | --- | --- |")
    for result in scenario_results:
        status = "✅" if result.passed else "❌"
        details = "; ".join(f"{c.name}: {'PASS' if c.passed else 'FAIL'}" for c in result.checks or [])
        lines.append(f"| {result.name} | {status} | {details} |")
    lines.append("")

    if monotonic_results:
        lines.append("## Directionality Checks")
        lines.append("")
        lines.append("| Check | Status | Details |")
        lines.append("| --- | --- | --- |")
        for check in monotonic_results:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"| {check.name} | {status} | {check.details} |")
        lines.append("")

    if plausibility_results:
        lines.append("## Plausibility Checks")
        lines.append("")
        lines.append("| Check | Status | Details |")
        lines.append("| --- | --- | --- |")
        for check in plausibility_results:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"| {check.name} | {status} | {check.details} |")
        lines.append("")
        if plausibility_stats:
            lines.append("### Distribution Diagnostics")
            for stage, payload in plausibility_stats.get("distributions", {}).get("stages", {}).items():
                ks_val = payload.get("ks_stat")
                ks_text = f"{ks_val:.4f}" if isinstance(ks_val, (int, float)) else "n/a"
                lines.append(f"- **{stage}**: KS={ks_text} with quantiles {payload.get('quantiles')}")
            arrival = plausibility_stats.get("arrivals", {}).get("arrival_rate")
            if arrival:
                lines.append(
                    f"- **Arrival rate**: config={arrival.get('config')} vs ETL={arrival.get('etl')} "
                    f"(rel_change={arrival.get('relative_change'):.3f})"
                )
    lines.append("")

    lines.append("## Artifacts")
    for result in scenario_results:
        lines.append(f"- **{result.name}**: outputs in `{result.output_dir}` (summary/tickets, config snapshot, verification report)")
    return "\n".join(lines)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run validation scenarios and consistency checks.")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR), help="Base experiments directory (default: simulation/experiments)")
    parser.add_argument("--seed", type=int, default=sim_config.GLOBAL_RANDOM_SEED, help="Base random seed for scenarios")
    return parser.parse_args(argv or sys.argv[1:])


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    base_outdir = Path(args.outdir)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    run_dir = base_outdir / f"{SCENARIO_PREFIX}_{stamp}"
    _configure_logging(run_dir)

    baseline_metrics = _load_baseline_metrics()
    scenarios = _scenario_overrides(args.seed)

    results: List[checks.ScenarioResult] = []
    for scenario in scenarios:
        try:
            result = _run_single_scenario(run_dir, scenario, baseline_metrics)
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Scenario %s failed: %s", scenario["id"], exc)
            failed_result = checks.ScenarioResult(
                name=scenario["id"],
                output_dir=str(run_dir / scenario["id"]),
                summary_path="",
                tickets_path="",
                config_snapshot={},
                summary_metrics={},
                ticket_rows=[],
                checks=[checks.CheckResult("Execution", False, str(exc))],
            )
            results.append(failed_result)

    scenario_map = {res.name: res for res in results}
    monotonic_results = checks.monotonicity_checks(scenario_map)
    plausibility_results: List[checks.CheckResult] = []
    plausibility_stats: Dict[str, Any] = {}

    baseline = scenario_map.get("baseline")
    if baseline:
        fit_path = REPO_ROOT / "etl/output/csv/fit_summary.csv"
        service_params_path = REPO_ROOT / sim_config.STATE_PARAMETER_PATHS["service_params"]
        baseline_metadata_path = REPO_ROOT / "validation/baseline_metadata.json"

        param_results, param_stats = checks.compare_service_parameters(
            baseline.config_snapshot,
            str(fit_path),
            str(service_params_path),
            tolerance=checks.DEFAULT_DISTRIBUTION_TOLERANCE,
        )
        dist_results, dist_stats = checks.compare_empirical_distributions(
            baseline.config_snapshot,
            str(fit_path),
            str(service_params_path),
            plot_dir=str(run_dir / "validation" / "plots"),
        )
        arrival_results, arrival_stats = checks.validate_arrival_and_feedback(
            baseline.config_snapshot,
            str(baseline_metadata_path),
            tolerance=checks.DEFAULT_DISTRIBUTION_TOLERANCE,
        )

        plausibility_results.extend(param_results + dist_results + arrival_results)
        plausibility_stats = {
            "parameters": param_stats,
            "distributions": dist_stats,
            "arrivals": arrival_stats,
        }
        checks.write_json_report(str(run_dir / DISTRIBUTION_JSON), plausibility_stats)

    report_md = _render_markdown(run_dir, results, monotonic_results, plausibility_results, plausibility_stats)
    report_path = run_dir / REPORT_MD
    report_path.write_text(report_md, encoding="utf-8")

    payload = {
        "run_dir": str(run_dir),
        "scenarios": [
            {
                "name": res.name,
                "output_dir": res.output_dir,
                "summary_path": res.summary_path,
                "tickets_path": res.tickets_path,
                "config_snapshot": res.config_snapshot,
                "checks": [check.__dict__ for check in (res.checks or [])],
            }
            for res in results
        ],
        "monotonicity": [check.__dict__ for check in monotonic_results],
        "plausibility_checks": [check.__dict__ for check in plausibility_results],
        "plausibility_stats": plausibility_stats,
    }
    checks.write_json_report(str(run_dir / RESULTS_JSON), payload)

    failures = [res for res in results if not res.passed] or [c for c in monotonic_results if not c.passed]
    logging.info("Validation run complete. Report at %s", report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
