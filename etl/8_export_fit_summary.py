"""
- Reads stage-specific distribution fit stats and exports a compact fit_summary.csv
  with rows for each requested stage (default: dev, review, testing).
- Picks the winner by lowest MAE_KDE_PDF (tie -> lower AIC, then lower BIC).
- Parses Parametri strings (e.g. "[ 1.23e-01 -4.56e+02  7.89e+02]") robustly.
- Maps labels to SciPy names + params:
    Lognormale  -> lognorm      (s, loc, scale)
    Weibull     -> weibull_min  (c, loc, scale)
    Esponenziale-> expon        (loc, scale)
    Normale     -> norm         (mu, sigma)
- Writes:  ./etl/output/csv/fit_summary.csv  (rows per stage)
- Logs to:  etl/output/logs/export_fit_summary.log  and stdout

Usage:
  python etl/8_export_fit_summary.py \
    --base-dir ./etl/output/csv \
    --out-csv ./etl/output/csv/fit_summary.csv \
    --stages dev review testing
"""
from __future__ import print_function

import argparse
import ast
import logging
import os
from os import path

import numpy as np
import pandas as pd
from path_config import PROJECT_ROOT

# ---------------------------------------------------------------------
# Py2/3 string type compatibility (fixes "Unresolved reference 'basestring'")
# ---------------------------------------------------------------------
try:
    STRING_TYPES = (basestring,)  # type: ignore  # Py2
except NameError:  # Py3
    STRING_TYPES = (str,)


def setup_logging():
    """Initialize both file and console logging, Py2/3 compatible."""
    logs_dir = path.join(PROJECT_ROOT, "etl", "output", "logs")
    try:
        os.makedirs(logs_dir)
    except OSError:
        if not path.isdir(logs_dir):
            raise

    log_path = path.join(logs_dir, "export_fit_summary.log")

    root = logging.getLogger()
    root.handlers[:] = []
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)

    root.addHandler(fh)
    root.addHandler(sh)

    logging.info("Logger ready. Logfile: %s", log_path)


def parse_params(val):
    """Turn 'Parametri' cell into a list of floats (robust to several formats)."""
    # Already a list/tuple? Try converting elements to float.
    if isinstance(val, (list, tuple)):
        try:
            return [float(x) for x in val]
        except Exception:
            return None

    # Not a string? Bail.
    if not isinstance(val, STRING_TYPES):
        return None

    s = val.strip()
    if not s:
        return None

    # 1) Try Python literal (e.g., "[0.1, -4.5, 7.8]" or "(...)", handles scientific notation)
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return [float(x) for x in obj]
    except Exception:
        pass

    # 2) Numpy parse: space- or comma-separated inside optional brackets
    try:
        s2 = s.strip("[]")
        arr = np.fromstring(s2, sep=" ")
        if arr.size == 0:
            arr = np.fromstring(s2.replace(" ", ""), sep=",")
        return arr.astype(float).tolist() if arr.size > 0 else None
    except Exception:
        return None


def choose_winner(df, metric_col):
    """Index of winner: lowest metric, then lower AIC, then lower BIC."""
    cols = [metric_col]
    if "AIC" in df.columns:
        cols.append("AIC")
    if "BIC" in df.columns:
        cols.append("BIC")
    winner_idx = df.sort_values(by=cols, ascending=True).index[0]
    return winner_idx


def map_to_scipy_row(label, params):
    """Map Italian labels to SciPy dist + param keys expected by the simulator."""
    row = {
        "dist": None,
        "mu": None, "sigma": None, "s": None,
        "c": None, "scale": None, "loc": None
    }

    name = str(label).strip()
    if params is None or len(params) == 0:
        return row

    if name == "Lognormale":
        # [s, loc, scale]
        row["dist"] = "lognorm"
        row["s"] = float(params[0])
        row["loc"] = float(params[1])
        row["scale"] = float(params[2])
        # convenience derivatives (not required by simulator, but useful)
        try:
            row["mu"] = float(np.log(row["scale"])) if row["scale"] > 0 else None
            row["sigma"] = row["s"]
        except Exception:
            pass

    elif name == "Weibull":
        # [c, loc, scale] for scipy.stats.weibull_min
        row["dist"] = "weibull_min"
        row["c"] = float(params[0])
        row["loc"] = float(params[1])
        row["scale"] = float(params[2])

    elif name == "Esponenziale":
        # [loc, scale]
        row["dist"] = "expon"
        row["loc"] = float(params[0])
        row["scale"] = float(params[1])

    else:
        # Unknown label — pass through the name and hope downstream supports it
        row["dist"] = name

    return row


