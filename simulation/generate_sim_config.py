# v2
# file: simulation/generate_sim_config.py
"""
Generate simulation/config.py by combining:
- ETL (for ARRIVAL_RATE and feedback probabilities)
- etl/output/csv/fit_summary.csv (for service-time distributions per stage)

Key features:
- Robust datetime handling (UTC-naive) for arrival rate estimation in a chosen window.
- Fallback: if chosen window has 0 arrivals, auto-expand to [min(created), max(created)+1d).
- Feedback probs estimated if ETL has columns (review_rounds, review_rework_flag, ci_failed_then_fix),
  else default to CLI-provided values and log a WARNING.
- Distributions read from fit_summary.csv in SciPy naming with explicit params.

Logging:
- Everything is logged to stdout and to output/logs/generate_sim_config.log

Repo: https://github.com/GVCUTV/BK_ASF.git
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd


# --------------------------- Logging setup --------------------------- #

def _setup_logging() -> None:
    """
    Configure logging to both stdout and a logfile under output/logs/.
    """
    os.makedirs("output/logs", exist_ok=True)
    log_path = "output/logs/generate_sim_config.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    sh = logging.StreamHandler()

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    logging.info("Logger initialized. Logfile: %s", log_path)


# --------------------------- Datetime helpers --------------------------- #

def _to_utc_naive_series(s: pd.Series) -> pd.Series:
    """
    Convert a Series of datetimes to UTC-naive (remove tz) for consistent comparisons.
    """
    s = pd.to_datetime(s, errors="coerce", utc=True)
    return s.dt.tz_convert("UTC").dt.tz_localize(None)


# --------------------------- Arrival rate --------------------------- #

def _estimate_arrival_rate(
    etl_csv: str, created_col: str, window_start: str, window_end: str
) -> Tuple[float, str, str, int]:
    """
    λ (tickets/day) = #created_in_window / days
    If no arrivals in the requested window, fallback to dataset-wide min..max+1d.
    Returns: (lambda, used_start_str, used_end_str, n_created)
    """
    logging.info("Reading ETL: %s", etl_csv)
    df = pd.read_csv(etl_csv)
    if created_col not in df.columns:
        raise SystemExit(f"Missing created column {created_col!r} in {etl_csv}")

    created = _to_utc_naive_series(df[created_col])

    start_ts = pd.to_datetime(window_start)
    end_ts = pd.to_datetime(window_end)
    if not pd.notna(start_ts) or not pd.notna(end_ts) or end_ts <= start_ts:
        raise SystemExit("Invalid window. Ensure window_start < window_end and valid dates.")

    mask = (created >= start_ts) & (created < end_ts)
    n = int(mask.sum())
    days = (end_ts - start_ts).days
    if days <= 0:
        raise SystemExit("Window duration must be positive in days.")

    if n == 0:
        logging.warning("No arrivals in requested window [%s, %s). Falling back to dataset-wide window.", window_start, window_end)
        valid = created.dropna()
        if valid.empty:
            logging.error("All created timestamps are NaT; cannot estimate arrival rate.")
            raise SystemExit(1)
        fb_start = valid.min().normalize()
        fb_end = valid.max().normalize() + timedelta(days=1)
        n = int(((created >= fb_start) & (created < fb_end)).sum())
        days = (fb_end - fb_start).days
        lam = (n / days) if days > 0 else 0.0
        logging.info("Fallback window [%s, %s): n=%d, days=%d, λ=%.6f/day", fb_start.date(), fb_end.date(), n, days, lam)
        return lam, fb_start.strftime("%Y-%m-%d"), fb_end.strftime("%Y-%m-%d"), n

    lam = n / days
    logging.info("Requested window [%s, %s): n=%d, days=%d, λ=%.6f/day", window_start, window_end, n, days, lam)
    return lam, window_start, window_end, n


# --------------------------- Feedback probabilities --------------------------- #

def _estimate_feedback_probs(
    etl_csv: str,
    review_rounds_col: str | None,
    review_flag_col: str | None,
    ci_fail_fix_col: str | None,
    default_p_dev: float,
    default_p_test: float,
) -> Tuple[float, float]:
    """
    Estimate feedback probabilities from ETL, falling back to defaults otherwise.
    - FEEDBACK_P_DEV: fraction with review rework (rounds > 1) OR review_flag truthy.
    - FEEDBACK_P_TEST: fraction with CI/QA fail+fix flag truthy.
    """
    df = pd.read_csv(etl_csv)

    p_dev = None
    if review_rounds_col and review_rounds_col in df.columns:
        rr = pd.to_numeric(df[review_rounds_col], errors="coerce")
        if rr.notna().any():
            p_dev = float((rr.dropna() > 1).mean())
            logging.info("FEEDBACK_P_DEV from %r (review_rounds > 1): %.6f", review_rounds_col, p_dev)

    if p_dev is None and review_flag_col and review_flag_col in df.columns:
        rf = df[review_flag_col].astype(str).str.strip().str.lower()
        if rf.notna().any():
            p_dev = float(rf.isin({"true", "1", "yes", "y"}).mean())
            logging.info("FEEDBACK_P_DEV from %r (truthy fraction): %.6f", review_flag_col, p_dev)

    if p_dev is None:
        p_dev = default_p_dev
        logging.warning("Could not estimate FEEDBACK_P_DEV from ETL; using default=%.4f", p_dev)

    p_test = None
    if ci_fail_fix_col and ci_fail_fix_col in df.columns:
        cf = df[ci_fail_fix_col].astype(str).str.strip().str.lower()
        if cf.notna().any():
            p_test = float(cf.isin({"true", "1", "yes", "y"}).mean())
            logging.info("FEEDBACK_P_TEST from %r (truthy fraction): %.6f", ci_fail_fix_col, p_test)

    if p_test is None:
        p_test = default_p_test
        logging.warning("Could not estimate FEEDBACK_P_TEST from ETL; using default=%.4f", p_test)

    return p_dev, p_test


# --------------------------- Read fit_summary --------------------------- #

def _read_fit_summary(path: str) -> Dict[str, Tuple[str, dict]]:
    """
    Read fit_summary.csv and build: stage -> (dist_name, params_dict)
    SciPy names supported: lognorm (s, scale, loc), weibull_min (c, scale, loc),
    expon (scale, loc), norm (loc, scale).
    """
    logging.info("Reading fit_summary: %s", path)
    if not os.path.exists(path):
        logging.error("fit_summary.csv not found: %s", path)
        raise SystemExit(1)

    df = pd.read_csv(path)
    need = {"stage", "dist"}
    if not need.issubset(df.columns):
        logging.error("fit_summary.csv must contain at least columns %s; found %s", need, list(df.columns))
        raise SystemExit(1)

    mapping: Dict[str, Tuple[str, dict]] = {}
    for _, r in df.iterrows():
        stage = str(r["stage"]).strip()
        dist = str(r["dist"]).strip().lower()
        params = {}

        try:
            if dist == "lognorm":
                params = {"s": float(r["s"]), "scale": float(r["scale"]), "loc": float(r["loc"])}
            elif dist in ("weibull_min", "weibull"):
                params = {"c": float(r["c"]), "scale": float(r["scale"]), "loc": float(r["loc"])}
                dist = "weibull_min"
            elif dist in ("expon", "exponential"):
                params = {"scale": float(r["scale"]), "loc": float(r["loc"])}
                dist = "expon"
            elif dist in ("norm", "normal"):
                params = {"loc": float(r["mu"]), "scale": float(r["sigma"])}
                dist = "norm"
            else:
                logging.error("Unsupported distribution in fit_summary: %s", dist)
                raise SystemExit(1)
        except KeyError as e:
            logging.error("Missing parameter column %s for dist=%s in fit_summary.", e, dist)
            raise SystemExit(1)

        mapping[stage] = (dist, params)
        logging.info("Stage %r -> %s %s", stage, dist, json.dumps(params))

    if not mapping:
        logging.error("fit_summary.csv appears empty or invalid.")
        raise SystemExit(1)

    return mapping


# --------------------------- Write config.py --------------------------- #

_CONFIG_TEMPLATE = """# v2
# file: simulation/config.py

