# v7
# file: simulation/generate_sim_config.py
"""
Data-only config generator with exhaustive logging.

Changes vs v5:
- Still fails if a required metric can't be derived, BUT:
  • Broader auto-detection for review/CI fields (matches what 8_enrich_feedback_cols.py creates).
  • Clear diagnostics that show top-50 column names when failing, so you know what to add.
- N_DEVS / N_TESTERS computed from distinct identities in-window (data-only).
- Logs every step to stdout and output/logs/generate_sim_config.log.

Usage:
  from path_config import PROJECT_ROOT
  python simulation/generate_sim_config.py \
    --etl-csv  $PROJECT_ROOT/etl/output/csv/tickets_prs_merged.csv \
    --fit-csv  $PROJECT_ROOT/etl/output/csv/fit_summary.csv \
    --config-out $PROJECT_ROOT/simulation/config.py
"""
from __future__ import print_function

import argparse
import glob
import json
import logging
import os
import sys
from datetime import timedelta, datetime
from os import path

import numpy as np
import pandas as pd

SCRIPT_DIR = path.dirname(path.abspath(__file__))
PROJECT_ROOT = path.abspath(path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from path_config import PROJECT_ROOT as _PROJECT_ROOT
    PROJECT_ROOT = _PROJECT_ROOT
except Exception:
    logging.getLogger(__name__).warning(
        "Falling back to inferred PROJECT_ROOT=%s; unable to import path_config", PROJECT_ROOT
    )


# --------------------------- logging --------------------------- #

def _safe_mkdirs(d):
    try:
        os.makedirs(d)
    except OSError:
        if not path.isdir(d):
            raise

def _setup_logging(level_str):
    logs_dir = path.join("output", "logs")
    _safe_mkdirs(logs_dir)
    log_path = path.join(logs_dir, "generate_sim_config.log")

    root = logging.getLogger()
    root.handlers[:] = []
    lvl = getattr(logging, str(level_str).upper(), logging.INFO)
    root.setLevel(lvl)

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt); fh.setLevel(lvl)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt); sh.setLevel(lvl)
    root.addHandler(fh); root.addHandler(sh)

    logging.info("Logger initialized. Logfile: %s", log_path)
    return log_path


# --------------------------- helpers --------------------------- #

def _to_utc_naive(s):
    ser = pd.to_datetime(s, errors="coerce", utc=True)
    return ser.dt.tz_convert("UTC").dt.tz_localize(None)

def _finite_params(d):
    for k, v in d.items():
        try:
            if not np.isfinite(float(v)):
                return False
        except Exception:
            return False
    return True

def _fail(msg, df=None):
    logging.error(msg)
    if df is not None:
        cols = list(df.columns)
        logging.error("Available columns (first 50): %s", cols[:50])
    raise SystemExit(1)


# --------------------------- state parameter inputs --------------------------- #

STATE_PARAMETER_DIR = path.join(PROJECT_ROOT, "data", "state_parameters")


def _require_file(abs_path, description):
    if not path.isfile(abs_path):
        _fail(f"Missing {description}: {abs_path}")
    logging.info("Validated %s: %s", description, abs_path)
    return abs_path


def collect_state_parameter_paths():
    if not path.isdir(STATE_PARAMETER_DIR):
        _fail(f"Missing state parameter directory: {STATE_PARAMETER_DIR}")

    matrix_path = _require_file(path.join(STATE_PARAMETER_DIR, "matrix_P.csv"), "matrix transition file")
    service_params_path = _require_file(path.join(STATE_PARAMETER_DIR, "service_params.json"), "service parameter json")

    stint_glob = sorted(glob.glob(path.join(STATE_PARAMETER_DIR, "stint_PMF_*.csv")))
    if not stint_glob:
        _fail("No stint_PMF_*.csv files found in state parameter directory.")
    for fpath in stint_glob:
        _require_file(fpath, f"stint PMF {path.basename(fpath)}")

    rel = lambda p: path.relpath(p, PROJECT_ROOT).replace("\\", "/")
    state_paths = {
        "matrix_P": rel(matrix_path),
        "service_params": rel(service_params_path),
        "stint_pmfs": [rel(p) for p in stint_glob],
    }
    logging.info("Collected state parameter paths: %s", state_paths)
    return state_paths


