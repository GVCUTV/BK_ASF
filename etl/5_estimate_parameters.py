# v13
# file: 5_estimate_parameters.py

"""
Stima parametri globali E PER-FASE (Development / Review / Testing) con durate in GIORNI.
Output:
- ./output/csv/phase_durations_wide.csv    (key, dev_duration_days, review_duration_days, test_duration_days)
- ./output/csv/phase_summary_stats.csv     (statistiche per fase)
- ./output/csv/parameter_estimates.csv     (arrivals/giorno, resolution time globale, throughput mensile)
- ./output/png/backlog_over_time.png       (serie temporale backlog)
"""

import pandas as pd
import numpy as np
import logging
import os
import matplotlib.pyplot as plt
from path_config import PROJECT_ROOT

def summarize_phase(series, name):
    """Statistiche robuste sulla fase (giorni)."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    return {
        "phase": name,
        "count": int(s.size),
        "nan_share": float(1.0 - (s.size / max(1, len(series)))),
        "mean_d": float(s.mean()) if s.size else np.nan,
        "median_d": float(s.median()) if s.size else np.nan,
        "std_d": float(s.std()) if s.size else np.nan,
        "p25_d": float(s.quantile(0.25)) if s.size else np.nan,
        "p75_d": float(s.quantile(0.75)) if s.size else np.nan,
        "min_d": float(s.min()) if s.size else np.nan,
        "max_d": float(s.max()) if s.size else np.nan,
    }

if __name__ == "__main__":
    # Setup logging/output dirs
    os.makedirs(PROJECT_ROOT+'/etl/output/logs', exist_ok=True)
    os.makedirs(PROJECT_ROOT+'/etl/output/csv', exist_ok=True)
    os.makedirs(PROJECT_ROOT+'/etl/output/png', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(PROJECT_ROOT+"/etl/output/logs/estimate_parameters.log"), logging.StreamHandler()]
    )

    IN_CSV = PROJECT_ROOT+"/etl/output/csv/tickets_prs_merged.csv"

    try:
        df = pd.read_csv(IN_CSV, low_memory=False)
        logging.info(f"Caricato dataset: {IN_CSV} ({len(df)})")
    except Exception as e:
        logging.error(f"Errore caricando il file CSV: {e}")
        raise SystemExit(1)

    # Date parsing
    for col in ['fields.created', 'fields.resolutiondate']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', utc=True).dt.tz_convert(None)
            logging.info(f"Colonna '{col}' convertita a datetime (naive).")

    # Arrival rate (ticket/giorno)
    if 'fields.created' in df.columns:
        df = df.sort_values('fields.created')
        df['inter_arrival_days'] = df['fields.created'].diff().dt.total_seconds() / 86400.0
        mean_interarrival = df['inter_arrival_days'].mean()
        arrival_rate = 1 / mean_interarrival if mean_interarrival and mean_interarrival > 0 else np.nan
        if not np.isnan(arrival_rate):
            logging.info(f"Tasso di arrivo stimato: {arrival_rate:.6f} ticket/giorno")
        else:
            logging.info("Tasso di arrivo: n/a")
    else:
        arrival_rate = np.nan
        logging.warning("Colonna 'fields.created' mancante: impossibile stimare il tasso di arrivo.")

    # Resolution time globale (giorni)
    if {'fields.created', 'fields.resolutiondate'}.issubset(df.columns):
        df['resolution_time_days'] = (df['fields.resolutiondate'] - df['fields.created']).dt.total_seconds() / 86400.0
        mean_res = df['resolution_time_days'].mean()
        median_res = df['resolution_time_days'].median()
        logging.info(f"Resolution time: mean={mean_res:.2f} d | median={median_res:.2f} d")
    else:
        mean_res = median_res = np.nan
        logging.warning("Impossibile calcolare la resolution time: colonne mancanti.")

    # Backlog plot
    if 'fields.created' in df.columns:
        end_date = df['fields.resolutiondate'].max() if 'fields.resolutiondate' in df.columns and df['fields.resolutiondate'].notna().any() else df['fields.created'].max()
        date_range = pd.date_range(df['fields.created'].min(), end_date, freq='D')
        backlog = []
        for day in date_range:
            n_open = ((df['fields.created'] <= day) & ((df.get('fields.resolutiondate', pd.NaT) > day) | df.get('fields.resolutiondate').isnull())).sum()
            backlog.append(n_open)
        plt.figure()
        plt.plot(date_range, backlog)
        plt.title("Backlog (Ticket aperti) nel tempo")
        plt.xlabel("Data")
        plt.ylabel("Ticket aperti")
        plt.tight_layout()
        plt.savefig(PROJECT_ROOT+'/etl/output/png/backlog_over_time.png')
        plt.close()
        logging.info("Grafico backlog nel tempo salvato in ./output/png/backlog_over_time.png")
    else:
        logging.warning("Impossibile plottare backlog: mancano le date di creazione.")

    # Throughput mensile
    if 'fields.resolutiondate' in df.columns:
        df['resolution_month'] = pd.to_datetime(df['fields.resolutiondate'], errors='coerce').dt.to_period('M')
        throughput_monthly = df.groupby('resolution_month').size()
        throughput_mean = float(throughput_monthly.mean()) if throughput_monthly.size else np.nan
        logging.info(f"Throughput medio mensile: {throughput_mean:.2f} ticket/mese" if not np.isnan(throughput_mean) else "Throughput medio mensile: n/a")
    else:
        throughput_mean = np.nan
        logging.warning("Impossibile calcolare throughput: 'fields.resolutiondate' mancante.")

    # Per‑fase durate (in giorni)
    phase_cols = ["dev_duration_days", "review_duration_days", "test_duration_days"]
    missing = [c for c in phase_cols if c not in df.columns]
    if missing:
        logging.warning(f"Colonne fase mancanti nel dataset: {missing}. Esegui 3_clean_and_merge.py v7 prima di questo script.")

    # Export wide durations
    durations_out = PROJECT_ROOT+"/etl/output/csv/phase_durations_wide.csv"
    base_cols = ["key"] if "key" in df.columns else []
    export_cols = base_cols + [c for c in phase_cols if c in df.columns]
    df_out = df[export_cols].copy()
    df_out.to_csv(durations_out, index=False)
    logging.info(f"Esportate durate per fase in {durations_out}")

    # Summaries
    summaries = []
    for col in phase_cols:
        if col in df.columns:
            summaries.append(summarize_phase(df[col], col))
    summary_df = pd.DataFrame(summaries)
    summary_path = PROJECT_ROOT+"/etl/output/csv/phase_summary_stats.csv"
    summary_df.to_csv(summary_path, index=False)
    logging.info(f"Statistiche per fase salvate in {summary_path}\n{summary_df.to_string(index=False)}")

    # Export parametri globali
    results = {
        "arrival_rate_per_day": arrival_rate,
        "mean_resolution_time_days": mean_res,
        "median_resolution_time_days": median_res,
        "throughput_monthly_mean": throughput_mean
    }
    pd.DataFrame([results]).to_csv(PROJECT_ROOT+'/etl/output/csv/parameter_estimates.csv', index=False)
    logging.info("Parametri chiave salvati in ./output/csv/parameter_estimates.csv")
    logging.info("=== ESTRAZIONE PARAMETRI COMPLETATA ===")
