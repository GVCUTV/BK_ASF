"""Validation helpers for simulation consistency checks."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np

from simulation.run_sweeps import parse_value

SUMMARY_FILENAME = "summary_stats.csv"
TICKETS_FILENAME = "tickets_stats.csv"
DEFAULT_DISTRIBUTION_TOLERANCE = 0.05


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


def load_fit_summary(path: str) -> Dict[str, Dict[str, Any]]:
    """Load ETL fit summary rows keyed by stage."""

    import csv

    fits: Dict[str, Dict[str, Any]] = {}
    last_stage: str | None = None
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            stage = (row.get("stage") or "").strip().lower()
            target_stage = stage or last_stage
            if not target_stage:
                continue
            record = fits.setdefault(target_stage, {})
            for key, value in row.items():
                if key == "stage":
                    continue
                parsed = parse_value(value or "")
                if parsed != "":
                    record[key] = parsed
            last_stage = target_stage
    return fits


def load_service_params(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    params: Dict[str, Dict[str, Any]] = {}
    for stage, cfg in payload.get("parameters", {}).items():
        params[stage.lower()] = cfg
    return params


def _mean(values: Iterable[float]) -> float:
    vals = [v for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return float(sum(vals) / len(vals)) if vals else 0.0


def _approx_equal(a: float, b: float, rel: float, abs_tol: float) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(1.0, abs(a), abs(b)))


def _ks_statistic(sample_a: np.ndarray, sample_b: np.ndarray) -> float:
    """Compute a two-sample KS statistic without SciPy."""

    a_sorted = np.sort(sample_a)
    b_sorted = np.sort(sample_b)
    data = np.concatenate([a_sorted, b_sorted])
    data.sort()

    cdf_a = np.searchsorted(a_sorted, data, side="right") / a_sorted.size
    cdf_b = np.searchsorted(b_sorted, data, side="right") / b_sorted.size
    return float(np.max(np.abs(cdf_a - cdf_b)))


def _draw_sample(dist_type: str, params: Dict[str, Any], rng: np.random.Generator) -> float:
    """Sample from a limited subset of SciPy-style parameterizations."""

    dist_type = dist_type.lower()
    loc = float(params.get("loc", 0.0))

    if dist_type in {"lognorm", "lognormal"}:
        sigma = params.get("s") if params.get("s") is not None else params.get("sigma")
        if sigma is None:
            raise ValueError("Lognormal distribution requires 's' or 'sigma' parameter.")
        if params.get("mu") is not None:
            mu = float(params["mu"])
        else:
            scale = params.get("scale", 1.0)
            mu = math.log(scale) if scale > 0 else 0.0
        sample = rng.lognormal(mean=mu, sigma=float(sigma))
        return float(max(1e-12, sample + loc))

    if dist_type in {"weibull", "weibull_min"}:
        shape = params.get("shape") if params.get("shape") is not None else params.get("c")
        if shape is None:
            raise ValueError("Weibull distribution requires 'shape' or 'c' parameter.")
        scale = float(params.get("scale", 1.0))
        sample = rng.weibull(float(shape)) * scale + loc
        return float(max(1e-12, sample))

    raise ValueError(f"Unsupported distribution for plausibility check: {dist_type}")


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


def check_baseline(
    summary: Dict[str, Any],
    baseline: Dict[str, Any],
    rel_tol: float,
    abs_tol: float,
    ticket_rows: List[Dict[str, Any]] | None = None,
) -> List[CheckResult]:
    results: List[CheckResult] = []
    ticket_means: Dict[str, float] | None = None
    if ticket_rows is not None:
        ticket_means = aggregate_ticket_means(ticket_rows)
    for metric, expected in baseline.items():
        if metric == "mean_total_wait" and ticket_means is not None:
            observed = ticket_means.get("mean_total_wait")
        else:
            observed = summary.get(metric)
        if expected is None or expected == "":
            continue
        if not isinstance(expected, (int, float)) or observed is None or not isinstance(observed, (int, float)):
            continue
        passed = _approx_equal(observed, expected, rel_tol, abs_tol)
        details = f"observed={observed}, expected={expected}"
        results.append(CheckResult(f"Baseline: {metric}", passed, details))
    return results


def _normalize_config_service_params(service_cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for stage, cfg in service_cfg.items():
        params = dict(cfg.get("params", {})) if isinstance(cfg, dict) else {}
        dist = (cfg.get("dist") or "").lower() if isinstance(cfg, dict) else ""
        if dist in {"lognorm", "lognormal"}:
            sigma = params.get("s") if params.get("s") is not None else params.get("sigma")
            if sigma is not None and params.get("mu") is None and params.get("scale") is not None:
                try:
                    params["mu"] = math.log(float(params["scale"]))
                except ValueError:
                    params["mu"] = None
            params["sigma"] = sigma
        normalized[stage.lower()] = {"dist": dist, "params": params}
    return normalized


def _extract_etl_params(
    etl_fit: Dict[str, Dict[str, Any]],
    service_params_json: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for stage, fit in etl_fit.items():
        dist = (fit.get("dist") or "").lower()
        params: Dict[str, Any] = {k: v for k, v in fit.items() if k not in {"stage", "dist", "is_winner"}}
        if dist in {"lognorm", "lognormal"} and params.get("mu") is None and params.get("scale"):
            params["mu"] = math.log(float(params["scale"])) if params.get("scale") else None
        merged[stage] = {"dist": dist, "params": params}

    # If the ETL fit omitted mu/sigma (e.g., legacy lognormal JSON), fall back to service_params.json
    for stage, cfg in service_params_json.items():
        lower = stage.lower()
        if lower not in merged:
            continue
        if merged[lower]["dist"] in {"", None}:
            merged[lower]["dist"] = (cfg.get("distribution") or cfg.get("dist") or "").lower()
        params = merged[lower].setdefault("params", {})
        if merged[lower]["dist"] in {"lognorm", "lognormal"}:
            params.setdefault("mu", cfg.get("mu"))
            params.setdefault("sigma", cfg.get("sigma"))
            if params.get("scale") is None and cfg.get("mu") is not None:
                params["scale"] = math.exp(float(cfg["mu"]))
    return merged


def aggregate_ticket_means(tickets: List[Dict[str, Any]]) -> Dict[str, float]:
    waits = [float(row.get("total_wait", 0.0)) for row in tickets if isinstance(row.get("total_wait"), (int, float))]
    times = [float(row.get("time_in_system", 0.0)) for row in tickets if isinstance(row.get("time_in_system"), (int, float))]
    return {
        "mean_total_wait": _mean(waits),
        "mean_time_in_system": _mean(times),
    }


def _relative_change(current: float, reference: float) -> float:
    if reference == 0:
        return math.inf if current != 0 else 0.0
    return abs(current - reference) / abs(reference)


def compare_service_parameters(
    config_snapshot: Dict[str, Any],
    etl_fit_path: str,
    service_param_json_path: str,
    tolerance: float = DEFAULT_DISTRIBUTION_TOLERANCE,
) -> Tuple[List[CheckResult], Dict[str, Any]]:
    """Compare configured service-time parameters with ETL-derived fits."""

    service_cfg = _normalize_config_service_params(config_snapshot.get("SERVICE_TIME_PARAMS", {}))
    etl_fit = load_fit_summary(etl_fit_path)
    etl_params = _extract_etl_params(etl_fit, load_service_params(service_param_json_path))

    results: List[CheckResult] = []
    stats: Dict[str, Any] = {"stage": {}, "tolerance": tolerance}
    for stage, cfg in service_cfg.items():
        observed = cfg
        reference = etl_params.get(stage)
        if reference is None:
            results.append(CheckResult(f"Service params {stage}", False, "Missing ETL reference"))
            continue

        dist_match = observed.get("dist") == reference.get("dist")
        if not dist_match:
            results.append(
                CheckResult(
                    f"Service params {stage}",
                    False,
                    f"Distribution mismatch: config={observed.get('dist')} vs etl={reference.get('dist')}",
                )
            )
        else:
            results.append(
                CheckResult(
                    f"Service params {stage} dist",
                    True,
                    f"Distribution {observed.get('dist')}",
                )
            )

        param_details: Dict[str, Any] = {"config": observed, "etl": reference}
        params_ok = True
        for field in ["mu", "sigma", "scale", "c", "shape"]:
            cfg_val = observed.get("params", {}).get(field)
            ref_val = reference.get("params", {}).get(field)
            if cfg_val is None or ref_val is None:
                continue
            delta = _relative_change(float(cfg_val), float(ref_val))
            param_details[field] = {"config": cfg_val, "etl": ref_val, "relative_change": delta}
            if delta > tolerance:
                params_ok = False
        stats["stage"][stage] = param_details
        if reference.get("params"):
            results.append(
                CheckResult(
                    f"Service params {stage} values",
                    params_ok,
                    f"Relative drift within {tolerance*100:.1f}% threshold",
                )
            )
    return results, stats


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


def compare_empirical_distributions(
    config_snapshot: Dict[str, Any],
    etl_fit_path: str,
    service_param_json_path: str,
    sample_size: int = 50000,
    rng_seed: int = 12345,
    plot_dir: str | None = None,
) -> Tuple[List[CheckResult], Dict[str, Any]]:
    """Sample simulator distributions against ETL fits and compute KS/quantiles."""

    service_cfg = _normalize_config_service_params(config_snapshot.get("SERVICE_TIME_PARAMS", {}))
    etl_fit = load_fit_summary(etl_fit_path)
    etl_params = _extract_etl_params(etl_fit, load_service_params(service_param_json_path))

    rng_config = np.random.default_rng(rng_seed)
    rng_etl = np.random.default_rng(rng_seed + 1)
    results: List[CheckResult] = []
    stats: Dict[str, Any] = {"rng_seed": rng_seed, "sample_size": sample_size, "stages": {}}

    try:
        import matplotlib.pyplot as plt

        plotting_enabled = True
    except Exception:  # pragma: no cover - optional dependency
        plotting_enabled = False

    plot_paths: List[str] = []

    for stage, cfg in service_cfg.items():
        etl = etl_params.get(stage)
        if not etl:
            results.append(CheckResult(f"Distribution samples {stage}", False, "Missing ETL fit"))
            continue

        config_params = cfg.get("params", {})
        etl_params_stage = etl.get("params", {})
        config_samples = np.array([_draw_sample(cfg.get("dist", ""), config_params, rng_config) for _ in range(sample_size)])
        etl_samples = np.array([_draw_sample(etl.get("dist", ""), etl_params_stage, rng_etl) for _ in range(sample_size)])

        ks_stat = _ks_statistic(config_samples, etl_samples)
        quantiles = [0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
        config_q = np.quantile(config_samples, quantiles).tolist()
        etl_q = np.quantile(etl_samples, quantiles).tolist()

        stats["stages"][stage] = {
            "ks_stat": ks_stat,
            "quantiles": {str(q): {"config": c, "etl": e} for q, c, e in zip(quantiles, config_q, etl_q)},
        }
        results.append(
            CheckResult(
                f"KS distance {stage}",
                ks_stat <= 0.2,
                f"ks={ks_stat:.4f} (<=0.2 threshold)",
            )
        )

        if plotting_enabled and plot_dir:
            Path(plot_dir).mkdir(parents=True, exist_ok=True)
            plt.figure(figsize=(6, 4))
            x_vals = np.linspace(0, np.quantile(np.concatenate([config_samples, etl_samples]), 0.99), 200)
            config_cdf = [np.mean(config_samples <= x) for x in x_vals]
            etl_cdf = [np.mean(etl_samples <= x) for x in x_vals]
            plt.plot(x_vals, config_cdf, label="sim config", color="tab:blue")
            plt.plot(x_vals, etl_cdf, label="etl fit", color="tab:orange")
            plt.title(f"CDF comparison — {stage}")
            plt.xlabel("Service time (days)")
            plt.ylabel("CDF")
            plt.legend()
            plot_path = Path(plot_dir) / f"service_distribution_comparison_{stage}.png"
            plt.tight_layout()
            plt.savefig(plot_path)
            plt.close()
            plot_paths.append(str(plot_path))

    if plot_paths:
        stats["plots"] = plot_paths
    return results, stats


def validate_arrival_and_feedback(
    config_snapshot: Dict[str, Any],
    baseline_metadata_path: str,
    tolerance: float = DEFAULT_DISTRIBUTION_TOLERANCE,
) -> Tuple[List[CheckResult], Dict[str, Any]]:
    with open(baseline_metadata_path, "r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    arrival_rate_etl = metadata.get("arrival_info", {}).get("arrival_rate")
    stage_info = metadata.get("stage_info", {})

    results: List[CheckResult] = []
    stats: Dict[str, Any] = {}

    if isinstance(arrival_rate_etl, (int, float)):
        arrival_rate_cfg = config_snapshot.get("ARRIVAL_RATE")
        delta = _relative_change(float(arrival_rate_cfg), float(arrival_rate_etl)) if arrival_rate_cfg else math.inf
        stats["arrival_rate"] = {
            "config": arrival_rate_cfg,
            "etl": arrival_rate_etl,
            "relative_change": delta,
        }
        results.append(
            CheckResult(
                "Arrival rate plausibility",
                delta <= tolerance,
                f"config={arrival_rate_cfg}, etl={arrival_rate_etl}, rel_change={delta:.3f}",
            )
        )

    # Feedback probabilities bounded by observed rework rates (if present)
    for key, cfg_field, meta_field in [
        ("DEV", "FEEDBACK_P_DEV", "rework_rate"),
        ("TEST", "FEEDBACK_P_TEST", "rework_rate"),
    ]:
        cfg_val = config_snapshot.get(cfg_field)
        meta = stage_info.get(key.lower()) or stage_info.get(key) or {}
        observed = meta.get(meta_field)
        if isinstance(cfg_val, (int, float)):
            stats[f"feedback_{key.lower()}"] = {"config": cfg_val, "observed": observed}
            if isinstance(observed, (int, float)):
                results.append(
                    CheckResult(
                        f"Feedback {key} plausibility",
                        cfg_val <= observed + tolerance,
                        f"config={cfg_val}, observed={observed}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        f"Feedback {key} plausibility",
                        cfg_val <= tolerance,
                        f"config={cfg_val}, observed unavailable (using tolerance {tolerance})",
                    )
                )

    return results, stats


def write_json_report(path: str, results: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
