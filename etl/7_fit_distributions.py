# v12
# file: 7_fit_distributions.py

"""
Fit di distribuzioni (Lognormale, Weibull(min), Esponenziale, Normale) su SERIE in GIORNI.
Separazione per fasi DISTINTE:
  - development  -> 'dev_duration_days'
  - review       -> 'review_duration_days'
  - testing      -> 'test_duration_days'
Inoltre: legacy 'resolution_time_days' per compatibilità con etl/8_export_fit_summary.py.

Output:
- ./output/csv/distribution_fit_stats.csv                (LEGACY: dettagli su resolution_time_days)
- ./output/csv/distribution_fit_stats_development.csv    (dettagli stage development)
- ./output/csv/distribution_fit_stats_review.csv         (dettagli stage review)
- ./output/csv/distribution_fit_stats_testing.csv        (dettagli stage testing)
- ./output/csv/fit_summary.csv                           (righe per stage -> dist + parametri in naming SciPy)
- ./output/png/confronto_fit_*.png                       (plot per target/stage)

Nessun argomento CLI: eseguire semplicemente `python 7_fit_distributions.py`.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as stats
from scipy.optimize import curve_fit
from scipy.special import gamma as gammafn
import logging
import os
from pathlib import Path
from math import exp, log, sqrt
from path_config import PROJECT_ROOT

# ---------------- Config ---------------- #
INPUT_CSV = PROJECT_ROOT+"/etl/output/csv/tickets_prs_merged.csv"
OUT_BASE = Path(PROJECT_ROOT+"/etl/output")
PNG_DIR = OUT_BASE / "png"
CSV_DIR = OUT_BASE / "csv"
LOG_PATH = OUT_BASE / "logs" / "fit_distributions.log"

# Stage mapping (nome_stage -> singola colonna da fittare)
STAGE_SERIES = {
    "development": "dev_duration_days",
    "review": "review_duration_days",
    "testing": "test_duration_days",
}

# Filtro outliers (giorni)
MAX_DAYS = 3650.0  # ~10 anni
# --------------------------------------- #

def _setup_logging():
    os.makedirs(OUT_BASE / "logs", exist_ok=True)
    logging.getLogger().handlers.clear()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
    )
    logging.info("Logger initialized. Logfile: %s", LOG_PATH)

def _valid_series(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").dropna()
    s = s[(s >= 0) & np.isfinite(s)]
    return s

def _mae(y_true, y_pred):
    return float(np.mean(np.abs(y_true - y_pred)))

def _mean_std_from_params(dist_name, params):
    # Distribuzione -> (mean, std) in giorni
    if dist_name == 'Normale':
        mu, sigma = params
        return float(mu), float(sigma)
    elif dist_name == 'Lognormale':
        s, loc, scale = params
        mu = log(scale)
        sigma = s
        mean = exp(mu + sigma**2 / 2)
        std = sqrt((exp(sigma**2) - 1) * exp(2*mu + sigma**2))
        return float(mean), float(std)
    elif dist_name == 'Weibull':
        c, loc, scale = params
        mean = scale * float(gammafn(1 + 1/c))
        std = scale * sqrt(float(gammafn(1 + 2/c) - gammafn(1 + 1/c)**2))
        return float(mean), float(std)
    elif dist_name == 'Esponenziale':
        loc, scale = params
        return float(loc + scale), float(scale)
    return float("nan"), float("nan")

def _plausible(emp_mean, emp_std, fit_mean, fit_std, max_pct=0.5):
    if np.isnan(emp_mean) or np.isnan(emp_std) or emp_mean == 0 or emp_std == 0:
        return True
    return (abs(fit_mean - emp_mean)/max(emp_mean,1e-9) < max_pct) and (abs(fit_std - emp_std)/max(emp_std,1e-9) < max_pct)

def _ks_aic_bic(dist_obj, params, data):
    try:
        ks_stat, ks_p = stats.kstest(data, dist_obj.name, args=params)
    except Exception:
        ks_p = np.nan
    try:
        ll = np.sum(dist_obj.logpdf(data, *params))
        k = len(params)
        aic = 2*k - 2*ll
        bic = k*np.log(len(data)) - 2*ll
    except Exception:
        aic = np.nan
        bic = np.nan
    return ks_p, aic, bic

def _curve_fit(pdf_func, x, y, p0, bounds):
    try:
        popt, _ = curve_fit(pdf_func, x, y, p0=p0, bounds=bounds, maxfev=40000)
        return popt
    except Exception as e:
        logging.warning("curve_fit failed: %s", e)
        return None

def _fit_distribution_set(series: pd.Series):
    data = _valid_series(series)
    data = data[data <= MAX_DAYS]
    if len(data) < 10:
        return None, None, None, []

    emp_mean = float(data.mean())
    emp_std = float(data.std())
    x = np.linspace(float(data.min()), float(data.max()), 1000)
    kde = stats.gaussian_kde(data)
    kde_y = kde(x)

    candidates = {
        'Lognormale': stats.lognorm,
        'Weibull': stats.weibull_min,
        'Esponenziale': stats.expon,
        'Normale': stats.norm
    }

    results = []
    best = None
    best_mae = float("inf")

    for label, dist in candidates.items():
        if label == 'Normale':
            def pdf(xx, mu, sigma):
                return stats.norm.pdf(xx, loc=mu, scale=sigma)
            p0 = [emp_mean, max(emp_std, max(emp_mean/10, 1e-3))]
            bounds = ([data.min()-emp_std*2, max(emp_std*0.05, 1e-6)],
                      [data.max()+emp_std*2, emp_std*10 + 1.0])
            params = _curve_fit(pdf, x, kde_y, p0, bounds)

        elif label == 'Lognormale':
            def pdf(xx, s, loc, scale):
                return stats.lognorm.pdf(xx, s, loc, scale)
            p0 = [max(emp_std/emp_mean if emp_mean>0 else 1.0, 0.25), 0.0, max(emp_mean, 1e-6)]
            bounds = ([0.05, data.min()-emp_std*2, 1e-9],
                      [10.0, data.max()+emp_std*2, data.max()*10])
            params = _curve_fit(pdf, x, kde_y, p0, bounds)

        elif label == 'Weibull':
            def pdf(xx, c, loc, scale):
                return stats.weibull_min.pdf(xx, c, loc, scale)
            p0 = [1.5, 0.0, max(emp_mean, 1e-6)]
            bounds = ([0.05, data.min()-emp_std*2, 1e-9],
                      [10.0, data.max()+emp_std*2, data.max()*10])
            params = _curve_fit(pdf, x, kde_y, p0, bounds)

        elif label == 'Esponenziale':
            def pdf(xx, loc, scale):
                return stats.expon.pdf(xx, loc, scale)
            p0 = [max(data.min()-emp_std, 0.0), max(emp_mean, 1e-9)]
            bounds = ([data.min()-emp_std*2, 1e-9],
                      [data.max()+emp_std*2, data.max()*10])
            params = _curve_fit(pdf, x, kde_y, p0, bounds)

        else:
            params = None

        if params is None:
            continue

        pdf_vals = candidates[label].pdf(x, *params)
        fit_mean, fit_std = _mean_std_from_params(label, params)
        plausible = _plausible(emp_mean, emp_std, fit_mean, fit_std)
        ks_p, aic, bic = _ks_aic_bic(candidates[label], params, data)
        mae = _mae(kde_y, pdf_vals)

        row = {
            "Distribuzione": label,
            "FitType": "Best-MAE (curve_fit)",
            "Parametri": params,
            "KS_pvalue": ks_p,
            "AIC": aic,
            "BIC": bic,
            "MAE_KDE_PDF": mae,
            "FitMean": fit_mean,
            "FitStd": fit_std,
            "Plausible": plausible,
        }
        results.append(row)
        if mae < best_mae:
            best_mae = mae
            best = row

    return data, x, kde_y, results, best

def _to_fit_summary_row(stage: str, win_row: dict) -> dict:
    """Mappa la riga vincente in naming SciPy e parametri espliciti."""
    name = win_row["Distribuzione"]
    params = win_row["Parametri"]
    out = {"stage": stage, "dist": None}

    if name == "Lognormale":
        out["dist"] = "lognorm"
        out["s"] = float(params[0]); out["loc"] = float(params[1]); out["scale"] = float(params[2])
        out["mu"] = float(np.log(out["scale"])) if out["scale"] > 0 else None
        out["sigma"] = out["s"]
    elif name == "Weibull":
        out["dist"] = "weibull_min"
        out["c"] = float(params[0]); out["loc"] = float(params[1]); out["scale"] = float(params[2])
        out["shape"] = out["c"]
    elif name == "Esponenziale":
        out["dist"] = "expon"
        out["loc"] = float(params[0]); out["scale"] = float(params[1])
    elif name == "Normale":
        out["dist"] = "norm"
        out["mu"] = float(params[0]); out["sigma"] = float(params[1])
    else:
        out["dist"] = name
    # Metriche utili
    out["mae"] = float(win_row.get("MAE_KDE_PDF", np.nan))
    out["ks_pvalue"] = float(win_row.get("KS_pvalue", np.nan)) if win_row.get("KS_pvalue") is not None else None
    out["aic"] = float(win_row.get("AIC", np.nan)) if win_row.get("AIC") is not None else None
    out["bic"] = float(win_row.get("BIC", np.nan)) if win_row.get("BIC") is not None else None
    return out

def main():
    # === Setup ===
    os.makedirs(PNG_DIR, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)
    _setup_logging()

    # Carica dataset
    try:
        df = pd.read_csv(INPUT_CSV, low_memory=False)
        logging.info("Caricato dataset: %s (%d righe)", INPUT_CSV, len(df))
    except Exception as e:
        logging.error("Errore caricando il CSV: %s", e)
        raise SystemExit(1)

    # 1) LEGACY: fit su resolution_time_days (richiesto dal nuovo 8_export_fit_summary.py)
    if "resolution_time_days" not in df.columns and {"fields.created","fields.resolutiondate"}.issubset(df.columns):
        df["fields.created"] = pd.to_datetime(df["fields.created"], errors="coerce", utc=True).dt.tz_convert(None)
        df["fields.resolutiondate"] = pd.to_datetime(df["fields.resolutiondate"], errors="coerce", utc=True).dt.tz_convert(None)
        df["resolution_time_days"] = (df["fields.resolutiondate"] - df["fields.created"]).dt.total_seconds()/86400.0

    if "resolution_time_days" in df.columns:
        logging.info("Fitting distribuzioni su 'resolution_time_days' (legacy)")
        data, x, kde_y, results, best = _fit_distribution_set(df["resolution_time_days"])
        if results:
            pd.DataFrame(results).to_csv(CSV_DIR / "distribution_fit_stats.csv", index=False)
            # Plot
            plt.figure(figsize=(16,7))
            plt.plot(x, kde_y, color='black', lw=3.5, label='KDE (Empirical)')
            for r in results:
                label = r["Distribuzione"] + (" [NOT plausible]" if not r["Plausible"] else "")
                distname = {'Lognormale':'lognorm','Weibull':'weibull_min','Esponenziale':'expon','Normale':'norm'}[r["Distribuzione"]]
                plt.plot(x, getattr(stats, distname).pdf(x, *r["Parametri"]),
                         lw=2.1, linestyle='-' if r["Plausible"] else '--', label=label)
            plt.title("All Distribution Fits – target: resolution_time_days (days)")
            plt.xlabel("resolution_time_days (days)"); plt.ylabel("Density (PDF)")
            plt.legend(fontsize=9, ncol=2); plt.tight_layout()
            plt.savefig(PNG_DIR / "confronto_fit_resolution_time_days.png", dpi=200); plt.close()
            if best:
                logging.info("WINNER [resolution_time_days]: %s, MAE=%.6f, params=%s",
                             best["Distribuzione"], best["MAE_KDE_PDF"], best["Parametri"])
        else:
            logging.warning("Dati insufficienti per fit su resolution_time_days.")
    else:
        logging.warning("Colonna resolution_time_days mancante e impossibile calcolarla: salto legacy output.")

    # 2) Stage-specific fits -> development, review, testing
    summary_rows = []
    for stage, col in STAGE_SERIES.items():
        if col not in df.columns:
            logging.warning("Colonna %s assente: salto stage %s", col, stage)
            continue
        series = _valid_series(df[col])
        series = series[series <= MAX_DAYS]
        if len(series) < 10:
            logging.warning("Dati insufficienti per fit dello stage %s (n=%d).", stage, len(series))
            continue

        logging.info("Fitting distribuzioni per stage '%s' (n=%d).", stage, len(series))
        data, x, kde_y, results, best = _fit_distribution_set(series)
        if not results:
            logging.warning("Nessun fit valido per stage %s.", stage)
            continue

        # Salva dettagli per stage
        pd.DataFrame(results).to_csv(CSV_DIR / f"distribution_fit_stats_{stage}.csv", index=False)

        # Plot
        plt.figure(figsize=(16,7))
        plt.plot(x, kde_y, color='black', lw=3.5, label='KDE (Empirical)')
        for r in results:
            label = r["Distribuzione"] + (" [NOT plausible]" if not r["Plausible"] else "")
            distname = {'Lognormale':'lognorm','Weibull':'weibull_min','Esponenziale':'expon','Normale':'norm'}[r["Distribuzione"]]
            plt.plot(x, getattr(stats, distname).pdf(x, *r["Parametri"]),
                     lw=2.1, linestyle='-' if r["Plausible"] else '--', label=label)
        plt.title(f"All Distribution Fits – stage: {stage} (days)")
        plt.xlabel(f"{stage} (days)"); plt.ylabel("Density (PDF)")
        plt.legend(fontsize=9, ncol=2); plt.tight_layout()
        plt.savefig(PNG_DIR / f"confronto_fit_{stage}.png", dpi=200); plt.close()

        if best:
            summary_rows.append(_to_fit_summary_row(stage, best))
            logging.info("WINNER [%s]: %s, MAE=%.6f, params=%s",
                         stage, best["Distribuzione"], best["MAE_KDE_PDF"], best["Parametri"])

    # fit_summary.csv per simulation/generate_sim_config.py
    if summary_rows:
        out = pd.DataFrame(summary_rows)
        out.to_csv(CSV_DIR / "fit_summary.csv", index=False)
        logging.info("fit_summary.csv salvato in %s", CSV_DIR / "fit_summary.csv")
        print(out.to_string(index=False))
    else:
        logging.error("Nessun fit_summary generato: assenza di dati o fit falliti.")

if __name__ == "__main__":
    main()