\"\"\"
Central configuration for simulation parameters.
All times are in DAYS. Arrival rate is tickets per DAY.
Distributions are SciPy-style with explicit params (shape/scale/loc) and include 'loc' if a sliding fit was selected.
Generated automatically by simulation/generate_sim_config.py on {gen_ts}.
Repo: https://github.com/GVCUTV/BK_ASF.git
\"\"\"

# ----------------------------- General ----------------------------- #
SIM_DURATION = {sim_duration:.6f}  # days of simulated time

# ----------------------------- Logging ----------------------------- #
LOG_FILE = "logs/simulation.log"

# --------------------------- Arrival process --------------------------- #
# Estimated from ETL data in window [{win_start} .. {win_end})
ARRIVAL_RATE = {arrival_rate:.10f}  # tickets/day (lambda)

# --------------------------- Service capacity --------------------------- #
# Calibrated to observed capacity or tuned to keep utilizations reasonable
N_DEVS = {n_devs}
N_TESTERS = {n_testers}

# --------------------------- Feedback probabilities --------------------------- #
# Estimated from ETL (review/test cycles); defaults used if columns not available
FEEDBACK_P_DEV  = {p_dev:.10f}   # after Dev/Review
FEEDBACK_P_TEST = {p_test:.10f}   # after Testing

