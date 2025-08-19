# v4
# file: etl/2_download_github_prs.py
"""
Downloader PR GitHub per apache/bookkeeper con estrazione estesa:
- Lista PR (state=all), paginata, con appiattimento json (sep='.')
- Per ogni PR:
    * recensioni (reviews) -> stati e conteggio CHANGES_REQUESTED
    * check-runs del commit HEAD -> conclusioni lista
    * combined status del commit HEAD -> stati lista
- CSV finale pronto per arricchimenti e join con Jira.

Tutto è loggato su stdout e output/logs/download_github_prs.log.

Repo: https://github.com/GVCUTV/BK_ASF.git
"""

from __future__ import print_function

import os
import time
import json
import logging
import requests
import pandas as pd
from os import path

from path_config import PROJECT_ROOT  # CWD-indipendente (come richiesto)

LOG_DIR = path.join(PROJECT_ROOT, "output", "logs")
OUT_CSV = path.join(PROJECT_ROOT, "etl", "output", "csv", "github_prs_raw.csv")

OWNER = "apache"
REPO  = "bookkeeper"
PER_PAGE = 100
MAX_PAGES = 200

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

def _safe_mkdirs(d):
    try:
        os.makedirs(d)
    except OSError:
        if not path.isdir(d):
            raise

def _setup_logging():
    _safe_mkdirs(LOG_DIR)
    log_path = path.join(LOG_DIR, "download_github_prs.log")

    root = logging.getLogger()
    root.handlers[:] = []
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)

    logging.info("Logger pronto. Logfile: %s", log_path)
    return log_path

def _headers(extra=None):
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "BK_ASF-ETL",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = "Bearer " + GITHUB_TOKEN
    if extra:
        h.update(extra)
    return h

def _gh_get(url, params=None, retries=3, preview=False):
    """GET GitHub con retry e rispetto rate limit."""
    hdr = _headers(extra={"Accept": "application/vnd.github.antiope-preview+json"} if preview else None)
    for i in range(retries + 1):
        r = requests.get(url, headers=hdr, params=params, timeout=30)
        if r.status_code == 200:
            # rate diagnostics
            remaining = r.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                logging.debug("Rate remaining: %s for %s", remaining, url)
            return r.json()
        if r.status_code in (429, 502, 503, 504):
            time.sleep(2 * (i + 1))
            continue
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = r.headers.get("X-RateLimit-Reset")
            logging.warning("Rate limited. Reset at %s. Sleeping 60s.", reset)
            time.sleep(60)
            continue
        logging.warning("GitHub GET %s -> %s | %s", url, r.status_code, r.text[:200])
        time.sleep(2 * (i + 1))
    raise RuntimeError("GitHub GET failed after retries: %s" % url)

def _list_all_prs(owner, repo, per_page=PER_PAGE, max_pages=MAX_PAGES):
    prs = []
    for page in range(1, max_pages + 1):
        url = "https://api.github.com/repos/{}/{}/pulls".format(owner, repo)
        params = {"state": "all", "per_page": per_page, "page": page}
        logging.info("PR page %d", page)
        data = _gh_get(url, params=params)
        if not isinstance(data, list) or not data:
            break
        prs.extend(data)
        if len(data) < per_page:
            break
    logging.info("Totale PR scaricate: %d", len(prs))
    return prs

def _list_reviews(owner, repo, pr_number):
    url = "https://api.github.com/repos/{}/{}/pulls/{}/reviews".format(owner, repo, pr_number)
    data = _gh_get(url, preview=False)
    # ritorna lista di dict, con chiavi come 'state' ('APPROVED','CHANGES_REQUESTED','COMMENTED',...)
    return data if isinstance(data, list) else []

def _list_check_runs(owner, repo, sha):
    # Check Runs API (needs preview accept header, handled in _gh_get with preview=True)
    url = "https://api.github.com/repos/{}/{}/commits/{}/check-runs".format(owner, repo, sha)
    data = _gh_get(url, preview=True)
    runs = data.get("check_runs", []) if isinstance(data, dict) else []
    return runs

def _combined_status(owner, repo, sha):
    url = "https://api.github.com/repos/{}/{}/commits/{}/status".format(owner, repo, sha)
    data = _gh_get(url, preview=False)
    statuses = data.get("statuses", []) if isinstance(data, dict) else []
    return statuses

