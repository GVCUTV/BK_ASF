# v6
# file: etl/2_download_github_prs.py
"""
GitHub PR downloader for apache/bookkeeper with:
- Concurrent page fetching for the PR list (state=all).
- **Concurrent per-PR detail fetching** (reviews, check-runs, combined statuses).
- Shared HTTP session with pooled connections for lower latency.
- Robust extraction of review signals, check-runs conclusions, and combined statuses.
- Token read from etl/env/github.env as: GITHUB_TOKEN=<token_value>.
- Exhaustive logging to stdout and output/logs/download_github_prs.log.

Design notes:
- We use a small thread pool (default 10 workers) to fetch the PR list in parallel.
- We use a separate, tunable pool (default 16 workers) to fetch PR details in parallel.
- We detect the last page using the HTTP 'Link' header to avoid overfetch.
- All API reads handle transient errors with simple retries and log details.
- Checks/Statuses responses are normalized to lists before iteration to avoid type errors.

Repo: https://github.com/GVCUTV/BK_ASF.git
"""

from __future__ import print_function

import os
import re
import time
import json
import logging
import requests
import pandas as pd
from os import path
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter

from path_config import PROJECT_ROOT  # CWD-independent

# --------------------------- Constants & Paths --------------------------- #

LOG_DIR = path.join(PROJECT_ROOT, "output", "logs")
OUT_CSV = path.join(PROJECT_ROOT, "etl", "output", "csv", "github_prs_raw.csv")
ENV_FILE = path.join(PROJECT_ROOT, "etl", "env", "github.env")

OWNER = "apache"
REPO = "bookkeeper"
PER_PAGE = 100
MAX_WORKERS = int(os.getenv("GITHUB_LIST_WORKERS", "10"))  # PR list pagination workers
DETAIL_WORKERS = int(os.getenv("GITHUB_DETAIL_WORKERS", "16"))  # per-PR details workers
RETRIES = 3
TIMEOUT = 30

# Connection pool sizes for the shared Session; keep a bit larger than workers
POOL_CONNECTIONS = int(os.getenv("GITHUB_POOL_CONNS", str(max(32, DETAIL_WORKERS * 2))))
POOL_MAXSIZE = int(os.getenv("GITHUB_POOL_MAXSIZE", str(max(64, DETAIL_WORKERS * 4))))

# --------------------------- Logging --------------------------- #

def _safe_mkdirs(d):
    try:
        os.makedirs(d, exist_ok=True)
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
    fh.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)

    logging.info("Logger ready. Logfile: %s", log_path)
    return log_path


# --------------------------- Token, Session & Headers --------------------------- #

def _read_token_from_envfile(p=ENV_FILE):
    """Read 'GITHUB_TOKEN=<token>' from file; return empty string if missing."""
    try:
        with open(p, "r") as f:
            txt = f.read().strip()
        if not txt:
            logging.warning("Token file is empty: %s", p)
            return ""
        # Find GITHUB_TOKEN=... pattern
        m = re.search(r"GITHUB_TOKEN\s*=\s*['\"]?([^'\"\n\r]+)", txt)
        token = m.group(1).strip() if m else txt.split("=", 1)[-1].strip()
        return token
    except IOError:
        logging.warning("Token file not found: %s (falling back to no token)", p)
        return ""

GITHUB_TOKEN = _read_token_from_envfile()

def _headers(preview=False):
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "BK_ASF-ETL",
        "Connection": "keep-alive",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = "Bearer " + GITHUB_TOKEN
    if preview:
        # Antiope preview for check-runs (still commonly used)
        h["Accept"] = "application/vnd.github.antiope-preview+json"
    return h

# Shared HTTP session with a tuned connection pool to reuse TCP/TLS connections
_SESSION = requests.Session()
_ADAPTER = HTTPAdapter(pool_connections=POOL_CONNECTIONS, pool_maxsize=POOL_MAXSIZE, max_retries=0)
_SESSION.mount("https://", _ADAPTER)
_SESSION.mount("http://", _ADAPTER)


# --------------------------- HTTP helpers --------------------------- #

