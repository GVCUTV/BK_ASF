# v1
# file: summarize_and_plot.py

"""
Calcola statistiche base, stampa tabella, mostra grafici.
"""

import pandas as pd
import logging
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("./output/logs/summarize_and_plot.log"),
        logging.StreamHandler()
    ]
)
IN_CSV = "./output/csv/tickets_prs_merged.csv"

if __name__ == "__main__":
    df = pd.read_csv(IN_CSV)

    # Numero totale ticket
    total = len(df)
    logging.info(f"Ticket totali: {total}")

    # Suddivisione per tipo
    type_counts = df['fields.issuetype.name'].value_counts()
    print("Suddivisione per tipo:\n", type_counts)

    # Ticket riaperti
    reopened = df[df['fields.status.name'].str.contains("Reopen", na=False)]
    logging.info(f"Ticket riaperti: {len(reopened)} ({len(reopened)/total*100:.1f}%)")

    # Ticket in progress
    in_progress = df[df['fields.status.name'] == "In Progress"]
    logging.info(f"In Progress: {len(in_progress)} ({len(in_progress)/total*100:.1f}%)")

    # Ticket chiusi senza PR
    closed_no_pr = df[
        (df['fields.status.name'].isin(["Closed", "Resolved"])) &
        (df['jira_key'].isnull())
    ]
    logging.info(f"Ticket chiusi senza PR: {len(closed_no_pr)} ({len(closed_no_pr)/total*100:.1f}%)")

    # Tabella finale
    summary = pd.DataFrame({
        "Tipo": type_counts.index,
        "Numero": type_counts.values,
        "% Totale": [f"{x/total*100:.1f}%" for x in type_counts.values]
    })
    print("\nTabella riassuntiva:\n", summary.to_string(index=False))

    # Grafico torta
    plt.figure(figsize=(6,6))
    plt.pie(type_counts, labels=type_counts.index, autopct='%1.1f%%', startangle=90)
    plt.title("Distribuzione Ticket per Tipo")
    plt.tight_layout()
    plt.savefig("./output/png/distribuzione_ticket_tipo.png")

    # Export summary
    summary.to_csv("./output/csv/statistiche_riassuntive.csv", index=False)
    logging.info("Statistiche esportate in ./output/csv/statistiche_riassuntive.csv")
