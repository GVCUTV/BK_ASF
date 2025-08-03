# v4
# file: 7_fit_distributions.py

"""
Fit e confronto visivo/quantitativo di distribuzioni candidate sui tempi di risoluzione.
- Empirical KDE (linea nera)
- Ogni distribuzione è testata con diverse strategie di fit (e.g. lognormale/Weibull con floc=0 o libero)
- Per ogni famiglia si mostra SOLO la versione migliore (minimo MAE rispetto alla KDE)
- Tutte le statistiche (KS, AIC, BIC, MAE) salvate e mostrate
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
import logging
import os

def mean_absolute_error_curve(y_true, y_pred):
    """MAE tra due curve sugli stessi x."""
    return np.mean(np.abs(y_true - y_pred))

if __name__ == "__main__":
    # === Setup logging/output dirs ===
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

    # --- Load and filter data ---
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

    # --- Empirical KDE for reference ---
    x = np.linspace(filtered.min(), filtered.max(), 1000)
    from scipy.stats import gaussian_kde
    kde = gaussian_kde(filtered)
    kde_y = kde(x)

    # ---- Fit each candidate with different strategies ----
    candidate_distributions = {
        #'Lognormale': stats.lognorm,
        #'Weibull': stats.weibull_min,
        'Esponenziale': stats.expon,
        'Normale': stats.norm
    }

    fit_stats = []
    best_fit_per_family = {}

    """
    # LOGNORMALE (try both fit, and fit with floc=0)
    dist = stats.lognorm
    label = 'Lognormale'
    lognorm_fits = []
    # 1. MLE fit
    params = dist.fit(filtered)
    pdf_y = dist.pdf(x, *params)
    mae = mean_absolute_error_curve(kde_y, pdf_y)
    ks_stat, ks_pval = stats.kstest(filtered, dist.name, args=params)
    loglike = np.sum(dist.logpdf(filtered, *params))
    k = len(params)
    aic = 2 * k - 2 * loglike
    bic = k * np.log(len(filtered)) - 2 * loglike
    lognorm_fits.append({
        "Distribuzione": label,
        "FitType": "MLE libero",
        "Parametri": params,
        "KS_pvalue": ks_pval,
        "AIC": aic,
        "BIC": bic,
        "MAE_KDE_PDF": mae,
        "PDF": pdf_y
    })
    # 2. fit with floc=0 (classic heavy-tail lognormal assumption)
    params0 = dist.fit(filtered, floc=0)
    pdf0_y = dist.pdf(x, *params0)
    mae0 = mean_absolute_error_curve(kde_y, pdf0_y)
    ks_stat0, ks_pval0 = stats.kstest(filtered, dist.name, args=params0)
    loglike0 = np.sum(dist.logpdf(filtered, *params0))
    k0 = len(params0)
    aic0 = 2 * k0 - 2 * loglike0
    bic0 = k0 * np.log(len(filtered)) - 2 * loglike0
    lognorm_fits.append({
        "Distribuzione": label,
        "FitType": "floc=0",
        "Parametri": params0,
        "KS_pvalue": ks_pval0,
        "AIC": aic0,
        "BIC": bic0,
        "MAE_KDE_PDF": mae0,
        "PDF": pdf0_y
    })
    best_lognorm = min(lognorm_fits, key=lambda d: d["MAE_KDE_PDF"])
    fit_stats.extend(lognorm_fits)
    best_fit_per_family[label] = best_lognorm

    # WEIBULL (free and floc=0)
    dist = stats.weibull_min
    label = 'Weibull'
    weibull_fits = []
    params = dist.fit(filtered)
    pdf_y = dist.pdf(x, *params)
    mae = mean_absolute_error_curve(kde_y, pdf_y)
    ks_stat, ks_pval = stats.kstest(filtered, dist.name, args=params)
    loglike = np.sum(dist.logpdf(filtered, *params))
    k = len(params)
    aic = 2 * k - 2 * loglike
    bic = k * np.log(len(filtered)) - 2 * loglike
    weibull_fits.append({
        "Distribuzione": label,
        "FitType": "MLE libero",
        "Parametri": params,
        "KS_pvalue": ks_pval,
        "AIC": aic,
        "BIC": bic,
        "MAE_KDE_PDF": mae,
        "PDF": pdf_y
    })
    # floc=0
    params0 = dist.fit(filtered, floc=0)
    pdf0_y = dist.pdf(x, *params0)
    mae0 = mean_absolute_error_curve(kde_y, pdf0_y)
    ks_stat0, ks_pval0 = stats.kstest(filtered, dist.name, args=params0)
    loglike0 = np.sum(dist.logpdf(filtered, *params0))
    k0 = len(params0)
    aic0 = 2 * k0 - 2 * loglike0
    bic0 = k0 * np.log(len(filtered)) - 2 * loglike0
    weibull_fits.append({
        "Distribuzione": label,
        "FitType": "floc=0",
        "Parametri": params0,
        "KS_pvalue": ks_pval0,
        "AIC": aic0,
        "BIC": bic0,
        "MAE_KDE_PDF": mae0,
        "PDF": pdf0_y
    })
    best_weibull = min(weibull_fits, key=lambda d: d["MAE_KDE_PDF"])
    fit_stats.extend(weibull_fits)
    best_fit_per_family[label] = best_weibull
    """

    # ESPONENZIALE (fit free and floc=0)
    dist = stats.expon
    label = 'Esponenziale'
    exp_fits = []
    params = dist.fit(filtered)
    pdf_y = dist.pdf(x, *params)
    mae = mean_absolute_error_curve(kde_y, pdf_y)
    ks_stat, ks_pval = stats.kstest(filtered, dist.name, args=params)
    loglike = np.sum(dist.logpdf(filtered, *params))
    k = len(params)
    aic = 2 * k - 2 * loglike
    bic = k * np.log(len(filtered)) - 2 * loglike
    exp_fits.append({
        "Distribuzione": label,
        "FitType": "MLE libero",
        "Parametri": params,
        "KS_pvalue": ks_pval,
        "AIC": aic,
        "BIC": bic,
        "MAE_KDE_PDF": mae,
        "PDF": pdf_y
    })
    params0 = dist.fit(filtered, floc=0)
    pdf0_y = dist.pdf(x, *params0)
    mae0 = mean_absolute_error_curve(kde_y, pdf0_y)
    ks_stat0, ks_pval0 = stats.kstest(filtered, dist.name, args=params0)
    loglike0 = np.sum(dist.logpdf(filtered, *params0))
    k0 = len(params0)
    aic0 = 2 * k0 - 2 * loglike0
    bic0 = k0 * np.log(len(filtered)) - 2 * loglike0
    exp_fits.append({
        "Distribuzione": label,
        "FitType": "floc=0",
        "Parametri": params0,
        "KS_pvalue": ks_pval0,
        "AIC": aic0,
        "BIC": bic0,
        "MAE_KDE_PDF": mae0,
        "PDF": pdf0_y
    })
    best_exp = min(exp_fits, key=lambda d: d["MAE_KDE_PDF"])
    fit_stats.extend(exp_fits)
    best_fit_per_family[label] = best_exp

    # NORMALE (no options, just fit once)
    dist = stats.norm
    label = 'Normale'
    params = dist.fit(filtered)
    pdf_y = dist.pdf(x, *params)
    mae = mean_absolute_error_curve(kde_y, pdf_y)
    ks_stat, ks_pval = stats.kstest(filtered, dist.name, args=params)
    loglike = np.sum(dist.logpdf(filtered, *params))
    k = len(params)
    aic = 2 * k - 2 * loglike
    bic = k * np.log(len(filtered)) - 2 * loglike
    norm_fit = {
        "Distribuzione": label,
        "FitType": "MLE",
        "Parametri": params,
        "KS_pvalue": ks_pval,
        "AIC": aic,
        "BIC": bic,
        "MAE_KDE_PDF": mae,
        "PDF": pdf_y
    }
    fit_stats.append(norm_fit)
    best_fit_per_family[label] = norm_fit

    # === PLOT ===
    plt.figure(figsize=(16, 7))
    plt.plot(x, kde_y, color='black', lw=3.5, label='Densità osservata (KDE)')
    colors = ['tab:blue', 'tab:orange', 'tab:red', 'tab:purple']
    for (label, fit), color in zip(best_fit_per_family.items(), colors):
        plt.plot(x, fit["PDF"], color=color, lw=2.2, label=f"{label} ({fit['FitType']})")
    plt.title("Confronto fit: densità empirica (KDE) e migliori PDF teorici", fontsize=17)
    plt.xlabel("Tempo di risoluzione (ore)", fontsize=15)
    plt.ylabel("Densità (PDF)", fontsize=15)
    plt.legend(fontsize=12, frameon=True)
    plt.tight_layout()
    plt.savefig('./output/png/confronto_fit_distribuzioni_linee.png', dpi=200)
    plt.close()
    logging.info("Grafico confronto fit (linee) salvato in ./output/png/confronto_fit_distribuzioni_linee.png")

    # --- Save and print summary statistics (sorted by MAE) ---
    stats_df = pd.DataFrame(fit_stats)
    stats_df = stats_df.sort_values("MAE_KDE_PDF")
    stats_df.to_csv('./output/csv/distribution_fit_stats.csv', index=False)
    print("\n=== SOMMARIO FIT DISTRIBUZIONI (ordinato per MAE) ===\n")
    print(stats_df[["Distribuzione", "FitType", "KS_pvalue", "AIC", "BIC", "MAE_KDE_PDF"]])
    logging.info("\n" + stats_df[["Distribuzione", "FitType", "KS_pvalue", "AIC", "BIC", "MAE_KDE_PDF"]].to_string(index=False))

"""
Note:
- Ogni distribuzione è valutata con più strategie (fit libero, floc=0, etc)
- Sul grafico viene mostrata solo la versione migliore (minimo MAE)
- Tutti i dettagli sono in distribution_fit_stats.csv
"""
