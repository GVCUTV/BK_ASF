# v7
# file: 5_estimate_parameters.py

"""
Estrazione e stima parametri fondamentali per il modello di code del workflow BookKeeper.
Usa ./output/csv/tickets_prs_merged.csv come input.
Genera e salva:
- Tassi di arrivo, tempi di servizio (fit lognormale), probabilità di feedback/riapertura.
- Metriche di performance chiave (resolution time, backlog, throughput, iterazioni feedback, utilization).
- Grafici e summary in ./output/png/ e ./output/csv/.
Logga ogni operazione su file e stdout.
"""

import pandas as pd
import numpy as np
import logging
import os
from scipy.stats import lognorm, kstest
import matplotlib.pyplot as plt

def parse_date_column(df, col):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce')
        logging.info(f"Colonna '{col}' convertita a datetime.")

def compute_phase_duration(df, start, end, label):
    if start in df.columns and end in df.columns:
        dur_col = f'{label}_duration_hours'
        df[dur_col] = (df[end] - df[start]).dt.total_seconds() / 3600
        logging.info(f"Durata '{label}' calcolata in '{dur_col}'.")
        return dur_col
    else:
        logging.warning(f"Mancano colonne '{start}' o '{end}' per '{label}'.")
        return None

def fit_and_plot(times, label):
    times = times.dropna()
    if len(times) < 5:
        logging.warning(f"Pochi campioni per {label} (n={len(times)}). Fit saltato.")
        return None, None, None, None
    shape, loc, scale = lognorm.fit(times, floc=0)
    ks_stat, ks_pval = kstest(times, 'lognorm', args=(shape, loc, scale))
    logging.info(f"{label}: fit lognormale (shape={shape:.3f}, loc={loc:.3f}, scale={scale:.3f}) - K-S p={ks_pval:.3f}")
    # Plot
    plt.figure()
    plt.hist(times, bins=30, density=True, alpha=0.5, label="Empirica")
    x = np.linspace(times.min(), times.max(), 100)
    plt.plot(x, lognorm.pdf(x, shape, loc, scale), label="Fit lognormale")
    plt.title(f"{label}: Fit Lognormale")
    plt.xlabel('Durata (ore)')
    plt.ylabel('Densità')
    plt.legend()
    plt.savefig(f'./output/png/{label}_lognorm_fit.png')
    plt.close()
    logging.info(f"Grafico fit {label} salvato.")
    return shape, loc, scale, ks_pval

def feedback_prob(df, col, label):
    if col in df.columns:
        p = (df[col].fillna(0) > 0).mean()
        logging.info(f"Probabilità feedback {label}: {p:.3f}")
        return p
    else:
        logging.warning(f"Colonna '{col}' mancante per feedback {label}.")
        return np.nan

