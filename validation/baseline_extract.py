"""
Generate empirical baseline metrics aligned with simulator KPIs.

Outputs
- validation/baseline_metrics.csv : metric-aligned vector with confidence intervals.
- validation/baseline_metadata.json: provenance, hashes, config snapshot.

The script relies on ETL outputs (tickets_prs_merged.csv, fit_summary.csv) and
captures a snapshot of the current simulator configuration for reproducibility.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple
import sys

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _resolve_path(path_like: Path | str) -> Path:
    """Return an absolute path anchored at the project root when needed."""

    path = Path(path_like).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


from simulation import config as sim_config

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "validation" / "baseline_config.yaml"


@dataclasses.dataclass
class BaselineConfig:
    input_csv: Path
    fit_summary_csv: Path
    output_metrics_csv: Path
    output_metadata_json: Path
    random_seed: int = 12345
    bootstrap_samples: int = 500
    ci_level: float = 0.95
    stage_columns: Dict[str, str] = dataclasses.field(default_factory=lambda: {
        "dev": "dev_duration_days",
        "review": "review_duration_days",
        "testing": "test_duration_days",
    })
    rework_flags: Dict[str, str] = dataclasses.field(default_factory=lambda: {
        "review": "review_rework_flag",
        "testing": "ci_failed_then_fix",
    })
    window_override: Tuple[str, str] | None = None

    @classmethod
    def from_file(cls, path: Path) -> "BaselineConfig":
        config_path = _resolve_path(path)
        with open(config_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        merged = {
            **dataclasses.asdict(
                cls(
                    input_csv=_resolve_path("etl/output/csv/tickets_prs_merged.csv"),
                    fit_summary_csv=_resolve_path("etl/output/csv/fit_summary.csv"),
                    output_metrics_csv=_resolve_path("validation/baseline_metrics.csv"),
                    output_metadata_json=_resolve_path("validation/baseline_metadata.json"),
                )
            ),
            **raw,
        }
        if merged.get("window_override"):
            win = merged["window_override"]
            merged["window_override"] = (win[0], win[1])
        merged["input_csv"] = _resolve_path(merged["input_csv"])
        merged["fit_summary_csv"] = _resolve_path(merged["fit_summary_csv"])
        merged["output_metrics_csv"] = _resolve_path(merged["output_metrics_csv"])
        merged["output_metadata_json"] = _resolve_path(merged["output_metadata_json"])
        return cls(**merged)


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def bootstrap_mean_ci(series: pd.Series, samples: int, seed: int, ci: float) -> Tuple[float, float]:
    data = series.dropna().to_numpy()
    if len(data) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = rng.choice(data, size=(samples, len(data)), replace=True).mean(axis=1)
    alpha = (1 - ci) / 2
    lower = float(np.quantile(draws, alpha))
    upper = float(np.quantile(draws, 1 - alpha))
    return lower, upper


def safe_window(created: pd.Series, resolved: pd.Series, override: Tuple[str, str] | None) -> Tuple[datetime, datetime]:
    if override:
        return pd.to_datetime(override[0]).to_pydatetime(), pd.to_datetime(override[1]).to_pydatetime()
    created_dt = pd.to_datetime(created, errors="coerce", utc=True).dropna()
    resolved_dt = pd.to_datetime(resolved, errors="coerce", utc=True).dropna()
    if created_dt.empty:
        raise ValueError("No valid created timestamps found in input CSV")
    window_start = created_dt.min().to_pydatetime()
    window_end = max(created_dt.max(), resolved_dt.max() if not resolved_dt.empty else created_dt.max()).to_pydatetime()
    return window_start, window_end


def rate_confidence_interval(count: int, denom: int, ci: float) -> Tuple[float, float]:
    if denom == 0:
        return float("nan"), float("nan")
    p = count / denom
    if count == 0 or count == denom:
        return p, p
    se = (p * (1 - p) / denom) ** 0.5
    z = 1.96 if abs(ci - 0.95) < 1e-9 else scipy_norm_z(ci)
    return p - z * se, p + z * se


def poisson_rate_ci(count: int, window_days: float, ci: float) -> Tuple[float, float]:
    if window_days <= 0:
        return float("nan"), float("nan")
    if count == 0:
        return 0.0, 0.0
    se = (count ** 0.5) / window_days
    z = 1.96 if abs(ci - 0.95) < 1e-9 else scipy_norm_z(ci)
    rate = count / window_days
    return rate - z * se, rate + z * se


def scipy_norm_z(ci: float) -> float:
    from scipy.stats import norm  # localized import to avoid top-level dependency in environments without SciPy

    alpha = 1 - ci
    return float(norm.ppf(1 - alpha / 2))


def compute_arrival_and_closure(df: pd.DataFrame, cfg: BaselineConfig) -> Dict[str, Any]:
    if "fields.created" in df.columns:
        created = df["fields.created"]
    elif "created" in df.columns:
        created = df["created"]
    else:
        raise ValueError("No created column found in input CSV")

    if "fields.resolutiondate" in df.columns:
        resolved = df["fields.resolutiondate"]
    else:
        resolved = df.get("resolved", pd.Series([], dtype="datetime64[ns]"))

    window_start, window_end = safe_window(created, resolved, cfg.window_override)
    window_days = max((window_end - window_start).total_seconds() / 86400.0, 1e-9)

    created_dt = pd.to_datetime(created, errors="coerce", utc=True).dropna()
    resolved_dt = pd.to_datetime(resolved, errors="coerce", utc=True).dropna()
    arrivals = len(created_dt)
    closures = len(resolved_dt)

    arrival_rate = arrivals / window_days
    closure_rate = closures / arrivals if arrivals else float("nan")
    closure_ci = rate_confidence_interval(closures, arrivals, cfg.ci_level)

    throughput_closed_ci = poisson_rate_ci(closures, window_days, cfg.ci_level)

    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "window_days": window_days,
        "arrivals": arrivals,
        "closures": closures,
        "arrival_rate": arrival_rate,
        "closure_rate": closure_rate,
        "closure_rate_ci": closure_ci,
        "throughput_closed": closures / window_days if window_days else float("nan"),
        "throughput_closed_ci": throughput_closed_ci,
    }


def compute_stage_summaries(df: pd.DataFrame, cfg: BaselineConfig, window_days: float) -> Dict[str, Dict[str, Any]]:
    summaries: Dict[str, Dict[str, Any]] = {}
    for stage, column in cfg.stage_columns.items():
        if column not in df.columns:
            continue
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        series = series[series >= 0]
        count = int(series.count())
        if count == 0:
            continue
        mean = float(series.mean())
        median = float(series.median())
        p95 = float(series.quantile(0.95))
        lower_ci, upper_ci = bootstrap_mean_ci(series, cfg.bootstrap_samples, cfg.random_seed, cfg.ci_level)

        throughput = count / window_days if window_days > 0 else float("nan")
        th_ci = poisson_rate_ci(count, window_days, cfg.ci_level)

        rework_flag_col = cfg.rework_flags.get(stage)
        rework_rate = float("nan")
        rework_n = 0
        if rework_flag_col and rework_flag_col in df.columns:
            flag_series = df[rework_flag_col]
            if flag_series.dtype == bool:
                rework_bool = flag_series
            else:
                str_vals = flag_series.astype(str).str.lower()
                rework_bool = str_vals.isin(["true", "1", "yes", "y", "1.0"])
            rework_n = int(rework_bool.sum())
            rework_rate = float(rework_bool.mean())
        summaries[stage] = {
            "count": count,
            "mean": mean,
            "median": median,
            "p95": p95,
            "mean_ci": (lower_ci, upper_ci),
            "throughput": throughput,
            "throughput_ci": th_ci,
            "rework_rate": rework_rate,
            "rework_count": rework_n,
        }
    return summaries


def load_fit_summary(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    rows: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        stage = str(row.get("stage")).strip().lower()
        rows[stage] = row.to_dict()
    return rows


def build_metrics_vector(arrival_info: Dict[str, Any], stage_info: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    records = []
    # Arrival and closure level metrics
    records.append({
        "metric": "arrival_rate",
        "value": arrival_info["arrival_rate"],
        "units": "tickets/day",
        "source": "ETL arrivals",
        "note": "Created tickets per day over empirical window",
        "ci_low": float("nan"),
        "ci_high": float("nan"),
    })
    records.append({
        "metric": "closure_rate",
        "value": arrival_info.get("closure_rate"),
        "units": "fraction",
        "source": "ETL closures",
        "note": "Resolved divided by created",
        "ci_low": arrival_info.get("closure_rate_ci", (float("nan"), float("nan")))[0],
        "ci_high": arrival_info.get("closure_rate_ci", (float("nan"), float("nan")))[1],
    })
    records.append({
        "metric": "throughput_closed",
        "value": arrival_info.get("throughput_closed"),
        "units": "tickets/day",
        "source": "ETL closures",
        "note": "Completion rate per day (all stages)",
        "ci_low": arrival_info.get("throughput_closed_ci", (float("nan"), float("nan")))[0],
        "ci_high": arrival_info.get("throughput_closed_ci", (float("nan"), float("nan")))[1],
    })

    for stage, stats in stage_info.items():
        records.append({
            "metric": f"throughput_{stage}",
            "value": stats.get("throughput"),
            "units": "tickets/day",
            "source": "ETL stage durations",
            "note": "Stage completions per day (non-null durations)",
            "ci_low": stats.get("throughput_ci", (float("nan"), float("nan")))[0],
            "ci_high": stats.get("throughput_ci", (float("nan"), float("nan")))[1],
        })
        # Queue waits not observable; store placeholder to align with simulator metrics
        records.append({
            "metric": f"avg_wait_{stage}",
            "value": float("nan"),
            "units": "days",
            "source": "not_observed",
            "note": "Queue waits not captured in ETL; requires simulation",
            "ci_low": float("nan"),
            "ci_high": float("nan"),
        })
        records.append({
            "metric": f"avg_queue_length_{stage}",
            "value": float("nan"),
            "units": "tickets",
            "source": "not_observed",
            "note": "Queue lengths require simulation; unavailable in ETL",
            "ci_low": float("nan"),
            "ci_high": float("nan"),
        })
        records.append({
            "metric": f"utilization_{stage}",
            "value": float("nan"),
            "units": "fraction",
            "source": "not_observed",
            "note": "Server utilization not directly observable; use simulation",
            "ci_low": float("nan"),
            "ci_high": float("nan"),
        })
        records.append({
            "metric": f"rework_rate_{stage}",
            "value": stats.get("rework_rate", float("nan")),
            "units": "fraction",
            "source": "ETL proxy",
            "note": "Proxy from rework flags when available",
            "ci_low": float("nan"),
            "ci_high": float("nan"),
        })
    return pd.DataFrame.from_records(records)


def collect_metadata(cfg: BaselineConfig, arrival_info: Dict[str, Any], stage_info: Dict[str, Dict[str, Any]], fit_rows: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    state_paths = sim_config.STATE_PARAMETER_PATHS
    state_hashes = {
        "matrix_P": sha256sum(Path(state_paths["matrix_P"])),
        "service_params": sha256sum(Path(state_paths["service_params"])),
        "stint_pmfs": {Path(p).name: sha256sum(Path(p)) for p in state_paths["stint_pmfs"]},
    }
    def _replace_nan(obj: Any) -> Any:
        if isinstance(obj, float) and np.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: _replace_nan(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_replace_nan(v) for v in obj]
        return obj

    meta = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "config": dataclasses.asdict(cfg),
        "arrival_info": arrival_info,
        "stage_info": _replace_nan(stage_info),
        "fit_summary": _replace_nan(fit_rows),
        "input_hashes": {
            "tickets_prs_merged.csv": sha256sum(cfg.input_csv),
            "fit_summary.csv": sha256sum(cfg.fit_summary_csv),
        },
        "state_parameter_hashes": state_hashes,
        "sim_config_snapshot": sim_config.current_config(),
        "random_seed": cfg.random_seed,
    }
    return meta


def run(config_path: Path) -> None:
    cfg = BaselineConfig.from_file(config_path)
    np.random.seed(cfg.random_seed)

    df = pd.read_csv(cfg.input_csv)
    arrival_info = compute_arrival_and_closure(df, cfg)
    stage_info = compute_stage_summaries(df, cfg, arrival_info["window_days"])
    fit_rows = load_fit_summary(cfg.fit_summary_csv)

    metrics_df = build_metrics_vector(arrival_info, stage_info)
    cfg.output_metrics_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(cfg.output_metrics_csv, index=False)

    metadata = collect_metadata(cfg, arrival_info, stage_info, fit_rows)
    cfg.output_metadata_json.parent.mkdir(parents=True, exist_ok=True)
    cfg.output_metadata_json.write_text(json.dumps(metadata, indent=2, default=str))

    print(metrics_df.to_string(index=False))
    print(f"\nSaved metrics to {cfg.output_metrics_csv} and metadata to {cfg.output_metadata_json}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract empirical baselines aligned with simulator metrics")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="Path to baseline_config.yaml")
    args = parser.parse_args()
    run(Path(args.config))
