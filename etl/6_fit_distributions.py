# v1
# file: 6_fit_distributions.py

"""
Script diagnostico per confrontare diverse distribuzioni sui tempi di risoluzione dei ticket.
- Carica i dati prodotti dallo script 5
- Fit lognormale, Weibull, Gamma, Esponenziale, Normale
- Logga, salva statistiche, e plottizza tutto per confronto visivo e quantitativo
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
import logging
import os

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

    # X range for PDF plotting
    x = np.linspace(filtered.min(), filtered.max(), 500)

    plt.figure(figsize=(14, 7))
    plt.hist(filtered, bins=80, density=True, alpha=0.4, label="Dati osservati (hist)", color="gray", edgecolor="black")

    # ---- Fit and plot for each distribution ----
    for label, dist in candidate_distributions.items():
        try:
            # Fit the distribution
            if dist is stats.lognorm:
                params = dist.fit(filtered, floc=0)
            else:
                params = dist.fit(filtered)
            # PDF
            pdf = dist.pdf(x, *params)
            plt.plot(x, pdf, label=label)
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
                "BIC": bic
            })
            logging.info(f"{label}: KS_pvalue={ks_pval:.4f} | AIC={aic:.1f} | BIC={bic:.1f}")
        except Exception as e:
            logging.warning(f"Errore fit {label}: {e}")

    plt.title("Fit di diverse distribuzioni sui tempi di risoluzione (0-10.000 ore)")
    plt.xlabel("Tempo di risoluzione (ore)")
    plt.ylabel("Densità (PDF)")
    plt.legend()
    plt.tight_layout()
    plt.savefig('./output/png/confronto_fit_distribuzioni.png', dpi=200)
    plt.close()
    logging.info("Grafico confronto fit salvato in ./output/png/confronto_fit_distribuzioni.png")

    # --- Save summary statistics ---
    stats_df = pd.DataFrame(fit_stats)
    stats_df.to_csv('./output/csv/distribution_fit_stats.csv', index=False)
    logging.info("Statistiche dei fit salvate in ./output/csv/distribution_fit_stats.csv")

"""
Note:
- Scegli la miglior distribuzione valutando sia K-S p-value che AIC/BIC.
- I parametri esatti delle distribuzioni sono esportati in distribution_fit_stats.csv.
- Se vuoi aggiungere altre distribuzioni, basta aggiungerle al dict candidate_distributions.
"""
