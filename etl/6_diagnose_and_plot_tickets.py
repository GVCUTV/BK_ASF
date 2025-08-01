# v1
# file: 6_diagnose_and_plot_tickets.py

"""
Per ogni ticket nel file tickets_prs_merged.csv stampa tutte le informazioni rilevanti per analisi/diagnosi,
segnala possibili incongruenze e salva il grafico dei tempi di risoluzione.
Log dettagliato su file e console.
"""

import pandas as pd
import logging
import os
import matplotlib.pyplot as plt

if __name__ == "__main__":
    # === Setup logging/output dirs ===
    os.makedirs('./output/logs', exist_ok=True)
    os.makedirs('./output/png', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("./output/logs/diagnose_tickets.log"),
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

    # --- Convert datetime columns if present ---
    for col in ['fields.created', 'fields.resolutiondate']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            logging.info(f"Colonna '{col}' convertita a datetime.")

    # --- Prepare output for diagnosis ---
    print_fields = [
        "key",
        "fields.issuetype.name",
        "fields.status.name",
        "fields.resolution.name",
        "fields.created",
        "fields.resolutiondate",
        "fields.assignee.displayName" if "fields.assignee.displayName" in df.columns else None,
        "summary" if "summary" in df.columns else None,
        "title" if "title" in df.columns else None,
        "created_at" if "created_at" in df.columns else None,
        "closed_at" if "closed_at" in df.columns else None,
        "jira_key" if "jira_key" in df.columns else None,
    ]
    print_fields = [f for f in print_fields if f is not None]

    # --- Compute resolution time if possible ---
    if {'fields.created', 'fields.resolutiondate'}.issubset(df.columns):
        df['resolution_time_hours'] = (df['fields.resolutiondate'] - df['fields.created']).dt.total_seconds() / 3600
    else:
        df['resolution_time_hours'] = None

    logging.info("Inizio stampa diagnostica ticket:")
    for idx, row in df.iterrows():
        info = {f: row[f] if f in row else None for f in print_fields}
        # Basic print for easy review
        print(f"\n=== TICKET #{idx+1} ===")
        for k, v in info.items():
            print(f"{k:30s}: {v}")
        # Resolution time
        res_time = row['resolution_time_hours']
        print(f"{'resolution_time_hours':30s}: {res_time}")
        # --- Diagnostic checks ---
        issues = []
        # Key should never be missing
        if pd.isnull(row.get("key", None)):
            issues.append("MANCANTE: chiave ticket")
        # Created date should not be missing
        if 'fields.created' in df.columns and pd.isnull(row['fields.created']):
            issues.append("MANCANTE: data creazione")
        # Resolution date should not be before creation
        if ('fields.created' in df.columns and 'fields.resolutiondate' in df.columns
            and pd.notnull(row['fields.created']) and pd.notnull(row['fields.resolutiondate'])
            and row['fields.resolutiondate'] < row['fields.created']):
            issues.append("INCONGRUENZA: risoluzione prima della creazione")
        # Resolution time negative or null
        if res_time is not None and pd.notnull(res_time) and res_time < 0:
            issues.append("INCONGRUENZA: durata negativa")
        # Tickets with resolution status but no resolutiondate
        if ("fields.status.name" in df.columns and "fields.resolutiondate" in df.columns and
            row.get("fields.status.name", "").lower() in ["closed", "resolved"] and pd.isnull(row['fields.resolutiondate'])):
            issues.append("INCONGRUENZA: ticket chiuso senza data risoluzione")
        # Print issues if any
        if issues:
            print("*** DIAGNOSTICA: " + " | ".join(issues))
            logging.warning(f"Ticket key={row.get('key', '???')}: " + " | ".join(issues))

    # --- Plot distribution of resolution times: only 0-10,000h range, max resolution ---
    if 'resolution_time_hours' in df.columns and df['resolution_time_hours'].notnull().any():
        filtered = df[(df['resolution_time_hours'] >= 0) & (df['resolution_time_hours'] <= 10000)][
            'resolution_time_hours']
        if len(filtered) > 0:
            plt.figure(figsize=(14, 6))
            bins = min(1000, max(20, int(len(filtered) / 3)))  # Dynamically choose bin count for detail
            plt.hist(filtered, bins=bins, alpha=0.85, edgecolor="black")
            plt.title("Distribuzione dei tempi di risoluzione (0-10.000 ore)", fontsize=15)
            plt.xlabel("Tempo di risoluzione (ore)", fontsize=13)
            plt.ylabel("Numero di ticket", fontsize=13)
            plt.xlim(0, 10000)
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            plt.savefig('./output/png/distribuzione_resolution_times_0_10000.png', dpi=200)
            plt.close()
            logging.info(
                "Grafico distribuzione tempi di risoluzione (0-10.000h) salvato in ./output/png/distribuzione_resolution_times_0_10000.png")
        else:
            logging.warning("Nessun ticket con tempo di risoluzione tra 0 e 10.000 ore.")
    else:
        logging.warning("Impossibile plottare la distribuzione dei tempi di risoluzione: dati mancanti.")

    logging.info("Analisi diagnostica completata.")

"""
Note:
- Ogni ticket viene stampato con tutte le informazioni disponibili e diagnosticato per incongruenze.
- Il log contiene warning per ticket problematici.
- La distribuzione dei tempi di risoluzione è utile per individuare outlier o dati sospetti.
"""
