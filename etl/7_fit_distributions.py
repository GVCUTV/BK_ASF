# v10
# file: 7_fit_distributions.py

"""
Fit, slide (loc), and compare candidate distributions on resolution times, then
EXPORT a standardized `fit_summary.csv` usable by the simulation config generator.

What this script does (v10):
- Loads the unified ETL dataset and extracts the resolution time column.
- Fits candidate distributions (Lognormal, Weibull(min), Exponential, Normal),
  optimizing slide (loc) and other parameters against the KDE of the data
  to minimize MAE between KDE and the model PDF.
- Computes KS p-value, AIC, BIC, mean, std, plausibility flags.
- ALWAYS prints/logs the WINNER (lowest MAE).
- Saves detailed per-distribution stats to:   ./etl/output/csv/distribution_fit_stats.csv
- NEW: writes a compact ./etl/output/csv/fit_summary.csv with rows per stage
       (e.g., dev_review, testing) using SciPy naming and explicit parameter fields.
       By default, when you only have end-to-end resolution times, the same winner
       is exported for both stages (duplicate rows) as a placeholder for Meeting 5.
       Later you can pass dedicated stage columns to fit them separately.
- Saves PNG overlays into ./etl/output/png/ (if requested).

Usage (examples):
    python etl/7_fit_distributions.py --input ./etl/output/csv/tickets_prs_merged.csv \
        --time-col resolution_time_hours --outdir ./etl/output \
        --stages dev_review testing

Optional (compute durations from Jira fields):
    python etl/7_fit_distributions.py --input ./etl/output/csv/tickets_prs_merged.csv \
        --created-col fields.created --resolved-col fields.resolutiondate --unit hours \
        --outdir ./etl/output --stages dev_review testing

Optional (stage-specific columns):
    python etl/7_fit_distributions.py --input ... --stage-cols dev_review_hours testing_hours --stages dev_review testing

Repo: https://github.com/GVCUTV/BK_ASF.git
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from math import exp, log, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as stats
from scipy.optimize import curve_fit
from scipy.special import gamma as gammafn


# --------------------------- Logging --------------------------- #

def setup_logging(outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "csv").mkdir(parents=True, exist_ok=True)
    (outdir / "png").mkdir(parents=True, exist_ok=True)
    (Path('output') / 'logs').mkdir(parents=True, exist_ok=True)

    log_path = Path('output/logs/fit_distributions.log')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, encoding='utf-8')
    sh = logging.StreamHandler()
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    logging.info("Logger ready. Logfile: %s", log_path)


# ----------------------- Helpers & metrics ---------------------- #

def kde_on_grid(data: np.ndarray, grid: np.ndarray) -> np.ndarray:
    kde = stats.gaussian_kde(data)
    return kde(grid)

def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))

def compute_mean_std(dist_name: str, params: list[float]) -> tuple[float, float]:
    # Expect parameterization consistent with how we fit:
    #   Lognormale  -> [s, loc, scale] with scale = exp(mu), s = sigma
    #   Weibull     -> [c, loc, scale] (weibull_min)
    #   Esponenziale-> [loc, scale]
    #   Normale     -> [mu, sigma]
    if dist_name == 'Normale':
        mu, sigma = params
        return mu, sigma
    elif dist_name == 'Lognormale':
        s, loc, scale = params
        mu = log(scale)
        sigma = s
        mean = exp(mu + sigma**2 / 2)
        std = sqrt((exp(sigma**2) - 1) * exp(2*mu + sigma**2))
        return mean, std
    elif dist_name == 'Weibull':
        c, loc, scale = params
        mean = scale * gammafn(1 + 1/c)
        std = scale * sqrt(float(gammafn(1 + 2/c) - gammafn(1 + 1/c)**2))
        return mean, std
    elif dist_name == 'Esponenziale':
        loc, scale = params
        return loc + scale, scale
    return float('nan'), float('nan')

def compute_information_criteria(dist_obj, params: list[float], data: np.ndarray) -> tuple[float, float, float]:
    # KS p-value + AIC + BIC using the log-likelihood from the pdf
    try:
        if dist_obj is stats.norm:
            mu, sigma = params
            ll = np.sum(dist_obj.logpdf(data, loc=mu, scale=sigma))
            k = 2
        elif dist_obj is stats.lognorm:
            s, loc, scale = params
            ll = np.sum(dist_obj.logpdf(data, s, loc=loc, scale=scale))
            k = 3
        elif dist_obj is stats.weibull_min:
            c, loc, scale = params
            ll = np.sum(dist_obj.logpdf(data, c, loc=loc, scale=scale))
            k = 3
        elif dist_obj is stats.expon:
            loc, scale = params
            ll = np.sum(dist_obj.logpdf(data, loc=loc, scale=scale))
            k = 2
        else:
            return np.nan, np.nan, np.nan
        ks_stat, ks_p = stats.kstest(data, dist_obj.name, args=tuple(params))
        aic = 2 * k - 2 * ll
        bic = k * np.log(len(data)) - 2 * ll
        return float(ks_p), float(aic), float(bic)
    except Exception as e:
        logging.exception("Failed IC computation: %s", e)
        return np.nan, np.nan, np.nan

def robust_curve_fit(pdf_func, x: np.ndarray, y: np.ndarray, p0, bounds):
    try:
        popt, _ = curve_fit(pdf_func, x, y, p0=p0, bounds=bounds, maxfev=20000)
        return popt.tolist()
    except Exception as e:
        logging.warning("curve_fit failed: %s", e)
        return None

def plausibility(emp_mean, emp_std, fit_mean, fit_std, tol=5.0):
    # mark implausible if too far from empirical moments
    if any(map(lambda v: v is None or np.isnan(v), [fit_mean, fit_std])):
        return False
    return (abs(fit_mean - emp_mean) <= tol * emp_std) and (abs(fit_std - emp_std) <= tol * emp_std)


# ----------------------- Fitting core -------------------------- #

def fit_single_series(series: pd.Series, label_prefix: str, png_dir: Path, save_png: bool):
    data = series.dropna().to_numpy(dtype=float)
    data = data[np.isfinite(data)]
    data = data[(data > 0)]
    if data.size < 10:
        raise ValueError(f"Too few valid samples in {label_prefix}: need >=10, found {data.size}")

    x = np.linspace(data.min(), data.max(), 1000)
    kde_y = kde_on_grid(data, x)
    emp_mean, emp_std = float(np.mean(data)), float(np.std(data, ddof=1))

    candidates = {
        'Lognormale': stats.lognorm,
        'Weibull': stats.weibull_min,
        'Esponenziale': stats.expon,
        'Normale': stats.norm,
    }

    results = []
    best = None
    best_mae = np.inf

    for name, dist in candidates.items():
        if name == 'Normale':
            def pdf(x, mu, sigma):
                return stats.norm.pdf(x, loc=mu, scale=sigma)
            p0 = [emp_mean, max(emp_std, 1e-6)]
            bounds = ([data.min() - 2*emp_std, 1e-6], [data.max() + 2*emp_std, 10*emp_std])
        elif name == 'Lognormale':
            def pdf(x, s, loc, scale):
                return stats.lognorm.pdf(x, s, loc=loc, scale=scale)
            s0 = max(0.5, min(2.0, np.std(np.log(data + 1e-6))))
            p0 = [s0, 0.0, max(1e-6, np.median(data))]
            bounds = ([1e-3, -data.min()*0.9, 1e-6], [5.0, data.max()*0.9, data.max()*10])
        elif name == 'Weibull':
            def pdf(x, c, loc, scale):
                return stats.weibull_min.pdf(x, c, loc=loc, scale=scale)
            p0 = [1.2, 0.0, max(1e-6, np.median(data))]
            bounds = ([0.2, -data.min()*0.9, 1e-6], [10.0, data.max()*0.9, data.max()*10])
        elif name == 'Esponenziale':
            def pdf(x, loc, scale):
                return stats.expon.pdf(x, loc=loc, scale=scale)
            p0 = [0.0, max(1e-6, np.mean(data))]
            bounds = ([-data.min()*0.9, 1e-6], [data.max()*0.9, data.max()*10])
        else:
            continue

        params = robust_curve_fit(pdf, x, kde_y, p0, bounds)
        if params is None:
            continue

        if name == 'Normale':
            pdf_y = stats.norm.pdf(x, loc=params[0], scale=params[1])
        elif name == 'Lognormale':
            pdf_y = stats.lognorm.pdf(x, params[0], loc=params[1], scale=params[2])
        elif name == 'Weibull':
            pdf_y = stats.weibull_min.pdf(x, params[0], loc=params[1], scale=params[2])
        else:
            pdf_y = stats.expon.pdf(x, loc=params[0], scale=params[1])

        m = mae(kde_y, pdf_y)
        fit_mean, fit_std = compute_mean_std(name, params)
        ks_p, aic, bic = compute_information_criteria(candidates[name], params, data)
        pl = plausibility(emp_mean, emp_std, fit_mean, fit_std)

        rec = {
            'Distribuzione': name,
            'Parametri': params,
            'MAE_KDE_PDF': m,
            'KS_pvalue': ks_p,
            'AIC': aic,
            'BIC': bic,
            'FitMean': fit_mean,
            'FitStd': fit_std,
            'Plausible': pl,
        }
        results.append(rec)

        if m < best_mae:
            best_mae = m
            best = rec

    if save_png:
        plt.figure(figsize=(8, 4.5))
        plt.plot(x, kde_y, label='KDE (data)')
        for rec in results:
            name = rec['Distribuzione']
            params = rec['Parametri']
            if name == 'Normale':
                y = stats.norm.pdf(x, loc=params[0], scale=params[1])
            elif name == 'Lognormale':
                y = stats.lognorm.pdf(x, params[0], loc=params[1], scale=params[2])
            elif name == 'Weibull':
                y = stats.weibull_min.pdf(x, params[0], loc=params[1], scale=params[2])
            else:
                y = stats.expon.pdf(x, loc=params[0], scale=params[1])
            plt.plot(x, y, alpha=0.8, label=name)
        plt.title(f"PDF fits vs KDE — {label_prefix}")
        plt.legend()
        plt.tight_layout()
        out_png = png_dir / f"{label_prefix}_fits.png"
        plt.savefig(out_png, dpi=130)
        plt.close()
        logging.info("Saved PNG: %s", out_png)

    logging.info("Winner for %s: %s (MAE=%.6g, params=%s)",
                 label_prefix, best['Distribuzione'], best['MAE_KDE_PDF'], json.dumps(best['Parametri']))
    print(f"\n==> WINNER [{label_prefix}]: {best['Distribuzione']} (MAE={best['MAE_KDE_PDF']:.6g}) params={best['Parametri']}")

    return pd.DataFrame(results), best


# ---------------------- Fit summary export ---------------------- #

def to_fit_summary_rows(stage: str, winner: dict) -> dict:
    """Map our winning record to SciPy-style param columns for generator."""
    name = winner['Distribuzione']
    params = winner['Parametri']
    row = {
        'stage': stage,
        'dist': None,
        'mu': None, 'sigma': None, 's': None,
        'shape': None, 'c': None,
        'scale': None, 'loc': None,
        'mae': winner.get('MAE_KDE_PDF'),
        'aic': winner.get('AIC'),
        'bic': winner.get('BIC'),
        'ks_pvalue': winner.get('KS_pvalue'),
        'is_winner': True,
    }
    if name == 'Normale':
        row['dist'] = 'norm'
        row['mu'], row['sigma'] = params[0], params[1]
    elif name == 'Lognormale':
        row['dist'] = 'lognorm'
        row['s'] = params[0]
        row['loc'] = params[1]
        row['scale'] = params[2]
        row['mu'] = float(np.log(params[2])) if params[2] and params[2] > 0 else None
        row['sigma'] = row['s']
    elif name == 'Weibull':
        row['dist'] = 'weibull_min'
        row['c'] = params[0]
        row['loc'] = params[1]
        row['scale'] = params[2]
        row['shape'] = row['c']
    elif name == 'Esponenziale':
        row['dist'] = 'expon'
        row['loc'] = params[0]
        row['scale'] = params[1]
    else:
        row['dist'] = name
    return row


# ----------------------------- CLI -------------------------------- #

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='./etl/output/csv/tickets_prs_merged.csv', help='ETL CSV')
    parser.add_argument('--time-col', default=None, help='Precomputed resolution time column (numeric)')
    parser.add_argument('--created-col', default='fields.created', help='Jira created datetime column')
    parser.add_argument('--resolved-col', default='fields.resolutiondate', help='Jira resolution datetime column')
    parser.add_argument('--unit', choices=['hours','days'], default='hours', help='Unit for computed durations')
    parser.add_argument('--outdir', default='./etl/output', help='Base output directory (will write csv/ and png/)')
    parser.add_argument('--stages', nargs='+', default=['dev_review', 'testing'],
                        help='Stages to export in fit_summary.csv (duplicated winner if only time-col is provided)')
    parser.add_argument('--stage-cols', nargs='*', default=None,
                        help='Optional: columns per stage, same order as --stages (fit each stage separately)')
    parser.add_argument('--save-png', action='store_true', help='Save PNG overlays')
    args = parser.parse_args()

    outdir = Path(args.outdir)
    setup_logging(outdir)

    logging.info("Reading ETL: %s", args.input)
    df = pd.read_csv(args.input)

    # If no time-col, compute from created/resolved
    if not args.time_col:
        if args.created_col not in df.columns or args.resolved_col not in df.columns:
            logging.error("Missing time columns. Either provide --time-col or both --created-col and --resolved-col.")
            raise SystemExit(1)
        logging.info("Computing resolution time from %s -> %s", args.created_col, args.resolved_col)
        created = pd.to_datetime(df[args.created_col], errors='coerce', utc=True).dt.tz_convert('UTC').dt.tz_localize(None)
        resolved = pd.to_datetime(df[args.resolved_col], errors='coerce', utc=True).dt.tz_convert('UTC').dt.tz_localize(None)
        delta = (resolved - created).dt.total_seconds()
        if args.unit == 'hours':
            df['__computed_time__'] = delta / 3600.0
        else:
            df['__computed_time__'] = delta / 86400.0
        args.time_col = '__computed_time__'
        logging.info("Computed %d valid durations (%s).", (~df[args.time_col].isna()).sum(), args.unit)

    # Decide data series list
    series_list = []
    if args.stage_cols and len(args.stage_cols) == len(args.stages):
        for col, stage in zip(args.stage_cols, args.stages):
            if col not in df.columns:
                logging.error("Missing stage column %s for stage %s", col, stage)
                raise SystemExit(1)
            series_list.append((stage, df[col]))
        logging.info("Fitting %d stage-specific series from columns: %s", len(series_list), args.stage_cols)
    else:
        if args.time_col not in df.columns:
            logging.error("Missing --time-col %s", args.time_col)
            raise SystemExit(1)
        s = df[args.time_col]
        series_list.append(("_e2e_", s))
        logging.info("Fitting single series from %s (will duplicate winner across stages %s)", args.time_col, args.stages)

    # Fit and collect
    all_stats = []
    winners = {}
    for stage, s in series_list:
        stats_df, win = fit_single_series(s, label_prefix=stage, png_dir=outdir / 'png', save_png=args.save_png)
        all_stats.append((stage, stats_df))
        winners[stage] = win

    # Save detailed stats
    detailed = []
    for stage, sdf in all_stats:
        tmp = sdf.copy()
        tmp.insert(0, 'Stage', stage)
        detailed.append(tmp)
    detailed_df = pd.concat(detailed, ignore_index=True)
    detailed_path = outdir / 'csv' / 'distribution_fit_stats.csv'
    detailed_df.to_csv(detailed_path, index=False)
    logging.info("Saved distribution_fit_stats.csv: %s", detailed_path)

    # Build fit_summary.csv
    summary_rows = []
    if args.stage_cols:
        for stage in args.stages:
            summary_rows.append(to_fit_summary_rows(stage, winners[stage]))
    else:
        only_win = winners[series_list[0][0]]
        for stage in args.stages:
            summary_rows.append(to_fit_summary_rows(stage, only_win))

    summary_df = pd.DataFrame(summary_rows)
    summary_path = outdir / 'csv' / 'fit_summary.csv'
    summary_df.to_csv(summary_path, index=False)
    logging.info("Saved fit_summary.csv for generator: %s", summary_path)

    print("\nfit_summary.csv written at:", summary_path)
    print(summary_df.to_string(index=False))
    for stage in args.stages:
        print(f"WINNER exported for stage '{stage}': {summary_df[summary_df['stage']==stage]['dist'].iloc[0]}")


if __name__ == '__main__':
    main()
