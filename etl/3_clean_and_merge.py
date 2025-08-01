# v1
# file: 3_clean_and_merge.py

"""
Pulizia dei ticket, rimozione duplicati/wont-fix, uniforma le date e cerca link ticket-PR tramite key nel titolo.
Salva i dati puliti e mergeati.
"""

import pandas as pd
import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("./output/logs/clean_and_merge.log"),
        logging.StreamHandler()
    ]
)
JIRA_CSV = "./output/csv/jira_issues_raw.csv"
PRS_CSV = "./output/csv/github_prs_raw.csv"
OUT_TICKET_CSV = "./output/csv/jira_issues_clean.csv"
OUT_PR_CSV = "./output/csv/github_prs_clean.csv"
OUT_MERGE_CSV = "./output/csv/tickets_prs_merged.csv"


def extract_jira_key(text):
    """Estrae la chiave Jira dal testo (es: BOOKKEEPER-1234)."""
    if pd.isnull(text):
        return None
    m = re.search(r'BOOKKEEPER-\d+', text)
    return m.group(0) if m else None


def clean_tickets(df):
    # Rimuovi duplicati su key
    df = df.drop_duplicates(subset=["key"])
    # Filtra ticket inutili
    bad_resolutions = ["Won't Fix", "Duplicate", "Not A Problem", "Incomplete", "Cannot Reproduce"]
    df = df[~df['fields.resolution.name'].isin(bad_resolutions)]
    # Uniforma le date
    df["created"] = pd.to_datetime(df["fields.created"], errors='coerce')
    df["resolved"] = pd.to_datetime(df["fields.resolutiondate"], errors='coerce')
    return df


def clean_prs(df):
    df["jira_key"] = df["title"].apply(extract_jira_key)
    return df


if __name__ == "__main__":
    # Ticket
    tickets = pd.read_csv(JIRA_CSV)
    tickets_clean = clean_tickets(tickets)
    tickets_clean.to_csv(OUT_TICKET_CSV, index=False)
    logging.info(f"Salvati {len(tickets_clean)} ticket puliti in {OUT_TICKET_CSV}")

    # PRs
    prs = pd.read_csv(PRS_CSV)
    prs_clean = clean_prs(prs)
    prs_clean.to_csv(OUT_PR_CSV, index=False)
    logging.info(f"Salvate {len(prs_clean)} PR pulite in {OUT_PR_CSV}")

    # Merge per key
    merged = pd.merge(tickets_clean, prs_clean, left_on="key", right_on="jira_key", how="left",
                      suffixes=("_ticket", "_pr"))
    merged.to_csv(OUT_MERGE_CSV, index=False)
    logging.info(f"Salvati dati mergeati (ticket+PR) in {OUT_MERGE_CSV}")
