# v3
# file: download_github_prs.py

"""
Scarica tutte le Pull Request di Apache BookKeeper e le salva in CSV.
Usa autenticazione tramite token personale GitHub per aumentare il rate limit delle API.
Token preso da variabile d'ambiente GITHUB_TOKEN o direttamente dal codice.
"""

import requests
import pandas as pd
import logging
import os
from time import sleep

# Crea le cartelle di output se non esistono
os.makedirs("./output/logs", exist_ok=True)
os.makedirs("./output/csv", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("./output/logs/download_github_prs.log"),
        logging.StreamHandler()
    ]
)

OWNER = "apache"
REPO = "bookkeeper"
PER_PAGE = 100
MAX_PAGES = 100  # 100x100 = 10,000 PR
OUT_CSV = "./output/csv/github_prs_raw.csv"

# Usa un token personale GitHub per autenticazione
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # Consigliato: esporta GITHUB_TOKEN nel terminale


def get_all_prs(per_page=PER_PAGE, max_pages=MAX_PAGES):
    prs = []
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
        logging.info("Uso autenticazione GitHub per aumentare il rate limit.")
    else:
        logging.warning("Nessun token GitHub trovato, il rate limit sarà basso (60 req/ora).")
    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues"
        params = {
            "state": "all",
            "per_page": per_page,
            "page": page,
            "sort": "created",
            "direction": "asc"
        }
        logging.info(f"Scarico /issues pagina {page}")
        r = requests.get(url, params=params, headers=headers)
        if r.status_code == 403:
            logging.error(f"Errore 403: {r.json().get('message')}")
            break
        if r.status_code != 200:
            logging.error(f"Errore {r.status_code}: {r.text}")
            break
        data = r.json()
        if not data:
            logging.info("Nessun dato restituito, fine delle pagine.")
            break
        # Solo PR, escludi le issue pure
        data_prs = [item for item in data if "pull_request" in item]
        prs.extend(data_prs)
        logging.info(f"Pagina {page}: aggiunte {len(data_prs)} PR, totale finora {len(prs)}")
        if len(data) < per_page:
            logging.info("Ultima pagina raggiunta.")
            break
        sleep(0.3)  # Evita di stressare le API di GitHub
    return prs


if __name__ == "__main__":
    prs = get_all_prs()
    if prs:
        df = pd.json_normalize(prs)
        df.to_csv(OUT_CSV, index=False)
        logging.info(f"Salvate {len(df)} PR in {OUT_CSV}")
    else:
        logging.warning("Nessuna PR scaricata!")

"""
Note:
- Per aumentare il limite di richieste, crea un Personal Access Token GitHub (solo permesso 'public_repo').
- Esporta la variabile: export GITHUB_TOKEN=tuo_token (meglio che scriverlo nel codice).
- Se non hai il token, lo script funziona ma molto lentamente (rate limit 60/ora).
- Il log salva tutto anche se lo script viene interrotto per superamento limiti.
"""
