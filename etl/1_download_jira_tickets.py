# v2
# file: download_jira_tickets.py

"""
Scarica tutti i ticket Jira di Apache BookKeeper, usando la paginazione dell'API.
I risultati vengono salvati in un CSV, con logging dettagliato di ogni operazione su stdout e su file.
"""

import requests
import pandas as pd
import logging
from time import sleep

# Imposta il logging sia su file che su console per tracciare ogni operazione.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("output/logs/download_jira_tickets.log"),
        logging.StreamHandler()
    ]
)

JIRA_DOMAIN = "https://issues.apache.org/jira"
PROJECT = "BOOKKEEPER"
JQL = f'project = {PROJECT} ORDER BY created DESC'
FIELDS = "key,summary,issuetype,status,resolution,resolutiondate,created,updated,assignee,description"
BATCH_SIZE = 1000  # Jira consente max 1000 per richiesta
MAX_BATCHES = 100  # Numero massimo di batch (impostato molto alto per sicurezza)
OUT_CSV = "./output/csv/jira_issues_raw.csv"


def get_jira_issues(jql, fields, batch_size=BATCH_SIZE, max_batches=MAX_BATCHES):
    """
    Estrae tutti i ticket Jira tramite paginazione.
    """
    url = f"{JIRA_DOMAIN}/rest/api/2/search"
    all_issues = []
    start_at = 0
    for batch in range(max_batches):
        params = {
            "jql": jql,
            "fields": fields,
            "maxResults": batch_size,
            "startAt": start_at
        }
        logging.info(f"Richiesta Jira issues {start_at}–{start_at + batch_size - 1}")
        try:
            resp = requests.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logging.error(f"Errore durante la richiesta a Jira: {e}")
            break
        issues = data.get("issues", [])
        if not issues:
            logging.info("Nessun'altra issue trovata, fine della paginazione.")
            break
        all_issues.extend(issues)
        logging.info(f"Batch {batch + 1}: scaricate {len(issues)} issue, totale finora {len(all_issues)}")
        if len(issues) < batch_size:
            logging.info("Batch incompleto, raggiunta la fine delle issue disponibili.")
            break
        start_at += batch_size
        sleep(0.2)  # Attendi un attimo per evitare rate limit
    return all_issues


if __name__ == "__main__":
    logging.info("Inizio download di tutti i ticket Jira di BOOKKEEPER...")
    data = get_jira_issues(JQL, FIELDS)
    if data:
        df = pd.json_normalize(data)
        df.to_csv(OUT_CSV, index=False)
        logging.info(f"Salvati {len(df)} ticket Jira in {OUT_CSV}")
    else:
        logging.warning("Nessun ticket Jira trovato o errore durante il download.")

"""
Note operative:
- Il file di log 'download_jira_tickets.log' tiene traccia di ogni operazione e può essere allegato ai report di gruppo.
- Puoi aumentare o diminuire BATCH_SIZE/MAX_BATCHES secondo necessità (es. se il progetto cresce molto in futuro).
- La struttura del CSV è compatibile con i successivi script di cleaning e merging previsti dal workflow.
"""