def main():
    setup_logging()

    ap = argparse.ArgumentParser(description="Export compact fit_summary.csv from per-stage distribution_fit_stats files")
    ap.add_argument("--base-dir", default=PROJECT_ROOT + "/etl/output/csv",
                    help="Directory containing distribution_fit_stats_<stage>.csv files")
    ap.add_argument("--out-csv", default=PROJECT_ROOT + "/etl/output/csv/fit_summary.csv")
    ap.add_argument("--stages", nargs="+", default=["dev", "review", "testing"],
                    help="Stages to export; stage names are written verbatim to fit_summary.csv")
    ap.add_argument("--stage-csv", action="append", default=[],
                    help="Optional overrides mapping stage:file (e.g., dev:/tmp/dev.csv). Can be repeated.")
    ap.add_argument("--require-plausible", action="store_true",
                    help="If present, filter to Plausible==True rows before picking winner")
    args = ap.parse_args()

    logging.info("Base dir  : %s", args.base_dir)
    logging.info("Output CSV: %s", args.out_csv)
    logging.info("Stages    : %s", ",".join(args.stages))

    overrides = {}
    for item in args.stage_csv:
        if ":" not in item:
            logging.error("--stage-csv expects stage:/path format; received %s", item)
            raise SystemExit(1)
        stage, csv_path = item.split(":", 1)
        overrides[stage.strip()] = csv_path.strip()

    def _resolve_stage_csv(stage: str) -> str:
        if stage in overrides:
            return overrides[stage]
        aliases = {
            "dev": ["dev", "development"],
            "development": ["development", "dev"],
            "review": ["review", "rev"],
            "rev": ["review", "rev"],
            "testing": ["testing", "test"],
            "test": ["testing", "test"],
        }
        candidates = []
        for name in aliases.get(stage, [stage]):
            candidates.append(path.join(args.base_dir, f"distribution_fit_stats_{name}.csv"))
            candidates.append(path.join(args.base_dir, f"distribution_fit_stats_{name}_duration_days.csv"))
        for cand in candidates:
            if path.exists(cand):
                return cand
        logging.error("No distribution_fit_stats file found for stage %s. Tried: %s", stage, candidates)
        raise SystemExit(1)

    rows = []
    for stage in args.stages:
        stage = stage.strip()
        csv_path = _resolve_stage_csv(stage)
        logging.info("[Stage: %s] Using CSV: %s", stage, csv_path)
        df = pd.read_csv(csv_path)
        logging.info("[Stage: %s] Loaded distribution_fit_stats: rows=%d cols=%d", stage, len(df), len(df.columns))

        metric_col = None
        if "MAE_KDE_PDF" in df.columns:
            metric_col = "MAE_KDE_PDF"
        elif "MSE_KDE_PDF" in df.columns:
            metric_col = "MSE_KDE_PDF"

        need = {"Distribuzione", "Parametri"}
        if metric_col is None or not need.issubset(df.columns):
            missing = set(need) - set(df.columns)
            if metric_col is None:
                missing.add("MAE_KDE_PDF or MSE_KDE_PDF")
            logging.error("Missing required columns %s in %s", missing, csv_path)
            raise SystemExit(1)

        if args.require_plausible and "Plausible" in df.columns:
            before = len(df)
            df = df[df["Plausible"] == True].copy()
            logging.info("[Stage: %s] Plausible filter applied: %d -> %d rows", stage, before, len(df))
            if df.empty:
                logging.error("[Stage: %s] No plausible fits remain; aborting.", stage)
                raise SystemExit(1)

        df["_params"] = df["Parametri"].apply(parse_params)
        bad = int(df["_params"].isna().sum())
        if bad:
            logging.warning("[Stage: %s] Dropping %d rows with unparseable 'Parametri'.", stage, bad)
            df = df[~df["_params"].isna()].copy()
        if df.empty:
            logging.error("[Stage: %s] No usable rows after parsing 'Parametri'.", stage)
            raise SystemExit(1)

        win_idx = choose_winner(df, metric_col)
        win = df.loc[win_idx]
        logging.info("[Stage: %s] Winner: Distribuzione=%s | %s=%.6g | AIC=%s | BIC=%s | Params=%s",
                     stage,
                     str(win.get("Distribuzione")),
                     metric_col,
                     float(win.get(metric_col)),
                     str(win.get("AIC")) if "AIC" in df.columns else "n/a",
                     str(win.get("BIC")) if "BIC" in df.columns else "n/a",
                     str(win.get("_params")))

        core = map_to_scipy_row(win["Distribuzione"], win["_params"])
        row = {
            "stage": stage,
            "is_winner": True,
            "mae": float(win[metric_col]),
            "ks_pvalue": float(win["KS_pvalue"]) if "KS_pvalue" in df.columns and pd.notna(win["KS_pvalue"]) else None,
            "aic": float(win["AIC"]) if "AIC" in df.columns and pd.notna(win["AIC"]) else None,
            "bic": float(win["BIC"]) if "BIC" in df.columns and pd.notna(win["BIC"]) else None,
        }
        row.update(core)
        rows.append(row)

    out = pd.DataFrame(rows)
    out_dir = path.dirname(args.out_csv)
    try:
        os.makedirs(out_dir)
    except OSError:
        if out_dir and not path.exists(out_dir):
            os.makedirs(out_dir)

    out.to_csv(args.out_csv, index=False)
    logging.info("fit_summary.csv saved: %s | rows=%d", args.out_csv, len(out))

    # Echo a small summary to stdout for quick inspection in CI/console
    try:
        print(out.to_string(index=False))
    except Exception:
        print(out.to_dict(orient="records"))


if __name__ == "__main__":
    main()
