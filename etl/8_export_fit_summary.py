# v2
# file: etl/export_fit_summary.py
"""
Export a compact, stage-ready `fit_summary.csv` for the simulator, starting from
`etl/output/csv/distribution_fit_stats.csv` produced by 7_fit_distributions.py.

What this script does:
- Reads the detailed stats table (one row per candidate distribution).
- Parses the "Parametri" column robustly (strings like "[ 8.14e-01 -6.96e+02  1.20e+03]" etc.).
- Picks the WINNER by lowest MAE_KDE_PDF (ties broken with lower AIC, then lower BIC).
- Writes `etl/output/csv/fit_summary.csv` with rows per stage you pass via --stages.
  Each row uses SciPy naming and explicit parameter fields: dist, (mu/sigma) or (s/loc/scale) or (c/loc/scale).
- Logs every operation to stdout and to output/logs/export_fit_summary.log.

Usage:
  python etl/export_fit_summary.py \
    --in-csv ./etl/output/csv/distribution_fit_stats.csv \
    --out-csv ./etl/output/csv/fit_summary.csv \
    --stages dev_review testing

Repo: https://github.com/GVCUTV/BK_ASF.git
"""

from __future__ import annotations

import argparse
import ast
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


# --------------------------- Logging setup --------------------------- #

def _setup_logging() -> None:
    """
    Configure logging to both stdout and a rotating logfile under output/logs/.
    """
    os.makedirs("output/logs", exist_ok=True)
    log_path = "output/logs/export_fit_summary.log"

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


# --------------------------- Helpers --------------------------- #

def _parse_params_field(val: object) -> Optional[List[float]]:
    """
    Parse the 'Parametri' field into a list of floats.

    Accepts:
      - Python-literal lists like "[0.81, -696.7, 1209.06]"
      - Space-separated bracket arrays like "[ 8.14e-01 -6.96e+02  1.20e+03]"
    Returns list[float] or None if parsing fails.
    """
    if isinstance(val, (list, tuple)):
        try:
            return [float(x) for x in val]
        except Exception:
            return None
    if not isinstance(val, str):
        return None

    s = val.strip()
    # Try Python literal first
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return [float(x) for x in obj]
    except Exception:
        pass

    # Fallback: strip brackets and parse with numpy.fromstring (handles spaces/commas)
    try:
        s2 = s.strip("[]")
        arr = np.fromstring(s2, sep=" ")
        if arr.size == 0:
            # Try with comma separator
            arr = np.fromstring(s2.replace(" ", ""), sep=",")
        return arr.astype(float).tolist() if arr.size > 0 else None
    except Exception:
        return None


def _choose_winner(df: pd.DataFrame) -> int:
    """
    Choose the winner by lowest MAE_KDE_PDF.
    Tie-break 1: lower AIC, Tie-break 2: lower BIC.
    Returns the winning row index.
    """
    sort_cols = ["MAE_KDE_PDF"]
    aux_cols = []
    if "AIC" in df.columns:
        aux_cols.append("AIC")
    if "BIC" in df.columns:
        aux_cols.append("BIC")
    sort_cols.extend(aux_cols)
    winner_idx = df.sort_values(by=sort_cols, ascending=True).index[0]
    return int(winner_idx)


def _map_to_scipy_row(dist_label: str, params: List[float]) -> dict:
    """
    Map our candidate label + params to SciPy-compatible naming.
    Supported labels in distribution_fit_stats.csv:
      - 'Lognormale' -> lognorm, params [s, loc, scale]
      - 'Weibull'    -> weibull_min, params [c, loc, scale]
      - 'Esponenziale' -> expon, params [loc, scale]
      - 'Normale'    -> norm, params [mu, sigma]
    """
    row = {
        "dist": None,
        "mu": None, "sigma": None, "s": None,
        "shape": None, "c": None,
        "scale": None, "loc": None,
    }

    name = str(dist_label).strip()
    if name == "Normale":
        # [mu, sigma]
        row["dist"] = "norm"
        row["mu"] = float(params[0])
        row["sigma"] = float(params[1])
    elif name == "Lognormale":
        # [s, loc, scale]
        row["dist"] = "lognorm"
        row["s"] = float(params[0])
        row["loc"] = float(params[1])
        row["scale"] = float(params[2])
        # Optional convenience values (mu = log(scale), sigma = s)
        row["mu"] = float(np.log(row["scale"])) if row["scale"] > 0 else None
        row["sigma"] = row["s"]
    elif name == "Weibull":
        # [c, loc, scale] for weibull_min
        row["dist"] = "weibull_min"
        row["c"] = float(params[0])
        row["loc"] = float(params[1])
        row["scale"] = float(params[2])
        row["shape"] = row["c"]
    elif name == "Esponenziale":
        # [loc, scale]
        row["dist"] = "expon"
        row["loc"] = float(params[0])
        row["scale"] = float(params[1])
    else:
        # Unknown label: keep the raw name, no param mapping
        row["dist"] = name

    return row