def _req_get(url, params=None, preview=False, return_response=False):
    """
    GET with simple retries using the shared Session. Returns r.json() or the raw response
    if return_response=True. Retries on common transient errors with backoff.
    """
    for attempt in range(RETRIES + 1):
        try:
            r = _SESSION.get(url, headers=_headers(preview=preview), params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r if return_response else r.json()
            # Rate limit handling
            if r.status_code == 403 and "rate limit" in r.text.lower():
                reset = r.headers.get("X-RateLimit-Reset")
                logging.warning("Rate limited (403). Reset at %s. Sleeping 60s.", reset)
                time.sleep(60)
                continue
            # Transient server/network errors
            if r.status_code in (429, 502, 503, 504):
                backoff = 2 * (attempt + 1)
                logging.warning("Transient error %s on %s (attempt %d). Sleeping %ss.",
                                r.status_code, url, attempt + 1, backoff)
                time.sleep(backoff)
                continue
            # Other errors -> log and retry a bit
            logging.warning("GET %s -> %s | %s", url, r.status_code, r.text[:200])
            time.sleep(2 * (attempt + 1))
        except requests.RequestException as e:
            logging.warning("Exception GET %s: %s (attempt %d)", url, e, attempt + 1)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("GET failed after retries: %s" % url)


# --------------------------- Pagination helpers --------------------------- #

def _discover_last_page(owner, repo, per_page=PER_PAGE):
    """
    Discover total pages using the 'Link' header.
    If absent, fall back to 1 page (or keep fetching until empty in the concurrent loop).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    params = {"state": "all", "per_page": per_page, "page": 1}
    r = _req_get(url, params=params, return_response=True)
    link = r.headers.get("Link", "")
    if link:
        # Look for rel="last"
        m = re.search(r'[?&]page=(\d+)[^>]*>; rel="last"', link)
        if m:
            last = int(m.group(1))
            logging.info("Discovered last page via Link header: %d", last)
            return last
    # If 'Link' not present, infer from body size
    data = r.json()
    n = len(data) if isinstance(data, list) else 0
    last = 1 if n < per_page else 2  # conservative guess; the concurrent loop stops on empty pages
    logging.info("No Link header. First page size=%d -> tentative last=%d", n, last)
    return last

def _fetch_pr_page(owner, repo, page, per_page=PER_PAGE):
    """Fetch a single page of PRs; returns (page, list)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    params = {"state": "all", "per_page": per_page, "page": page}
    data = _req_get(url, params=params)
    if isinstance(data, list):
        return page, data
    logging.warning("Unexpected PR page payload (not list) at page=%d", page)
    return page, []

def _list_all_prs_concurrent(owner, repo, per_page=PER_PAGE, max_workers=MAX_WORKERS):
    """
    Fetch all PR pages concurrently.
    - Use Link header to know last page.
    - Submit all pages, gather results, stop if trailing pages are empty.
    """
    last_page = _discover_last_page(owner, repo, per_page)
    pages = list(range(1, last_page + 1))
    logging.info("Fetching %d pages concurrently with %d workers…", len(pages), max_workers)

    prs_by_page = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_pr_page, owner, repo, p, per_page): p for p in pages}
        for fut in as_completed(futures):
            page, data = fut.result()
            prs_by_page[page] = data
            logging.info("Page %d fetched: %d PRs", page, len(data))

    # If we guessed last_page and there are trailing empties, trim them
    all_pages = sorted(prs_by_page.keys())
    while all_pages and len(prs_by_page[all_pages[-1]]) == 0:
        logging.info("Trimming empty trailing page %d", all_pages[-1])
        all_pages.pop()

    # Flatten in page order
    flattened = []
    for p in all_pages:
        flattened.extend(prs_by_page[p])

    logging.info("Total PRs fetched: %d", len(flattened))
    return flattened


# --------------------------- Detail helpers --------------------------- #

def _list_reviews(owner, repo, pr_number):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    data = _req_get(url, preview=False)
    if isinstance(data, list):
        return data
    logging.warning("Unexpected reviews payload for PR#%s (type=%s)", pr_number, type(data).__name__)
    return []

def _list_check_runs(owner, repo, sha):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs"
    data = _req_get(url, preview=True)
    if isinstance(data, dict):
        runs = data.get("check_runs") or []
        if isinstance(runs, list):
            return runs
    elif isinstance(data, list):
        # Rarely some proxies return a list directly
        return data
    elif isinstance(data, (str, bytes)):
        logging.warning("Checks payload is a %s string for sha=%s; skipping.", type(data).__name__, sha)
    else:
        logging.warning("Unexpected checks payload type=%s for sha=%s", type(data).__name__, sha)
    return []

def _combined_status(owner, repo, sha):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/status"
    data = _req_get(url, preview=False)
    if isinstance(data, dict):
        statuses = data.get("statuses") or []
        if isinstance(statuses, list):
            return statuses
    elif isinstance(data, list):
        return data
    elif isinstance(data, (str, bytes)):
        logging.warning("Status payload is a %s string for sha=%s; skipping.", type(data).__name__, sha)
    else:
        logging.warning("Unexpected status payload type=%s for sha=%s", type(data).__name__, sha)
    return []


def _derive_review_signals(reviews):
    states = []
    try:
        for x in reviews:
            if isinstance(x, dict):
                states.append(str(x.get("state", "")).upper())
    except Exception as e:
        logging.warning("Review states parse error: %s", e)
    requested_changes = sum(1 for s in states if s == "CHANGES_REQUESTED")
    return {
        "reviews_count": len(reviews) if isinstance(reviews, list) else 0,
        "requested_changes_count": requested_changes,
        "pull_request_review_states": json.dumps(states),
    }

