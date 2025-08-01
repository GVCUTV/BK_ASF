# v3
# file: 7_fit_distributions.py

"""
Fit e confronto visivo/quantitativo di distribuzioni candidate sui tempi di risoluzione.
- La distribuzione empirica è mostrata come KDE (linea nera spessa)
- Fit di: lognormale, Weibull, Gamma, Esponenziale, Normale (PDF, linee colorate)
- Calcolo MAE fra KDE e PDF di ogni distribuzione
- Tutte le statistiche (KS, AIC, BIC, MAE) salvate e mostrate
- Logging dettagliato su file e stdout
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
import logging
import os

def mean_absolute_error_curve(y_true, y_pred):
    """Calcola MAE tra due curve valutate sugli stessi punti."""
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

    # Compute resolution times if not present
    if 'fields.created' in df.columns and 'fields.resolutiondate' in df.columns:
        df['fields.created'] = pd.to_datetime(df['fields.created'], errors='coerce')
        df['fields.resolutiondate'] = pd.to_datetime(df['fields.resolutiondate'], errors='coerce')
        df['resolution_time_hours'] = (df['fields.resolutiondate'] - df['fields.created']).dt.total_seconds() / 3600

    # Filter: only realistic resolution times
    filtered = df[(df['resolution_time_hours'] > 0) & (df['resolution_time_hours'] < 10000)]['resolution_time_hours'].dropna()
    if len(filtered) < 10:
        logging.error("Pochi dati validi per il fit! Intervallo 0 < t < 10000 ore.")
        exit(1)
    logging.info(f"Ticket validi per il fit: {len(filtered)}")

    # ---- Candidate distributions to test ----
    candidate_distributions = {
        'Lognormale': stats.lognorm,
        'Weibull': stats.weibull_min,
        'Gamma': stats.gamma,
        'Esponenziale': stats.expon,
        'Normale': stats.norm
    }

    # Store fit results
    fit_stats = []
    # Evaluation x-grid for PDFs and KDE
    x = np.linspace(filtered.min(), filtered.max(), 1000)

    # === Plot: empirical KDE and all model PDFs as lines ===
    plt.figure(figsize=(16, 7))

    # Empirical KDE (line, black, thick)
    try:
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(filtered)
        kde_y = kde(x)
        plt.plot(x, kde_y, color='black', lw=3.5, label='Densità osservata (KDE)')
    except ImportError:
        kde_y = pd.Series(filtered).plot.kde(bw_method=0.2, ax=plt.gca(), color='black', lw=3.5, label='Densità osservata (KDE)').get_lines()[-1].get_ydata()

    # Fit and plot each candidate as a line, and compute all stats
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple']
    for (label, dist), color in zip(candidate_distributions.items(), colors):
        try:
            # Fit
            if dist is stats.lognorm:
                params = dist.fit(filtered, floc=0)
            else:
                params = dist.fit(filtered)
            # PDF curve
            pdf_y = dist.pdf(x, *params)
            plt.plot(x, pdf_y, color=color, lw=2.2, label=label)
            # Compute MAE vs empirical KDE
            mae = mean_absolute_error_curve(kde_y, pdf_y)
            # K-S test
            ks_stat, ks_pval = stats.kstest(filtered, dist.name, args=params)
            # Log-likelihood, AIC, BIC
            loglike = np.sum(dist.logpdf(filtered, *params))
            k = len(params)
            aic = 2*k - 2*loglike
            bic = k*np.log(len(filtered)) - 2*loglike
            fit_stats.append({
                "Distribuzione": label,
                "Parametri": params,
                "KS_pvalue": ks_pval,
                "AIC": aic,
                "BIC": bic,
                "MAE_KDE_PDF": mae
            })
            logging.info(f"{label:12s} | KS_p={ks_pval:.4f} | AIC={aic:9.2f} | BIC={bic:9.2f} | MAE={mae:8.5f}")
        except Exception as e:
            logging.warning(f"Errore fit {label}: {e}")

    plt.title("Confronto fit: densità empirica (KDE) e PDF delle distribuzioni teoriche", fontsize=17)
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
    print(stats_df[["Distribuzione", "KS_pvalue", "AIC", "BIC", "MAE_KDE_PDF"]])
    logging.info("\n" + stats_df[["Distribuzione", "KS_pvalue", "AIC", "BIC", "MAE_KDE_PDF"]].to_string(index=False))

"""
Note:
- La curva nera spessa mostra la distribuzione empirica (KDE).
- Le curve colorate sono i fit delle distribuzioni candidate.
- La tabella e il CSV riassumono tutti gli indicatori quantitativi.
"""