# --------------------------- Main logic --------------------------- #

def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(description="Export stage-ready fit_summary.csv from detailed fit stats.")
    parser.add_argument("--in-csv", default="./etl/output/csv/distribution_fit_stats.csv",
                        help="Input CSV from 7_fit_distributions.py")
    parser.add_argument("--out-csv", default="./etl/output/csv/fit_summary.csv",
                        help="Output CSV consumed by simulation/generate_sim_config.py")
    parser.add_argument("--stages", nargs="+", default=["dev_review", "testing"],
                        help="Stages to export (winner duplicated per stage)")
    parser.add_argument("--require-plausible", action="store_true",
                        help="If set, consider only rows with Plausible==True; else consider all")
    args = parser.parse_args()

    logging.info("Reading input CSV: %s", args.in_csv)
    if not os.path.exists(args.in_csv):
        logging.error("Input file does not exist: %s", args.in_csv)
        raise SystemExit(1)

    df = pd.read_csv(args.in_csv)

    required = {"Distribuzione", "Parametri", "MAE_KDE_PDF"}
    if not required.issubset(df.columns):
        logging.error("Missing required columns in %s. Found: %s", args.in_csv, list(df.columns))
        raise SystemExit(1)

    # Optionally filter for plausible fits
    if args.require_plausible and "Plausible" in df.columns:
        before = len(df)
        df = df[df["Plausible"] == True].copy()
        logging.info("Filtered plausible rows: %d -> %d", before, len(df))
        if df.empty:
            logging.error("No plausible rows left after filtering. Remove --require-plausible or check inputs.")
            raise SystemExit(1)

    # Parse Parametri field robustly
    logging.info("Parsing Parametri field into numeric lists …")
    df["_params"] = df["Parametri"].apply(_parse_params_field)
    if df["_params"].isna().any():
        bad = df[df["_params"].isna()]
        logging.warning("Some rows failed parameter parsing; will ignore these rows:\n%s", bad[["Distribuzione", "Parametri"]].to_string(index=False))
        df = df[~df["_params"].isna()].copy()
    if df.empty:
        logging.error("No usable rows after parameter parsing. Aborting.")
        raise SystemExit(1)

    # Choose winner
    winner_idx = _choose_winner(df)
    win = df.loc[winner_idx]
    logging.info("Winner: %s (MAE=%.6g) params=%s", win["Distribuzione"], win["MAE_KDE_PDF"], win["_params"])

    # Map to SciPy columns
    row_core = _map_to_scipy_row(str(win["Distribuzione"]), list(win["_params"]))

    # Compose final rows per stage
    rows = []
    for stage in args.stages:
        out_row = {
            "stage": stage,
            "is_winner": True,
            "mae": float(win["MAE_KDE_PDF"]),
            "aic": float(win["AIC"]) if "AIC" in df.columns and pd.notna(win["AIC"]) else None,
            "bic": float(win["BIC"]) if "BIC" in df.columns and pd.notna(win["BIC"]) else None,
            "ks_pvalue": float(win["KS_pvalue"]) if "KS_pvalue" in df.columns and pd.notna(win["KS_pvalue"]) else None,
        }
        out_row.update(row_core)
        rows.append(out_row)

    out = pd.DataFrame(rows)
    Path(os.path.dirname(args.out_csv)).mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)
    logging.info("fit_summary.csv saved: %s", args.out_csv)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