# --------------------------- reproducibility --------------------------- #

SEED_OVERRIDE_ENV_VAR = "SIMULATION_RANDOM_SEED"
DEFAULT_RANDOM_SEEDS = {
    "global": 22015001,
    "arrivals": 22015002,
    "service": 22015003,
    "state": 22015004,
}


# --------------------------- arrivals --------------------------- #

def estimate_arrival_rate(df, created_col, window_start, window_end):
    if created_col not in df.columns:
        _fail("Missing created column %r in ETL." % created_col, df)
    created = _to_utc_naive(df[created_col])
    start_ts = pd.to_datetime(window_start); end_ts = pd.to_datetime(window_end)
    if not pd.notna(start_ts) or not pd.notna(end_ts) or end_ts <= start_ts:
        _fail("Invalid window: %s .. %s" % (window_start, window_end))
    mask = (created >= start_ts) & (created < end_ts)
    n = int(mask.sum()); days = (end_ts - start_ts).days
    if days <= 0: _fail("Window duration must be >0 days.")
    if n == 0:
        valid = created.dropna()
        if valid.empty: _fail("All created timestamps are NaT; cannot estimate λ.", df)
        fb_start = valid.min().normalize(); fb_end = valid.max().normalize() + pd.Timedelta(days=1)
        n = int(((created >= fb_start) & (created < fb_end)).sum()); days = (fb_end - fb_start).days
        lam = (n/float(days)) if days>0 else 0.0
        logging.info("Using dataset-wide window [%s, %s): n=%d days=%d λ=%.6f/day", fb_start.date(), fb_end.date(), n, days, lam)
        return lam, str(fb_start.date()), str(fb_end.date()), n
    lam = n/float(days)
    logging.info("Using requested window [%s, %s): n=%d days=%d λ=%.6f/day", window_start, window_end, n, days, lam)
    return lam, window_start, window_end, n


# --------------------------- feedback --------------------------- #

DEV_NUMERIC_CANDS   = ["review_rounds", "pr_review_rounds", "requested_changes_count", "reviews_count"]
DEV_FLAG_CANDS      = ["review_rework_flag", "reopened_flag", "requested_changes_flag"]
DEV_STRINGLIST_CANDS= ["pull_request_review_states","review_states","pr_review_states","review_decisions","requested_changes_states"]

TEST_BOOL_CANDS     = ["ci_failed_then_fix","ci_failed","build_failed","qa_failed_flag"]
TEST_LIST_CANDS     = ["check_runs_conclusions","ci_status_history","combined_statuses",
                       "workflow_conclusions","build_state_history","statuses",
                       "ci_conclusion","check_suite_conclusion","build_conclusion"]

FAIL_TOKENS   = {"fail", "failure", "failed", "error", "timed_out", "timeout", "cancelled", "canceled", "aborted", "broken"}
SUCCESS_TOKENS= {"success", "succeeded", "passed", "ok", "green", "completed_success"}

def _truthy_fraction(series):
    s = series.astype(str).str.strip().str.lower()
    return float(s.isin({"true","1","yes","y","t"}).mean())

