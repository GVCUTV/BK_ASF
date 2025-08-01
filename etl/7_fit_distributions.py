# v2
# file: 7_fit_distributions.py

"""
Fit e confronto visivo/quantitativo di distribuzioni candidate sui tempi di risoluzione.
- Histogram ben visibile
- Fit di: lognormale, Weibull, Gamma, Esponenziale, Normale (PDF)
- MAE fra istogramma osservato e PDF di ogni distribuzione
- Tutte le statistiche (KS, AIC, BIC, MAE) salvate e mostrate
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
import logging
import os

def mean_absolute_error_hist_pdf(data, pdf_func, bins):
    """Compute MAE between normalized histogram and PDF curve, for fair comparison."""
    hist_vals, bin_edges = np.histogram(data, bins=bins, density=True)
    # Bin centers for comparison
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    pdf_vals = pdf_func(bin_centers)
    mae = np.mean(np.abs(hist_vals - pdf_vals))
    return mae

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
    # For reproducible bins and PDF/MAE calculation
    bins = np.linspace(filtered.min(), filtered.max(), 120)

    # Plot: data histogram as filled bars, high alpha
    plt.figure(figsize=(16, 7))
    hist_vals, _, _ = plt.hist(filtered, bins=bins, density=True,
                               alpha=0.5, color="tab:blue",
                               edgecolor="black", label="Dati osservati", linewidth=1.3)
    # X for PDF plotting
    x = np.linspace(filtered.min(), filtered.max(), 1000)

    # ---- Fit, plot, compute metrics for each distribution ----
    for label, dist in candidate_distributions.items():
        try:
            # Fit the distribution
            if dist is stats.lognorm:
                params = dist.fit(filtered, floc=0)
            else:
                params = dist.fit(filtered)
            # PDF and MAE
            pdf = dist.pdf(x, *params)
            # For MAE, match binning of histogram
            pdf_func = lambda z: dist.pdf(z, *params)
            mae = mean_absolute_error_hist_pdf(filtered, pdf_func, bins)
            # Plot with strong line
            plt.plot(x, pdf, label=f"{label}", linewidth=2.8)
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
                "MAE_hist_pdf": mae
            })
            logging.info(f"{label:12s} | KS_p={ks_pval:.4f} | AIC={aic:9.2f} | BIC={bic:9.2f} | MAE={mae:8.5f}")
        except Exception as e:
            logging.warning(f"Errore fit {label}: {e}")

    plt.title("Confronto Fit: Tempi di Risoluzione (0-10.000 ore)", fontsize=17)
    plt.xlabel("Tempo di risoluzione (ore)", fontsize=15)
    plt.ylabel("Densità (PDF)", fontsize=15)
    plt.legend(fontsize=12, frameon=True)
    plt.tight_layout()
    plt.savefig('./output/png/confronto_fit_distribuzioni.png', dpi=200)
    plt.close()
    logging.info("Grafico confronto fit salvato in ./output/png/confronto_fit_distribuzioni.png")

    # --- Save and print summary statistics (sorted by MAE) ---
    stats_df = pd.DataFrame(fit_stats)
    stats_df = stats_df.sort_values("MAE_hist_pdf")
    stats_df.to_csv('./output/csv/distribution_fit_stats.csv', index=False)
    print("\n=== SOMMARIO FIT DISTRIBUZIONI (ordinato per MAE) ===\n")
    print(stats_df[["Distribuzione", "KS_pvalue", "AIC", "BIC", "MAE_hist_pdf"]])
    logging.info("\n" + stats_df[["Distribuzione", "KS_pvalue", "AIC", "BIC", "MAE_hist_pdf"]].to_string(index=False))

"""
Note:
- L'istogramma (area blu) mostra la distribuzione reale.
- Le curve spesse mostrano il fit di ciascuna distribuzione.
- Scegli la "migliore" combinando MAE, p-value, AIC e BIC.
- Tutte le statistiche sono esportate e stampate/visibili a colpo d'occhio.
"""
