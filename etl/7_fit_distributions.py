# v9
# file: 7_fit_distributions.py

"""
Fit, slide (loc), and compare all candidate distributions on resolution times.
- For each: optimize all parameters for best MAE-to-KDE (i.e. finds the best slide, shape, stretch)
- For every fit, compute: MAE, KS, AIC, BIC, mean/std, plausibility.
- Winner is ALWAYS reported in logs and stdout (lowest MAE).
- 4 PNG: all fits, plausible, MAE<2x, top-3. Manual overlay for visual debug.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as stats
from scipy.optimize import curve_fit
from scipy.special import gamma as gammafn
import logging
import os

def mean_absolute_error_curve(y_true, y_pred):
    return np.mean(np.abs(y_true - y_pred))

def mean_std_from_params(dist_name, params):
    if dist_name == 'Normale':
        mu, sigma = params[0], params[1]
        return mu, sigma
    elif dist_name == 'Lognormale':
        s, loc, scale = params
        mu = np.log(scale)
        sigma = s
        mean = np.exp(mu + sigma**2 / 2)
        std = np.sqrt((np.exp(sigma**2) - 1) * np.exp(2*mu + sigma**2))
        return mean, std
    elif dist_name == 'Weibull':
        c, loc, scale = params
        mean = scale * gammafn(1 + 1/c)
        std = scale * np.sqrt(gammafn(1 + 2/c) - gammafn(1 + 1/c)**2)
        return mean, std
    elif dist_name == 'Esponenziale':
        loc, scale = params
        return loc + scale, scale
    return None, None

def plausibility_check(emp_mean, emp_std, fit_mean, fit_std, max_pct_diff=0.5):
    mean_ok = abs(fit_mean - emp_mean) / emp_mean < max_pct_diff
    std_ok = abs(fit_std - emp_std) / emp_std < max_pct_diff
    return mean_ok and std_ok

def compute_ks_aic_bic(dist, params, data):
    try:
        ks_stat, ks_pval = stats.kstest(data, dist.name, args=params)
    except Exception:
        ks_pval = np.nan
    try:
        loglike = np.sum(dist.logpdf(data, *params))
        k = len(params)
        aic = 2 * k - 2 * loglike
        bic = k * np.log(len(data)) - 2 * loglike
    except Exception:
        aic, bic = np.nan, np.nan
    return ks_pval, aic, bic

def robust_curve_fit(pdf_func, x, kde_y, p0, bounds):
    try:
        popt, _ = curve_fit(pdf_func, x, kde_y, p0=p0, bounds=bounds, maxfev=20000)
        return popt
    except Exception as e:
        logging.warning(f"curve_fit failed: {e}")
        return None

if __name__ == "__main__":
    os.makedirs('./output/logs', exist_ok=True)
    os.makedirs('./output/png', exist_ok=True)
    os.makedirs('./output/csv', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("./output/logs/fit_distributions.log"),
            logging.StreamHandler()
        ]
    )

    IN_CSV = "./output/csv/tickets_prs_merged.csv"
    try:
        df = pd.read_csv(IN_CSV)
        logging.info(f"Caricato dataset: {IN_CSV} ({len(df)} righe)")
    except Exception as e:
        logging.error(f"Errore caricando il file CSV: {e}")
        exit(1)

    if 'fields.created' in df.columns and 'fields.resolutiondate' in df.columns:
        df['fields.created'] = pd.to_datetime(df['fields.created'], errors='coerce')
        df['fields.resolutiondate'] = pd.to_datetime(df['fields.resolutiondate'], errors='coerce')
        df['resolution_time_hours'] = (df['fields.resolutiondate'] - df['fields.created']).dt.total_seconds() / 3600

    filtered = df[(df['resolution_time_hours'] > 0) & (df['resolution_time_hours'] < 10000)]['resolution_time_hours'].dropna()
    if len(filtered) < 10:
        logging.error("Pochi dati validi per il fit! Intervallo 0 < t < 10000 ore.")
        exit(1)
    logging.info(f"Ticket validi per il fit: {len(filtered)}")

    emp_mean = filtered.mean()
    emp_std = filtered.std()

    x = np.linspace(filtered.min(), filtered.max(), 1000)
    kde = stats.gaussian_kde(filtered)
    kde_y = kde(x)

    candidate_distributions = {
        'Lognormale': stats.lognorm,
        'Weibull': stats.weibull_min,
        'Esponenziale': stats.expon,
        'Normale': stats.norm
    }

    fit_stats = []
    line_styles = {True: '-', False: '--'}
    color_map = {
        'Lognormale': 'tab:red',
        'Weibull': 'tab:purple',
        'Esponenziale': 'tab:blue',
        'Normale': 'tab:orange'
    }

    best_fit_global = None
    min_mae_global = np.inf

    for label, dist in candidate_distributions.items():
        # -- Best-MAE with all parameters free (curve_fit to KDE) --
        if label == 'Normale':
            def normal_pdf(x, mu, sigma):
                return stats.norm.pdf(x, loc=mu, scale=sigma)
            p0 = [emp_mean, emp_std]
            bounds = ([filtered.min()-emp_std*2, emp_std*0.1],
                      [filtered.max()+emp_std*2, emp_std*5])
            best_params = robust_curve_fit(normal_pdf, x, kde_y, p0, bounds)
            if best_params is not None:
                best_pdf = stats.norm.pdf(x, *best_params)
                fit_mean, fit_std = best_params[0], best_params[1]
                plausible = plausibility_check(emp_mean, emp_std, fit_mean, fit_std)
                ks_pval, aic, bic = compute_ks_aic_bic(stats.norm, best_params, filtered)
                mae = mean_absolute_error_curve(kde_y, best_pdf)
                fit_stats.append({
                    "Distribuzione": label,
                    "FitType": "Best-MAE (curve_fit)",
                    "Parametri": best_params,
                    "KS_pvalue": ks_pval,
                    "AIC": aic,
                    "BIC": bic,
                    "MAE_KDE_PDF": mae,
                    "PDF": best_pdf,
                    "FitMean": fit_mean,
                    "FitStd": fit_std,
                    "Plausible": plausible
                })
                if mae < min_mae_global:
                    min_mae_global = mae
                    best_fit_global = fit_stats[-1]

        elif label == 'Lognormale':
            def lognorm_pdf(x, s, loc, scale):
                return stats.lognorm.pdf(x, s, loc, scale)
            p0 = [1, 0, filtered.min()]
            bounds = ([0.05, filtered.min()-emp_std*2, 0.01],
                      [10, filtered.max()+emp_std*2, filtered.max()*2])
            best_params = robust_curve_fit(lognorm_pdf, x, kde_y, p0, bounds)
            if best_params is not None:
                best_pdf = stats.lognorm.pdf(x, *best_params)
                fit_mean, fit_std = mean_std_from_params(label, best_params)
                plausible = plausibility_check(emp_mean, emp_std, fit_mean, fit_std)
                ks_pval, aic, bic = compute_ks_aic_bic(stats.lognorm, best_params, filtered)
                mae = mean_absolute_error_curve(kde_y, best_pdf)
                fit_stats.append({
                    "Distribuzione": label,
                    "FitType": "Best-MAE (curve_fit)",
                    "Parametri": best_params,
                    "KS_pvalue": ks_pval,
                    "AIC": aic,
                    "BIC": bic,
                    "MAE_KDE_PDF": mae,
                    "PDF": best_pdf,
                    "FitMean": fit_mean,
                    "FitStd": fit_std,
                    "Plausible": plausible
                })
                if mae < min_mae_global:
                    min_mae_global = mae
                    best_fit_global = fit_stats[-1]

        elif label == 'Weibull':
            def weibull_pdf(x, c, loc, scale):
                return stats.weibull_min.pdf(x, c, loc, scale)
            p0 = [1.5, 0, emp_mean]
            bounds = ([0.05, filtered.min()-emp_std*2, 0.01],
                      [10, filtered.max()+emp_std*2, filtered.max()*2])
            best_params = robust_curve_fit(weibull_pdf, x, kde_y, p0, bounds)
            if best_params is not None:
                best_pdf = stats.weibull_min.pdf(x, *best_params)
                fit_mean, fit_std = mean_std_from_params(label, best_params)
                plausible = plausibility_check(emp_mean, emp_std, fit_mean, fit_std)
                ks_pval, aic, bic = compute_ks_aic_bic(stats.weibull_min, best_params, filtered)
                mae = mean_absolute_error_curve(kde_y, best_pdf)
                fit_stats.append({
                    "Distribuzione": label,
                    "FitType": "Best-MAE (curve_fit)",
                    "Parametri": best_params,
                    "KS_pvalue": ks_pval,
                    "AIC": aic,
                    "BIC": bic,
                    "MAE_KDE_PDF": mae,
                    "PDF": best_pdf,
                    "FitMean": fit_mean,
                    "FitStd": fit_std,
                    "Plausible": plausible
                })
                if mae < min_mae_global:
                    min_mae_global = mae
                    best_fit_global = fit_stats[-1]

        elif label == 'Esponenziale':
            def exp_pdf(x, loc, scale):
                return stats.expon.pdf(x, loc, scale)
            p0 = [0, emp_mean]
            bounds = ([filtered.min()-emp_std*2, 0.01],
                      [filtered.max()+emp_std*2, filtered.max()*2])
            best_params = robust_curve_fit(exp_pdf, x, kde_y, p0, bounds)
            if best_params is not None:
                best_pdf = stats.expon.pdf(x, *best_params)
                fit_mean, fit_std = mean_std_from_params(label, best_params)
                plausible = plausibility_check(emp_mean, emp_std, fit_mean, fit_std)
                ks_pval, aic, bic = compute_ks_aic_bic(stats.expon, best_params, filtered)
                mae = mean_absolute_error_curve(kde_y, best_pdf)
                fit_stats.append({
                    "Distribuzione": label,
                    "FitType": "Best-MAE (curve_fit)",
                    "Parametri": best_params,
                    "KS_pvalue": ks_pval,
                    "AIC": aic,
                    "BIC": bic,
                    "MAE_KDE_PDF": mae,
                    "PDF": best_pdf,
                    "FitMean": fit_mean,
                    "FitStd": fit_std,
                    "Plausible": plausible
                })
                if mae < min_mae_global:
                    min_mae_global = mae
                    best_fit_global = fit_stats[-1]

    # --- PLOT: All fits
    plt.figure(figsize=(16, 7))
    plt.plot(x, kde_y, color='black', lw=3.5, label='KDE (Empirical)')
    for fit in fit_stats:
        color = color_map.get(fit["Distribuzione"], 'gray')
        style = '-' if fit["Plausible"] else '--'
        label_str = f"{fit['Distribuzione']} ({fit['FitType']})"
        if not fit["Plausible"]:
            label_str += " [NOT plausible]"
        plt.plot(x, fit["PDF"], color=color, lw=2.1, linestyle=style, label=label_str)
    plt.plot(x, best_fit_global["PDF"], color='gold', lw=4, linestyle='--',
             label=f"WINNER: {best_fit_global['Distribuzione']} (MAE={best_fit_global['MAE_KDE_PDF']:.2g})")
    plt.title("All Distribution Fits (Best-MAE, best possible slide/shape)", fontsize=17)
    plt.xlabel("Resolution Time (hours)", fontsize=15)
    plt.ylabel("Density (PDF)", fontsize=15)
    plt.legend(fontsize=10, frameon=True, ncol=2)
    plt.tight_layout()
    plt.savefig('./output/png/confronto_fit_distribuzioni_tutti.png', dpi=200)
    plt.close()

    # --- Save CSV and print summary
    stats_df = pd.DataFrame(fit_stats).sort_values("MAE_KDE_PDF")
    stats_df.to_csv('./output/csv/distribution_fit_stats.csv', index=False)

    print("\n=== SOMMARIO FIT DISTRIBUZIONI (Best MAE slide/shape) ===\n")
    print(stats_df[["Distribuzione", "FitType", "KS_pvalue", "AIC", "BIC", "MAE_KDE_PDF", "FitMean", "FitStd", "Plausible"]])
    logging.info("\n" + stats_df[["Distribuzione", "FitType", "KS_pvalue", "AIC", "BIC", "MAE_KDE_PDF", "FitMean", "FitStd", "Plausible"]].to_string(index=False))

    print(f"\n==> WINNER: {best_fit_global['Distribuzione']} ({best_fit_global['FitType']}), MAE={best_fit_global['MAE_KDE_PDF']:.6f}, parameters={best_fit_global['Parametri']}\n")
    logging.info(f"WINNER: {best_fit_global['Distribuzione']} ({best_fit_global['FitType']}), MAE={best_fit_global['MAE_KDE_PDF']:.6f}, parameters={best_fit_global['Parametri']}")

    # Show implausibles (optional)
    implausible = stats_df[~stats_df["Plausible"]]
    if not implausible.empty:
        print("Distributions marked as NOT plausible (mean/std too far from data):")
        print(implausible[["Distribuzione", "FitType", "FitMean", "FitStd"]])
        logging.info("Implausible fits:\n" + implausible[["Distribuzione", "FitType", "FitMean", "FitStd"]].to_string(index=False))

"""
v9: Optimizes loc/scale/shape (slide/fit) for ALL distributions.
Winner is always reported, even if all implausible. Full logs, PNG, and CSV as per PMCSN project specs.
"""