def _to_listish(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return []
    s = str(val).strip()
    if not s: return []
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
        try:
            import ast
            obj = ast.literal_eval(s)
            if isinstance(obj, (list, tuple)):
                return [str(x).strip() for x in obj]
        except Exception:
            pass
    for sep in [";", ",", "|", " "]:
        if sep in s:
            return [t.strip() for t in s.split(sep) if t.strip()]
    return [s]

def _has_fail_then_success(tokens):
    toks = [t.lower() for t in tokens]
    seen_fail = False
    for t in toks:
        if any(k in t for k in FAIL_TOKENS): seen_fail = True
        if seen_fail and any(k in t for k in SUCCESS_TOKENS): return True
    return False

def estimate_feedback(df, created_col, start_str, end_str):
    created = _to_utc_naive(df[created_col])
    start_ts, end_ts = pd.to_datetime(start_str), pd.to_datetime(end_str)
    wdf = df[(created >= start_ts) & (created < end_ts)].copy()
    logging.info("Feedback window slice size: %d", len(wdf))

    # p_dev
    p_dev = None
    for c in DEV_NUMERIC_CANDS:
        if c in wdf.columns:
            rr = pd.to_numeric(wdf[c], errors="coerce")
            if rr.notna().any():
                p = float((rr.dropna() > 1).mean())
                logging.info("p_dev via numeric %s: %.6f", c, p)
                p_dev = max(p_dev, p) if p_dev is not None else p
    for c in DEV_FLAG_CANDS:
        if c in wdf.columns:
            p = _truthy_fraction(wdf[c])
            logging.info("p_dev via flag %s: %.6f", c, p)
            p_dev = max(p_dev, p) if p_dev is not None else p
    if p_dev is None:
        # string/state lists → changes_requested implies at least 1 rework
        for c in DEV_STRINGLIST_CANDS:
            if c in wdf.columns:
                flags = wdf[c].apply(_to_listish).apply(
                    lambda lst: any("changes_requested" in str(x).lower() for x in lst)
                )
                p = float(flags.mean())
                logging.info("p_dev via stringlist %s: %.6f", c, p)
                p_dev = max(p_dev, p) if p_dev is not None else p
    if p_dev is None:
        _fail("Cannot compute FEEDBACK_P_DEV from data. Expected one of %s or %s or %s"
              % (DEV_NUMERIC_CANDS, DEV_FLAG_CANDS, DEV_STRINGLIST_CANDS), wdf)

    # p_test
    p_test = None
    for c in TEST_BOOL_CANDS:
        if c in wdf.columns:
            p = _truthy_fraction(wdf[c])
            logging.info("p_test via bool %s: %.6f", c, p)
            p_test = max(p_test, p) if p_test is not None else p
    if p_test is None:
        # scan lists for fail→success
        agg = None
        for c in TEST_LIST_CANDS:
            if c in wdf.columns:
                series = wdf[c].apply(_to_listish)
                flags = series.apply(_has_fail_then_success)
                p = float(flags.mean())
                logging.info("p_test via list %s: %.6f", c, p)
                agg = flags if agg is None else (agg | flags)
                p_test = max(p_test, p) if p_test is not None else p
        if p_test is None and agg is not None:
            p_test = float(agg.mean())
    if p_test is None:
        _fail("Cannot compute FEEDBACK_P_TEST from data. Expected one of %s or %s"
              % (TEST_BOOL_CANDS, TEST_LIST_CANDS), wdf)

    return p_dev, p_test


# --------------------------- capacity --------------------------- #

DEV_ID_CANDS  = ["dev_user","author_login","pr_author_login","fields.assignee","assignee","developer"]
TEST_ID_CANDS = ["tester","ci_runner","ci_agent","jenkins_node","build_agent","runner_name","runner_id","qa_user","testing_user"]
TESTER_HEURISTIC_RATIO = 0.5

def _count_distinct(series):
    s = series.dropna().astype(str).str.strip()
    s = s[s!=""]
    return int(s.nunique())

def infer_capacity(df, created_col, start_str, end_str):
    created = _to_utc_naive(df[created_col])
    start_ts, end_ts = pd.to_datetime(start_str), pd.to_datetime(end_str)
    wdf = df[(created >= start_ts) & (created < end_ts)].copy()

    dev_counts = []
    for c in DEV_ID_CANDS:
        if c in wdf.columns:
            cnt = _count_distinct(wdf[c]); dev_counts.append((c, cnt))
            logging.info("DEV id column %-20s -> distinct: %d", c, cnt)
    if not dev_counts:
        _fail("Cannot infer N_DEVS: add one of %s to ETL (e.g., via 8_enrich_feedback_cols.py)." % DEV_ID_CANDS, wdf)
    dev_counts.sort(key=lambda x: x[1], reverse=True)
    dev_col, n_devs = dev_counts[0]
    if n_devs <= 0:
        _fail("Cannot infer N_DEVS: %s has 0 distinct ids in window." % dev_col)

    test_counts = []
    for c in TEST_ID_CANDS:
        if c in wdf.columns:
            cnt = _count_distinct(wdf[c]); test_counts.append((c, cnt))
            logging.info("TEST id column %-20s -> distinct: %d", c, cnt)
    if not test_counts:
        n_testers = max(1, int(round(max(1.0, n_devs * TESTER_HEURISTIC_RATIO))))
        logging.warning(
            "Cannot infer N_TESTERS from ETL columns %s; defaulting to heuristic ratio %.2f -> %d testers.",
            TEST_ID_CANDS,
            TESTER_HEURISTIC_RATIO,
            n_testers,
        )
        logging.info("Selected DEV column='%s' -> N_DEVS=%d | TEST column='%s' -> N_TESTERS=%d", dev_col, n_devs, "heuristic_ratio", n_testers)
        return n_devs, n_testers, dev_col, "heuristic_ratio"
    test_counts.sort(key=lambda x: x[1], reverse=True)
    test_col, n_testers = test_counts[0]
    if n_testers <= 0:
        _fail("Cannot infer N_TESTERS: %s has 0 distinct ids in window." % test_col)

    logging.info("Selected DEV column='%s' -> N_DEVS=%d | TEST column='%s' -> N_TESTERS=%d", dev_col, n_devs, test_col, n_testers)
    return n_devs, n_testers, dev_col, test_col


# --------------------------- fits --------------------------- #

def read_fit_summary(fit_csv):
    logging.info("Reading fit_summary: %s", fit_csv)
    if not os.path.exists(fit_csv):
        _fail("fit_summary.csv not found: %s" % fit_csv)
    df = pd.read_csv(fit_csv)
    need = {"stage","dist"}
    if not need.issubset(df.columns):
        _fail("fit_summary.csv must contain %s" % need, df)
    fits = {}
    for _, r in df.iterrows():
        stage = str(r["stage"]).strip().lower()
        dist  = str(r["dist"]).strip().lower()
        if dist == "lognorm":
            params = {"s": float(r["s"]), "loc": float(r["loc"]), "scale": float(r["scale"])}
        elif dist in ("weibull_min","weibull"):
            params = {"c": float(r["c"]), "loc": float(r["loc"]), "scale": float(r["scale"])}
            dist = "weibull_min"
        elif dist in ("expon","exponential"):
            params = {"loc": float(r["loc"]), "scale": float(r["scale"])}
            dist = "expon"
        elif dist in ("norm","normal"):
            params = {"loc": float(r["mu"]), "scale": float(r["sigma"])}
            dist = "norm"
        else:
            _fail("Unsupported dist in fit_summary: %s" % dist)
        if not _finite_params(params):
            _fail("Non-finite params for stage=%s dist=%s: %s" % (stage, dist, json.dumps(params)))
        fits[stage] = (dist, params)
        logging.info("Stage %r -> %s %s", stage, dist, json.dumps(params))
    if not fits:
        _fail("fit_summary.csv empty or invalid.", df)
    return fits

def pick_stage(fits, candidates):
    for c in candidates:
        if c in fits:
            logging.info("Stage selected: %s", c)
            return fits[c]
    _fail(f"Candidates {candidates} not found in fit_summary. Available stages: {sorted(fits.keys())}")


# --------------------------- template --------------------------- #

CONFIG_TEMPLATE = """# v3
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
# Derived from ETL distinct actors in the same window
N_DEVS = {n_devs}        # source={dev_source_col}
N_TESTERS = {n_testers}  # source={test_source_col}

# --------------------------- Feedback probabilities --------------------------- #
# Estimated from ETL within the same window
FEEDBACK_P_DEV  = {p_dev:.10f}
FEEDBACK_P_TEST = {p_test:.10f}

# --------------------------- Service time distributions --------------------------- #
# Names follow SciPy; params are explicit and include 'loc' (shift), if any.
SERVICE_TIME_PARAMS = {{
    "dev": {{
        "dist": "{dev_dist}",
        "params": {dev_params}
    }},
    "review": {{
        "dist": "{review_dist}",
        "params": {review_params}
    }},
    "testing": {{
        "dist": "{test_dist}",
        "params": {test_params}
    }}
}}

# --------------------------- State parameter inputs --------------------------- #
STATE_PARAMETER_PATHS = {state_paths}

# --------------------------- Random seeds --------------------------- #
GLOBAL_RANDOM_SEED = {global_seed}
SEED_OVERRIDE_ENV_VAR = "{seed_env_var}"
ARRIVAL_STREAM_SEED = {arrival_seed}
SERVICE_TIME_STREAM_SEED = {service_seed}
STATE_TRANSITION_STREAM_SEED = {state_seed}
"""


# --------------------------- main --------------------------- #

def main():
    ap = argparse.ArgumentParser(description="Generate simulation/config.py (data-only).")
    ap.add_argument("--log-level", default="INFO")
    ap.add_argument("--etl-csv", default=PROJECT_ROOT + "/etl/output/csv/tickets_prs_merged.csv")
    ap.add_argument("--fit-csv", default=PROJECT_ROOT + "/etl/output/csv/fit_summary.csv")
    ap.add_argument("--created-col", default="fields.created")
    ap.add_argument("--window-start", default="2024-01-01")
    ap.add_argument("--window-end",   default="2025-01-01")
    ap.add_argument("--config-out",   default=PROJECT_ROOT + "/simulation/config.py")
    ap.add_argument("--sim-duration-days", type=float, default=365.0)
    args = ap.parse_args()

    _setup_logging(args.log_level)
    logging.info("PROJECT_ROOT: %s", PROJECT_ROOT)
    logging.info("CLI args: %s", vars(args))

    etl = pd.read_csv(args.etl_csv)
    logging.info("ETL shape: %s", etl.shape)

    # 1) λ
    lam, used_start, used_end, _ = estimate_arrival_rate(etl, args.created_col, args.window_start, args.window_end)

    # 2) feedback (data only)
    p_dev, p_test = estimate_feedback(etl, args.created_col, used_start, used_end)

    # 3) capacity (data only)
    n_devs, n_testers, dev_src, test_src = infer_capacity(etl, args.created_col, used_start, used_end)

    # 4) fits
    fits = read_fit_summary(args.fit_csv)
    dev_fit = pick_stage(fits, ["dev", "development"])
    review_fit = pick_stage(fits, ["review", "rev", "development", "dev"])
    test_fit = pick_stage(fits, ["testing", "qa", "ci", "test"])
    state_paths = collect_state_parameter_paths()

    # 5) render
    out_dir = path.dirname(args.config_out)
    if out_dir: _safe_mkdirs(out_dir)
    content = CONFIG_TEMPLATE.format(
        gen_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        sim_duration=args.sim_duration_days,
        win_start=used_start, win_end=used_end,
        arrival_rate=lam,
        n_devs=n_devs, n_testers=n_testers,
        dev_source_col=dev_src, test_source_col=test_src,
        p_dev=p_dev, p_test=p_test,
        dev_dist=dev_fit[0], dev_params=json.dumps(dev_fit[1]),
        review_dist=review_fit[0], review_params=json.dumps(review_fit[1]),
        test_dist=test_fit[0], test_params=json.dumps(test_fit[1]),
        state_paths=json.dumps(state_paths, indent=4, sort_keys=True),
        global_seed=DEFAULT_RANDOM_SEEDS["global"],
        seed_env_var=SEED_OVERRIDE_ENV_VAR,
        arrival_seed=DEFAULT_RANDOM_SEEDS["arrivals"],
        service_seed=DEFAULT_RANDOM_SEEDS["service"],
        state_seed=DEFAULT_RANDOM_SEEDS["state"],
    )
    with open(args.config_out, "w") as f:
        f.write(content)
    logging.info("Configuration written: %s", args.config_out)


if __name__ == "__main__":
    main()