def _derive_checks(runs):
    conclusions = []
    try:
        for x in runs if isinstance(runs, list) else []:
            if isinstance(x, dict):
                conclusions.append(str(x.get("conclusion") or "").lower())
    except Exception as e:
        logging.warning("Checks parse error: %s", e)
    return {"check_runs_conclusions": json.dumps(conclusions)}

def _derive_statuses(statuses):
    states = []
    try:
        for x in statuses if isinstance(statuses, list) else []:
            if isinstance(x, dict):
                states.append(str(x.get("state") or "").lower())
    except Exception as e:
        logging.warning("Statuses parse error: %s", e)
    return {"combined_status_states": json.dumps(states)}


# --------------------------- Per-PR processing (parallelizable) --------------------------- #

def _process_one_pr(pr):
    """
    Fetch and derive details for a single PR item.
    This function is designed to run in a worker thread (I/O bound).
    """
    t0 = time.time()
    number = pr.get("number")
    head = pr.get("head") or {}
    head_sha = head.get("sha")

    # Fetch reviews
    reviews = _list_reviews(OWNER, REPO, number)
    rev_sig = _derive_review_signals(reviews)

    # Fetch checks (if we have a head sha)
    chk_sig = {"check_runs_conclusions": json.dumps([])}
    if head_sha:
        runs = _list_check_runs(OWNER, REPO, head_sha)
        chk_sig = _derive_checks(runs)

    # Fetch combined statuses (if we have a head sha)
    st_sig = {"combined_status_states": json.dumps([])}
    if head_sha:
        statuses = _combined_status(OWNER, REPO, head_sha)
        st_sig = _derive_statuses(statuses)

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

    # Log one line per processed PR with timing (as requested)
    dt = time.time() - t0
    logging.info(
        "Processed PR #%s in %.2fs | reviews=%s, changes_requested=%s, head_sha=%s",
        str(number),
        dt,
        str(base.get("reviews_count")),
        str(base.get("requested_changes_count")),
        head_sha if head_sha else "-"
    )
    return base


# --------------------------- Main --------------------------- #

def main():
    _setup_logging()
    logging.info("PROJECT_ROOT: %s", PROJECT_ROOT)
    logging.info("OUT_CSV     : %s", OUT_CSV)
    logging.info("Workers     : list=%d, details=%d, pool_conns=%d, pool_max=%d",
                 MAX_WORKERS, DETAIL_WORKERS, POOL_CONNECTIONS, POOL_MAXSIZE)

    if not GITHUB_TOKEN:
        logging.warning("GITHUB_TOKEN not found in %s. You will be limited by GitHub's anonymous rate limit.", ENV_FILE)

    # 1) Fetch PR list (concurrent across pages)
    prs = _list_all_prs_concurrent(OWNER, REPO, per_page=PER_PAGE, max_workers=MAX_WORKERS)
    if not prs:
        logging.warning("No PRs found.")
        _safe_mkdirs(path.dirname(OUT_CSV))
        pd.DataFrame([]).to_csv(OUT_CSV, index=False)
        return

    # 2) For each PR, fetch details
    #    PREVIOUSLY: this was a sequential for-loop, causing 2–3 HTTP calls per PR in series.
    #    NOW: we parallelize per-PR detail fetching with a ThreadPoolExecutor.
    #    This is safe and effective because the operations are network I/O bound.
    rows = []
    t_loop0 = time.time()
    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as ex:
        futures = [ex.submit(_process_one_pr, pr) for pr in prs]
        processed = 0
        for fut in as_completed(futures):
            try:
                rows.append(fut.result())
                processed += 1
                if processed % 100 == 0:
                    elapsed = time.time() - t_loop0
                    logging.info("Parallel details progress: %d/%d (%.1f%%) in %.1fs",
                                 processed, len(prs), 100.0 * processed / max(1, len(prs)), elapsed)
            except Exception as e:
                logging.warning("Error processing PR item in worker: %s", e)

    # 3) Save CSV
    df = pd.DataFrame(rows)
    _safe_mkdirs(path.dirname(OUT_CSV))
    df.to_csv(OUT_CSV, index=False)
    logging.info("Saved %d PRs in %s", len(df), OUT_CSV)

    # 4) Quick stats
    for c in ["reviews_count", "requested_changes_count"]:
        if c in df.columns:
            logging.info("Stats %s: non-null=%d mean=%.4f max=%s",
                         c, int(df[c].notna().sum()),
                         float(pd.to_numeric(df[c], errors='coerce').mean()),
                         str(pd.to_numeric(df[c], errors='coerce').max()))
    if "check_runs_conclusions" in df.columns and len(df) > 0:
        logging.info("Sample check_runs_conclusions: %s", df["check_runs_conclusions"].iloc[0])
    if "combined_status_states" in df.columns and len(df) > 0:
        logging.info("Sample combined_status_states: %s", df["combined_status_states"].iloc[0])


if __name__ == "__main__":
    main()