if __name__ == "__main__":
    # ==== Logging setup ====
    os.makedirs('./output/logs', exist_ok=True)
    os.makedirs('./output/csv', exist_ok=True)
    os.makedirs('./output/png', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("./output/logs/estimate_parameters.log"),
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

    # ==== Gestione colonne data ====
    for col in ['created', 'closed', 'dev_review_start', 'dev_review_end', 'test_start', 'test_end']:
        parse_date_column(df, col)

    # ==== 1. Tasso di arrivo ====
    if 'created' in df.columns:
        df = df.sort_values('created')
        df['inter_arrival'] = df['created'].diff().dt.total_seconds() / 3600  # ore
        mean_interarrival = df['inter_arrival'].mean()
        arrival_rate = 1 / mean_interarrival if mean_interarrival and mean_interarrival > 0 else np.nan
        logging.info(f"Tasso di arrivo stimato (ticket/ora): {arrival_rate:.5f}")
    else:
        arrival_rate = np.nan
        logging.warning("Colonna 'created' mancante: impossibile stimare il tasso di arrivo.")

    # ==== 2. Tempi di servizio per fase ====
    devrev_col = compute_phase_duration(df, 'dev_review_start', 'dev_review_end', 'dev_review')
    test_col   = compute_phase_duration(df, 'test_start', 'test_end', 'test')

    phase_stats = {}
    for col, label in [(devrev_col, "DevReview"), (test_col, "TestQA")]:
        if col:
            mean, median = df[col].mean(), df[col].median()
            shape, loc, scale, ks_pval = fit_and_plot(df[col], label)
            phase_stats[label] = dict(
                mean=mean, median=median,
                lognorm_shape=shape, lognorm_loc=loc, lognorm_scale=scale,
                ks_pval=ks_pval
            )

    # ==== 3. Probabilità di feedback e reopening ====
    p_review = feedback_prob(df, 'review_feedback_count', 'review')
    p_test   = feedback_prob(df, 'test_feedback_count', 'test')
    p_reopen = feedback_prob(df, 'reopened_count', 'reopen')

    # ==== 4. Metriche chiave ====
    # -- Resolution time --
    if {'created', 'closed'}.issubset(df.columns):
        df['resolution_time_hours'] = (df['closed'] - df['created']).dt.total_seconds() / 3600
        mean_res = df['resolution_time_hours'].mean()
        median_res = df['resolution_time_hours'].median()
        logging.info(f"Resolution time medio: {mean_res:.2f} h, mediana: {median_res:.2f} h")
    else:
        mean_res = median_res = np.nan
        logging.warning("Impossibile calcolare la resolution time: colonne mancanti.")

    # -- Backlog over time --
    if {'created', 'closed'}.issubset(df.columns):
        date_range = pd.date_range(df['created'].min(), df['closed'].max(), freq='D')
        backlog = []
        for day in date_range:
            n_open = ((df['created'] <= day) & ((df['closed'] > day) | df['closed'].isnull())).sum()
            backlog.append(n_open)
        plt.figure()
        plt.plot(date_range, backlog)
        plt.title("Backlog (Ticket aperti) nel tempo")
        plt.xlabel("Data")
        plt.ylabel("Ticket aperti")
        plt.savefig('./output/png/backlog_over_time.png')
        plt.close()
        logging.info("Grafico backlog nel tempo salvato.")
    else:
        logging.warning("Impossibile plottare backlog: colonne data mancanti.")

    # -- Iterazioni feedback --
    if {'review_feedback_count', 'test_feedback_count'}.issubset(df.columns):
        df['total_feedback'] = df['review_feedback_count'].fillna(0) + df['test_feedback_count'].fillna(0)
        mean_loops = df['total_feedback'].mean()
        median_loops = df['total_feedback'].median()
        logging.info(f"Iterazioni feedback medie: {mean_loops:.2f}, mediana: {median_loops:.2f}")
    else:
        mean_loops = median_loops = np.nan
        logging.warning("Impossibile calcolare iterazioni feedback: colonne mancanti.")

    # -- Throughput mensile --
    if 'closed' in df.columns:
        df['closed_month'] = pd.to_datetime(df['closed']).dt.to_period('M')
        throughput_monthly = df.groupby('closed_month').size()
        throughput_mean = throughput_monthly.mean()
        logging.info(f"Throughput mensile medio: {throughput_mean:.2f} ticket/mese")
    else:
        throughput_mean = np.nan
        logging.warning("Impossibile calcolare throughput: colonna 'closed' mancante.")

    # -- Utilization --
    if arrival_rate and devrev_col:
        utilization = arrival_rate * df[devrev_col].mean()
        logging.info(f"Utilization stimata (Dev+Review): {utilization:.3f}")
    else:
        utilization = np.nan
        logging.warning("Impossibile stimare utilization: dati mancanti.")

    # ==== 5. Export summary ====
    results = {
        "arrival_rate_per_hour": arrival_rate,
        "mean_resolution_time_hours": mean_res,
        "median_resolution_time_hours": median_res,
        "feedback_review_prob": p_review,
        "feedback_test_prob": p_test,
        "reopen_rate": p_reopen,
        "mean_feedback_iterations": mean_loops,
        "median_feedback_iterations": median_loops,
        "throughput_monthly_mean": throughput_mean,
        "utilization_estimate": utilization,
    }
    for phase, stats in phase_stats.items():
        for k, v in stats.items():
            results[f"{phase}_{k}"] = v

    pd.DataFrame([results]).to_csv('./output/csv/parameter_estimates.csv', index=False)
    logging.info("Parametri e metriche salvati in ./output/csv/parameter_estimates.csv")
    logging.info("=== STIMA PARAMETRI COMPLETATA ===")

"""
Note:
- Tutto viene loggato in ./output/logs/estimate_parameters.log.
- Output: ./output/csv/parameter_estimates.csv e ./output/png/*.png.
- Puoi adattare i nomi colonne se cambiano nel merge o cleaning.
- Script pronto per inserimento in pipeline automatica e reportistica.
"""