# --------------------------- Service time distributions --------------------------- #
# Names follow SciPy; params are explicit and include 'loc' (shift), if any.
SERVICE_TIME_PARAMS = {{
    "dev_review": {{
        "dist": "{dev_dist}",
        "params": {dev_params}
    }},
    "testing": {{
        "dist": "{test_dist}",
        "params": {test_params}
    }}
}}
"""

def _write_config(
    out_path: str,
    sim_duration_days: float,
    win_start: str,
    win_end: str,
    arrival_rate: float,
    n_devs: int,
    n_testers: int,
    p_dev: float,
    p_test: float,
    dev_dist_name: str,
    dev_params: dict,
    test_dist_name: str,
    test_params: dict,
) -> None:
    """
    Render and write simulation/config.py from the collected pieces.
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    content = _CONFIG_TEMPLATE.format(
        gen_ts=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        sim_duration=sim_duration_days,
        win_start=win_start,
        win_end=win_end,
        arrival_rate=arrival_rate,
        n_devs=n_devs,
        n_testers=n_testers,
        p_dev=p_dev,
        p_test=p_test,
        dev_dist=dev_dist_name,
        dev_params=json.dumps(dev_params),
        test_dist=test_dist_name,
        test_params=json.dumps(test_params),
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    logging.info("Configuration written: %s", out_path)


# --------------------------- CLI --------------------------- #

def main() -> None:
    _setup_logging()

    ap = argparse.ArgumentParser(description="Generate simulation/config.py from ETL + fit_summary.csv")
    ap.add_argument("--etl-csv", default="../etl/output/csv/tickets_prs_merged.csv", help="ETL merged CSV path")
    ap.add_argument("--fit-csv", default="../etl/output/csv/fit_summary.csv", help="Path to fit_summary.csv")
    ap.add_argument("--created-col", default="fields.created", help="Creation timestamp column in ETL")
    ap.add_argument("--window-start", default="2024-01-01", help="Arrival-rate window start (inclusive)")
    ap.add_argument("--window-end", default="2025-01-01", help="Arrival-rate window end (exclusive)")

    ap.add_argument("--default-p-dev", type=float, default=0.20, help="Fallback FEEDBACK_P_DEV if not estimable")
    ap.add_argument("--default-p-test", type=float, default=0.15, help="Fallback FEEDBACK_P_TEST if not estimable")
    ap.add_argument("--review-rounds-col", default="review_rounds", help="Optional: review rounds int (>1 means rework)")
    ap.add_argument("--review-flag-col", default="review_rework_flag", help="Optional: boolean-ish rework flag")
    ap.add_argument("--ci-fail-fix-col", default="ci_failed_then_fix", help="Optional: boolean-ish CI/QA fail+fix flag")

    ap.add_argument("--sim-duration-days", type=float, default=365.0, help="Simulation horizon (days)")
    ap.add_argument("--n-devs", type=int, default=3, help="Parallel servers at Dev/Review stage")
    ap.add_argument("--n-testers", type=int, default=2, help="Parallel servers at Testing stage")

    ap.add_argument("--config-out", default="simulation/config.py", help="Where to write the generated config.py")

    args = ap.parse_args()
    logging.info("CLI args: %s", vars(args))

    # 1) Arrival rate λ (tickets/day)
    lam, used_start, used_end, n_created = _estimate_arrival_rate(
        args.etl_csv, args.created_col, args.window_start, args.window_end
    )

    # 2) Feedback probabilities
    p_dev, p_test = _estimate_feedback_probs(
        etl_csv=args.etl_csv,
        review_rounds_col=args.review_rounds_col,
        review_flag_col=args.review_flag_col,
        ci_fail_fix_col=args.ci_fail_fix_col,
        default_p_dev=args.default_p_dev,
        default_p_test=args.default_p_test,
    )

    # 3) Fit summary (per-stage distributions → SciPy params)
    fits = _read_fit_summary(args.fit_csv)
    dev_fit = fits.get("dev_review") or next(iter(fits.values()))
    test_fit = fits.get("testing") or next(iter(fits.values()))
    logging.info("Using dev_review fit: %s %s", dev_fit[0], json.dumps(dev_fit[1]))
    logging.info("Using testing    fit: %s %s", test_fit[0], json.dumps(test_fit[1]))

    # 4) Write config.py
    _write_config(
        out_path=args.config_out,
        sim_duration_days=args.sim_duration_days,
        win_start=used_start,
        win_end=used_end,
        arrival_rate=lam,
        n_devs=args.n_devs,
        n_testers=args.n_testers,
        p_dev=p_dev,
        p_test=p_test,
        dev_dist_name=dev_fit[0],
        dev_params=dev_fit[1],
        test_dist_name=test_fit[0],
        test_params=test_fit[1],
    )

    logging.info("Done. Inspect %s and logs for details.", args.config_out)


if __name__ == "__main__":
    main()
