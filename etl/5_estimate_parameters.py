# v8
# file: 5_estimate_parameters.py

"""
Estrazione dei parametri dal file tickets_prs_merged.csv.
Compatibile con le colonne effettivamente prodotte dagli script precedenti (no phase, no feedback count espliciti).
Calcola tasso di arrivo, risoluzione, backlog, throughput, e segnala se certi dati non sono presenti.
Log dettagliato in ./output/logs/estimate_parameters.log.
"""

import pandas as pd
import numpy as np
import logging
import os
import matplotlib.pyplot as plt

if __name__ == "__main__":
    # === Setup logging/output dirs ===
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

    # --- Use JIRA creation and resolution fields ---
    for col in ['fields.created', 'fields.resolutiondate']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            logging.info(f"Colonna '{col}' convertita a datetime.")

    # === 1. Arrival rate (new ticket per hour) ===
    if 'fields.created' in df.columns:
        df = df.sort_values('fields.created')
        df['inter_arrival'] = df['fields.created'].diff().dt.total_seconds() / 3600  # ore
        mean_interarrival = df['inter_arrival'].mean()
        arrival_rate = 1 / mean_interarrival if mean_interarrival and mean_interarrival > 0 else np.nan
        logging.info(f"Tasso di arrivo stimato (ticket/ora): {arrival_rate:.5f}")
    else:
        arrival_rate = np.nan
        logging.warning("Colonna 'fields.created' mancante: impossibile stimare il tasso di arrivo.")

    # === 2. Resolution time (from creation to resolution) ===
    if {'fields.created', 'fields.resolutiondate'}.issubset(df.columns):
        df['resolution_time_hours'] = (df['fields.resolutiondate'] - df['fields.created']).dt.total_seconds() / 3600
        mean_res = df['resolution_time_hours'].mean()
        median_res = df['resolution_time_hours'].median()
        logging.info(f"Resolution time media: {mean_res:.2f} h, mediana: {median_res:.2f} h")
    else:
        mean_res = median_res = np.nan
        logging.warning("Impossibile calcolare la resolution time: colonne mancanti.")

    # === 3. Backlog over time ===
    if {'fields.created', 'fields.resolutiondate'}.issubset(df.columns):
        date_range = pd.date_range(df['fields.created'].min(), df['fields.resolutiondate'].max(), freq='D')
        backlog = []
        for day in date_range:
            n_open = ((df['fields.created'] <= day) & ((df['fields.resolutiondate'] > day) | df['fields.resolutiondate'].isnull())).sum()
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

    # === 4. Throughput mensile (resolved per month) ===
    if 'fields.resolutiondate' in df.columns:
        df['resolution_month'] = df['fields.resolutiondate'].dt.to_period('M')
        throughput_monthly = df.groupby('resolution_month').size()
        throughput_mean = throughput_monthly.mean()
        logging.info(f"Throughput medio mensile: {throughput_mean:.2f} ticket/mese")
    else:
        throughput_mean = np.nan
        logging.warning("Impossibile calcolare throughput: colonna 'fields.resolutiondate' mancante.")

    # === 5. Reopen rate (approximate: count "Reopened" in status history, if any) ===
    # Your merged does not contain a reopen count, but we can approximate from status
    if 'fields.status.name' in df.columns:
        reopened_tickets = df['fields.status.name'].str.contains('Reopen', na=False)
        reopen_rate = reopened_tickets.mean()
        logging.info(f"Reopen rate stimato: {reopen_rate:.3f}")
    else:
        reopen_rate = np.nan
        logging.warning("Impossibile stimare reopen rate: colonna 'fields.status.name' mancante.")

    # === 6. Issue type stats (bug/feature) ===
    if 'fields.issuetype.name' in df.columns:
        type_counts = df['fields.issuetype.name'].value_counts()
        logging.info(f"Suddivisione ticket per tipo:\n{type_counts}")
    else:
        type_counts = None

    # === 7. Export summary ===
    results = {
        "arrival_rate_per_hour": arrival_rate,
        "mean_resolution_time_hours": mean_res,
        "median_resolution_time_hours": median_res,
        "reopen_rate": reopen_rate,
        "throughput_monthly_mean": throughput_mean
    }
    pd.DataFrame([results]).to_csv('./output/csv/parameter_estimates.csv', index=False)
    logging.info("Parametri chiave salvati in ./output/csv/parameter_estimates.csv")
    logging.info("=== ESTRAZIONE PARAMETRI COMPLETATA ===")

"""
Note:
- Compatibile solo con le colonne realmente prodotte dagli script precedenti!
- Usiamo fields.created e fields.resolutiondate come timestamp principali.
- Nessun fit di fasi o feedback: mancano dati per farlo, va documentato nel report.
- Output: ./output/csv/parameter_estimates.csv e ./output/png/backlog_over_time.png.
- Tutto loggato in ./output/logs/estimate_parameters.log.
"""
