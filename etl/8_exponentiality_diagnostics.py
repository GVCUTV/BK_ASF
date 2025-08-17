# v1
# file: 8_exponentiality_diagnostics.py

"""
Diagnostic suite for testing whether empirical data is truly exponential,
or better fits heavy-tailed distributions (Weibull, lognormal, etc).
Outputs plots and quantitative metrics for critical project decisions.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as stats
import logging
import os

# Set up output
os.makedirs('../simulation/output/png', exist_ok=True)
os.makedirs('../simulation/output/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("../simulation/output/logs/exponentiality_diag.log"),
        logging.StreamHandler()
    ]
)

IN_CSV = "./output/csv/tickets_prs_merged.csv"
df = pd.read_csv(IN_CSV)
if 'fields.created' in df.columns and 'fields.resolutiondate' in df.columns:
    df['fields.created'] = pd.to_datetime(df['fields.created'], errors='coerce')
    df['fields.resolutiondate'] = pd.to_datetime(df['fields.resolutiondate'], errors='coerce')
    df['resolution_time_hours'] = (df['fields.resolutiondate'] - df['fields.created']).dt.total_seconds() / 3600

filtered = df[(df['resolution_time_hours'] > 0) & (df['resolution_time_hours'] < 10000)]['resolution_time_hours'].dropna()
if len(filtered) < 10:
    logging.error("Too few valid data points for diagnostics.")
    exit(1)
logging.info(f"Filtered data count: {len(filtered)}")

x = np.linspace(filtered.min(), filtered.max(), 1000)
kde = stats.gaussian_kde(filtered)
kde_y = kde(x)

# --- Fit candidate distributions ---
distros = {
    'Exp': stats.expon,
    'Norm': stats.norm,
    'Lognorm': stats.lognorm,
    'Weibull': stats.weibull_min
}
fitparams = {}
for name, dist in distros.items():
    try:
        if name == 'Lognorm':
            params = dist.fit(filtered, floc=0)
        elif name == 'Weibull':
            params = dist.fit(filtered, floc=0)
        else:
            params = dist.fit(filtered)
        fitparams[name] = params
        logging.info(f"{name} fit params: {params}")
    except Exception as e:
        logging.warning(f"{name} fit failed: {e}")

# --- Histogram + fitted curves ---
plt.figure(figsize=(16,7))
plt.hist(filtered, bins=40, density=True, alpha=0.3, color='gray', label='Empirical histogram')
plt.plot(x, kde_y, 'k-', lw=2.5, label='Empirical KDE')
for name, dist in distros.items():
    if name in fitparams:
        plt.plot(x, dist.pdf(x, *fitparams[name]), lw=2, label=name)
plt.title("Histogram & Fitted Distribution PDFs")
plt.xlabel("Resolution time (h)")
plt.ylabel("Density")
plt.legend()
plt.tight_layout()
plt.savefig('./output/png/diagnostic_hist_fit.png', dpi=200)
plt.close()

# --- CDF comparison ---
plt.figure(figsize=(16,7))
sorted_data = np.sort(filtered)
emp_cdf = np.arange(1, len(sorted_data)+1)/len(sorted_data)
plt.plot(sorted_data, emp_cdf, 'k-', lw=2, label='Empirical CDF')
for name, dist in distros.items():
    if name in fitparams:
        cdf_theo = dist.cdf(sorted_data, *fitparams[name])
        plt.plot(sorted_data, cdf_theo, lw=2, label=f"{name} CDF")
plt.title("Empirical vs Theoretical CDFs")
plt.xlabel("Resolution time (h)")
plt.ylabel("CDF")
plt.legend()
plt.tight_layout()
plt.savefig('./output/png/diagnostic_cdf.png', dpi=200)
plt.close()

# --- Q-Q plots ---
for name, dist in distros.items():
    if name in fitparams:
        plt.figure(figsize=(8,8))
        stats.probplot(filtered, dist=dist, sparams=fitparams[name], plot=plt)
        plt.title(f"Q-Q Plot vs {name}")
        plt.tight_layout()
        plt.savefig(f'./output/png/diagnostic_qq_{name}.png', dpi=200)
        plt.close()

# --- Log-survival plot (should be straight for exponential) ---
plt.figure(figsize=(16,7))
surv_emp = 1 - emp_cdf
plt.semilogy(sorted_data, surv_emp, 'k-', lw=2, label='Empirical survival')
for name, dist in distros.items():
    if name in fitparams:
        surv_theo = 1 - dist.cdf(sorted_data, *fitparams[name])
        plt.semilogy(sorted_data, surv_theo, lw=2, label=f"{name} survival")
plt.title("Log-survival plot: heavy tail test (straight line = exponential)")
plt.xlabel("Resolution time (h)")
plt.ylabel("log Survival P(T>t)")
plt.legend()
plt.tight_layout()
plt.savefig('./output/png/diagnostic_logsurv.png', dpi=200)
plt.close()

# --- Skewness and Kurtosis ---
emp_skew = stats.skew(filtered)
emp_kurt = stats.kurtosis(filtered)
print(f"\nEmpirical Skewness: {emp_skew:.3f}")
print(f"Empirical Kurtosis: {emp_kurt:.3f}")

# --- KS tests (vs data) ---
print("\nKolmogorov-Smirnov p-values:")
for name, dist in distros.items():
    if name in fitparams:
        ks = stats.kstest(filtered, dist.name, args=fitparams[name])
        print(f"{name}: p={ks.pvalue:.4g}")

print("\nCheck PNGs in ./output/png/:")
print(" - diagnostic_hist_fit.png")
print(" - diagnostic_cdf.png")
print(" - diagnostic_qq_*.png")
print(" - diagnostic_logsurv.png\n")

logging.info(f"Empirical skew: {emp_skew:.3f}, kurtosis: {emp_kurt:.3f}")
