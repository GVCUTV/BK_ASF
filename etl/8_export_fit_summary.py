# v3
# file: etl/8_export_fit_summary.py
"""
Create a compact, stage-ready fit_summary.csv from distribution_fit_stats.csv.

- Reads:  ./etl/output/csv/distribution_fit_stats.csv
- Picks the winner by lowest MAE_KDE_PDF (tie -> lower AIC, then lower BIC)
- Parses Parametri strings (e.g. "[ 1.23e-01 -4.56e+02  7.89e+02]") robustly
- Maps labels to SciPy names + params:
    Lognormale -> lognorm (s, loc, scale)
    Weibull    -> weibull_min (c, loc, scale)
    Esponenziale -> expon (loc, scale)
    Normale    -> norm (mu, sigma)
- Writes:  ./etl/output/csv/fit_summary.csv  (rows per --stages)
- Logs to:  output/logs/export_fit_summary.log  and stdout

Usage:
  python etl/export_fit_summary.py \
    --in-csv ./etl/output/csv/distribution_fit_stats.csv \
    --out-csv ./etl/output/csv/fit_summary.csv \
    --stages dev_review testing
"""
from __future__ import print_function

import argparse
import ast
import logging
import os
from os import path
from path_config import PROJECT_ROOT

import numpy as np
import pandas as pd


def setup_logging():
    try:
        os.makedirs("output/logs", exist_ok=True)  # Py3
    except TypeError:
        if not path.exists("output/logs"):         # Py2 fallback
            os.makedirs("output/logs")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler("output/logs/export_fit_summary.log", encoding="utf-8")
                  if hasattr(logging, "FileHandler") else logging.StreamHandler()]
    )
    # Ensure also a stream handler in Py2
    root = logging.getLogger()
    have_stream = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not have_stream:
        root.addHandler(logging.StreamHandler())
    logging.info("Logger ready.")


def parse_params(val):
    """Turn 'Parametri' cell into a list of floats."""
    if isinstance(val, (list, tuple)):
        try:
            return [float(x) for x in val]
        except Exception:
            return None
    if not isinstance(val, basestring if str is bytes else str):  # Py2/3
        return None

    s = val.strip()
    # 1) Try Python literal
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return [float(x) for x in obj]
    except Exception:
        pass

    # 2) Numpy parse: space- or comma-separated inside brackets
    try:
        s2 = s.strip("[]")
        arr = np.fromstring(s2, sep=" ")
        if arr.size == 0:
            arr = np.fromstring(s2.replace(" ", ""), sep=",")
        return arr.astype(float).tolist() if arr.size > 0 else None
    except Exception:
        return None


def choose_winner(df):
    """Idx of winner: lowest MAE_KDE_PDF, then lower AIC, then lower BIC."""
    cols = ["MAE_KDE_PDF"]
    if "AIC" in df.columns:
        cols.append("AIC")
    if "BIC" in df.columns:
        cols.append("BIC")
    return df.sort_values(by=cols, ascending=True).index[0]


def map_to_scipy_row(label, params):
    """Map Italian labels to SciPy dist + param columns."""
    row = {
        "dist": None,
        "mu": None, "sigma": None, "s": None,
        "c": None, "scale": None, "loc": None
    }
    name = str(label).strip()
    if name == "Normale":
        # [mu, sigma]
        row["dist"] = "norm"
        row["mu"], row["sigma"] = float(params[0]), float(params[1])
    elif name == "Lognormale":
        # [s, loc, scale]
        row["dist"] = "lognorm"
        row["s"] = float(params[0]); row["loc"] = float(params[1]); row["scale"] = float(params[2])
        # convenience (optional)
        try:
            row["mu"] = float(np.log(row["scale"])) if row["scale"] > 0 else None
            row["sigma"] = row["s"]
        except Exception:
            pass
    elif name == "Weibull":
        # [c, loc, scale] for weibull_min
        row["dist"] = "weibull_min"
        row["c"] = float(params[0]); row["loc"] = float(params[1]); row["scale"] = float(params[2])
    elif name == "Esponenziale":
        # [loc, scale]
        row["dist"] = "expon"
        row["loc"] = float(params[0]); row["scale"] = float(params[1])
    else:
        row["dist"] = name
    return row


def main():
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", default=PROJECT_ROOT+"/etl/output/csv/distribution_fit_stats.csv")
    ap.add_argument("--out-csv", default=PROJECT_ROOT+"/etl/output/csv/fit_summary.csv")
    ap.add_argument("--stages", nargs="+", default=["dev_review", "testing"])
    ap.add_argument("--require-plausible", action="store_true",
                    help="Filter to Plausible==True rows before picking winner")
    args = ap.parse_args()

    logging.info("Input: %s", args.in_csv)
    if not path.exists(args.in_csv):
        logging.error("File not found: %s", args.in_csv)
        raise SystemExit(1)

    df = pd.read_csv(args.in_csv)
    need = {"Distribuzione", "Parametri", "MAE_KDE_PDF"}
    if not need.issubset(df.columns):
        logging.error("Missing required columns %s in %s", need, args.in_csv)
        raise SystemExit(1)

    if args.require_plausible and "Plausible" in df.columns:
        before = len(df)
        df = df[df["Plausible"] == True].copy()
        logging.info("Plausible filter: %d -> %d rows", before, len(df))
        if df.empty:
            logging.error("No plausible fits remain; aborting.")
            raise SystemExit(1)

    # Parse parameters
    df["_params"] = df["Parametri"].apply(parse_params)
    bad = df["_params"].isna().sum()
    if bad:
        logging.warning("Dropping %d rows with unparseable Parametri.", int(bad))
        df = df[~df["_params"].isna()].copy()
    if df.empty:
        logging.error("No usable rows after parsing Parametri.")
        raise SystemExit(1)

    # Pick winner & map
    win_idx = choose_winner(df)
    win = df.loc[win_idx]
    logging.info("Winner: %s (MAE=%.6g) params=%s", win["Distribuzione"], win["MAE_KDE_PDF"], win["_params"])

    core = map_to_scipy_row(win["Distribuzione"], win["_params"])

    rows = []
    for st in args.stages:
        row = {
            "stage": st,
            "is_winner": True,
            "mae": float(win["MAE_KDE_PDF"]),
            "ks_pvalue": float(win["KS_pvalue"]) if "KS_pvalue" in df.columns and pd.notna(win["KS_pvalue"]) else None,
            "aic": float(win["AIC"]) if "AIC" in df.columns and pd.notna(win["AIC"]) else None,
            "bic": float(win["BIC"]) if "BIC" in df.columns and pd.notna(win["BIC"]) else None,
        }
        row.update(core)
        rows.append(row)

    out = pd.DataFrame(rows)
    out_dir = path.dirname(args.out_csv)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except TypeError:
        if out_dir and not path.exists(out_dir):
            os.makedirs(out_dir)

    out.to_csv(args.out_csv, index=False)
    logging.info("fit_summary.csv saved: %s", args.out_csv)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