def _derive_review_signals(reviews):
    states = [str(x.get("state","")).upper() for x in reviews]
    requested_changes = sum(1 for s in states if s == "CHANGES_REQUESTED")
    return {
        "reviews_count": len(reviews),
        "requested_changes_count": requested_changes,
        "pull_request_review_states": json.dumps(states),
    }

def _derive_checks(runs):
    conclusions = [str(x.get("conclusion") or "").lower() for x in runs if x]
    # 'conclusion' often in {'success','failure','neutral','cancelled','timed_out','action_required',...}
    return {
        "check_runs_conclusions": json.dumps(conclusions)
    }

def _derive_statuses(statuses):
    states = [str(x.get("state") or "").lower() for x in statuses if x]
    return {
        "combined_status_states": json.dumps(states)
    }

# --------------------------- Main --------------------------- #

def main():
    _setup_logging()
    logging.info("PROJECT_ROOT: %s", PROJECT_ROOT)
    logging.info("OUT_CSV     : %s", OUT_CSV)
    if not GITHUB_TOKEN:
        logging.warning("GITHUB_TOKEN non impostato: rate limit 60/h. Consigliato esportare GITHUB_TOKEN.")

    # 1) Elenco PR (metadata base)
    prs = _list_all_prs(OWNER, REPO)
    if not prs:
        logging.warning("Nessuna PR trovata.")
        _safe_mkdirs(path.dirname(OUT_CSV))
        pd.DataFrame([]).to_csv(OUT_CSV, index=False)
        return

    rows = []
    for pr in prs:
        number = pr.get("number")
        head = pr.get("head") or {}
        head_sha = head.get("sha")

        # 2) Reviews
        reviews = _list_reviews(OWNER, REPO, number)
        rev_sig = _derive_review_signals(reviews)

        # 3) Checks API (per head_sha)
        chk_sig = {"check_runs_conclusions": json.dumps([])}
        if head_sha:
            runs = _list_check_runs(OWNER, REPO, head_sha)
            chk_sig = _derive_checks(runs)

        # 4) Combined status API
        st_sig = {"combined_status_states": json.dumps([])}
        if head_sha:
            statuses = _combined_status(OWNER, REPO, head_sha)
            st_sig = _derive_statuses(statuses)

        # 5) Record base fields + signals
        base = {
            "number": number,
            "html_url": pr.get("html_url"),
            "state": pr.get("state"),
            "title": pr.get("title"),
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "closed_at": pr.get("closed_at"),
            "merged_at": pr.get("merged_at"),
            "merge_commit_sha": pr.get("merge_commit_sha"),
            "user.login": (pr.get("user") or {}).get("login"),
            "assignee.login": (pr.get("assignee") or {}).get("login"),
            "requested_reviewers": json.dumps([(u or {}).get("login") for u in (pr.get("requested_reviewers") or [])]),
            "head.ref": head.get("ref"),
            "head.sha": head_sha,
            "base.ref": (pr.get("base") or {}).get("ref"),
        }
        base.update(rev_sig)
        base.update(chk_sig)
        base.update(st_sig)
        rows.append(base)

        logging.info("PR #%s | reviews=%d changes_requested=%d head_sha=%s",
                     number, rev_sig["reviews_count"], rev_sig["requested_changes_count"], head_sha)

    # 6) DataFrame e salvataggio
    df = pd.DataFrame(rows)
    _safe_mkdirs(path.dirname(OUT_CSV))
    df.to_csv(OUT_CSV, index=False)
    logging.info("Salvate %d PR in %s", len(df), OUT_CSV)

    # 7) Statistiche rapide per debug
    for c in ["reviews_count", "requested_changes_count"]:
        if c in df.columns:
            logging.info("Stats %s: non-null=%d, mean=%.4f, max=%s",
                         c, int(df[c].notna().sum()),
                         float(pd.to_numeric(df[c], errors='coerce').mean()),
                         str(pd.to_numeric(df[c], errors='coerce').max()))
    logging.info("Esempio check_runs_conclusions: %s", df["check_runs_conclusions"].iloc[0] if "check_runs_conclusions" in df.columns and len(df)>0 else "n/a")
    logging.info("Esempio combined_status_states: %s", df["combined_status_states"].iloc[0] if "combined_status_states" in df.columns and len(df)>0 else "n/a")


if __name__ == "__main__":
    main()
