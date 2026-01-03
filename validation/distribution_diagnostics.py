"""
Quick plausibility and drift diagnostics for simulator assumptions versus ETL fits.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from simulation import config as sim_config
from validation import checks

DEFAULT_FIT_PATH = Path("etl/output/csv/fit_summary.csv")
DEFAULT_SERVICE_JSON = Path(sim_config.STATE_PARAMETER_PATHS["service_params"])
DEFAULT_METADATA = Path("validation/baseline_metadata.json")
DEFAULT_OUTPUT = Path("validation/distribution_checks.json")
DEFAULT_PLOT_DIR = Path("validation/plots")


def _render_cli(checks_list: List[checks.CheckResult]) -> str:
    lines = ["Plausibility diagnostics"]
    for item in checks_list:
        status = "PASS" if item.passed else "FAIL"
        lines.append(f"- {status}: {item.name} — {item.details}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run distribution plausibility diagnostics without full validation harness.")
    parser.add_argument("--fit", default=str(DEFAULT_FIT_PATH), help="Path to ETL fit_summary.csv")
    parser.add_argument("--service-json", default=str(DEFAULT_SERVICE_JSON), help="Path to service_params.json")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA), help="Path to baseline_metadata.json")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Where to write distribution_checks.json")
    parser.add_argument("--plot-dir", default=str(DEFAULT_PLOT_DIR), help="Directory for CDF comparison plots")
    parser.add_argument("--samples", type=int, default=50000, help="Samples per distribution (default: 50k)")
    parser.add_argument("--seed", type=int, default=12345, help="Random seed for sampling")
    args = parser.parse_args(argv)

    config_snapshot = sim_config.current_config()

    param_results, param_stats = checks.compare_service_parameters(
        config_snapshot,
        args.fit,
        args.service_json,
        tolerance=checks.DEFAULT_DISTRIBUTION_TOLERANCE,
    )
    dist_results, dist_stats = checks.compare_empirical_distributions(
        config_snapshot,
        args.fit,
        args.service_json,
        sample_size=args.samples,
        rng_seed=args.seed,
        plot_dir=args.plot_dir,
    )
    arrival_results, arrival_stats = checks.validate_arrival_and_feedback(
        config_snapshot,
        args.metadata,
        tolerance=checks.DEFAULT_DISTRIBUTION_TOLERANCE,
    )

    all_results: List[checks.CheckResult] = param_results + dist_results + arrival_results
    stats: Dict[str, Any] = {
        "parameters": param_stats,
        "distributions": dist_stats,
        "arrivals": arrival_stats,
    }

    checks.write_json_report(args.output, stats)
    print(_render_cli(all_results))
    print(f"Detailed stats written to {args.output}")
    if dist_stats.get("plots"):
        print(f"Plots saved under {args.plot_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
