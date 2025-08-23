# v2
# file: etl/9_enrich_feedback_cols.py
"""
Enrich tickets_prs_merged.csv with feedback & capacity signals derived from data.

Outputs (new columns written back to CSV):
- review_rounds        : int >= 1  (1 = no rework; >1 = at least one rework cycle)
- review_rework_flag   : bool      (True if any changes requested / extra review round)
- ci_failed_then_fix   : bool      (True if any CI/build/test failure before a later success)
- dev_user             : string    (best-effort developer identity from ETL)
- tester               : string    (best-effort CI/QA runner identity from ETL)

Heuristics (all data-driven; no manual constants):
- Review rework:
    • Prefer numeric counters like 'requested_changes_count', 'pr_review_rounds', 'reviews_count'
      → review_rounds = row-wise max(counter-derived), clipped to minimum 1
    • Else look for string/state lists (e.g., 'pull_request_review_states') containing 'CHANGES_REQUESTED'
      → review_rounds = 2 if any 'CHANGES_REQUESTED' appears, else 1
- CI fail→fix:
    • Look for history/conclusion arrays:
      ['check_runs_conclusions','combined_status_states','ci_status_history',
       'combined_statuses','workflow_conclusions','build_state_history','statuses']
      → True if a failure-like token appears before a later success-like token
    • Also merge with boolean-ish columns if they exist: ['ci_failed_then_fix','ci_failed','build_failed','qa_failed_flag']
- dev_user/tester:
    • dev_user from first present among:
      ['fields.assignee.name','fields.assignee.displayName','assignee.login','user.login',
       'author_login','pr_author_login','dev_user','developer','fields.assignee']
    • tester from first present among (CI/runner-ish):
      ['ci_runner','ci_agent','jenkins_node','build_agent','runner_name','runner_id','qa_user','testing_user']

Logging: stdout + output/logs/enrich_feedback.log
Repo: https://github.com/GVCUTV/BK_ASF.git
"""

from __future__ import print_function

import argparse
import json
import logging
import os
from os import path

import numpy as np
import pandas as pd
from path_config import PROJECT_ROOT


# ----------------------------- logging utils ----------------------------- #

def _safe_mkdirs(d):
    try:
        os.makedirs(d)
    except OSError:
        if not path.isdir(d):
            raise

def _setup_logging():
    logs_dir = path.join("output", "logs")
    _safe_mkdirs(logs_dir)
    log_path = path.join(logs_dir, "enrich_feedback.log")

    root = logging.getLogger()
    root.handlers[:] = []
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt); fh.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt); sh.setLevel(logging.INFO)
    root.addHandler(fh); root.addHandler(sh)

    logging.info("Logger ready. Logfile: %s", log_path)


# ----------------------------- helpers ----------------------------- #

FAIL_TOKENS    = {"fail", "failure", "failed", "error", "timed_out", "timeout", "cancelled", "canceled", "aborted", "broken"}
SUCCESS_TOKENS = {"success", "succeeded", "passed", "ok", "green", "completed_success"}

def _to_listish(val):
    """Turn cells like '["SUCCESS","FAILURE"]' or 'SUCCESS;FAILURE' into a list of tokens."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return []
    s = str(val).strip()
    if not s:
        return []
    # JSON-like list
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
        try:
            import ast
            obj = ast.literal_eval(s)
            if isinstance(obj, (list, tuple)):
                return [str(x).strip() for x in obj]
        except Exception:
            pass
    # CSV/semicolon/pipe/space-separated fallbacks
    for sep in [";", ",", "|", " "]:
        if sep in s:
            return [t.strip() for t in s.split(sep) if t.strip()]
    return [s]

def _has_fail_then_success(tokens):
    """True if we see any failure-like token and later a success-like token."""
    toks = [t.lower() for t in tokens]
    seen_fail = False
    for t in toks:
        if any(k in t for k in FAIL_TOKENS):
            seen_fail = True
        if seen_fail and any(k in t for k in SUCCESS_TOKENS):
            return True
    return False

def _truthy_series(s):
    return s.astype(str).str.strip().str.lower().isin({"true","1","yes","y","t"})


# ----------------------------- core enrichment ----------------------------- #

def enrich(df):
    """Return df with added columns; logs how each was computed."""
    cols = list(df.columns)
    logging.info("Input columns: %d. Sample: %s ...", len(cols), cols[:40])

    # ---------- review_rounds & review_rework_flag ----------
    rounds = None
    rework = None

    numeric_candidates = [
        "requested_changes_count", "pr_review_rounds", "reviews_count",
        "review_rounds"  # if already present, keep it in the max
    ]
    strlist_candidates = [
        "pull_request_review_states", "review_states", "pr_review_states",
        "review_decisions", "requested_changes_states"
    ]

    present_num = [c for c in numeric_candidates if c in df.columns]
    if present_num:
        # Build a numeric DataFrame and take row-wise max (keeps pandas Series -> .clip(lower=1) works)
        num_df = pd.concat([pd.to_numeric(df[c], errors="coerce") for c in present_num], axis=1)
        rounds = num_df.max(axis=1).fillna(0).astype(int)
        rounds = rounds.clip(lower=1)  # <-- pandas Series clip (fix for your error)
        rework = (rounds > 1)
        for c in present_num:
            logging.info("Considered numeric review signal: %s (non-null=%d)", c, int(pd.to_numeric(df[c], errors="coerce").notna().sum()))
        logging.info("Derived review_rounds from numeric candidates.")
    else:
        # Try string/state columns → if any 'CHANGES_REQUESTED' appears → rework True
        for c in strlist_candidates:
            if c in df.columns:
                flags = df[c].apply(_to_listish).apply(
                    lambda lst: any("changes_requested" in str(x).lower() for x in lst)
                )
                rework = flags if rework is None else (rework | flags)
                logging.info("Derived review_rework_flag from string list: %s", c)
        if rework is not None:
            rounds = (rework.astype(int) + 1)  # 2 if rework True, else 1

    if rounds is None:
        logging.warning("Could not derive review_rounds from data (no candidates found).")
    else:
        df["review_rounds"] = rounds.astype(int)

    if rework is None and "review_rounds" in df.columns:
        rework = (pd.to_numeric(df["review_rounds"], errors="coerce").fillna(1).astype(int) > 1)
    if rework is not None:
        df["review_rework_flag"] = rework.astype(bool)

    # ---------- ci_failed_then_fix ----------
    ci = None
    ci_candidates = [
        "check_runs_conclusions", "combined_status_states",  # typical from our GH fetcher
        "ci_status_history", "combined_statuses", "workflow_conclusions",
        "build_state_history", "statuses",
        "ci_conclusion", "check_suite_conclusion", "build_conclusion"
    ]
    for c in ci_candidates:
        if c in df.columns:
            series = df[c].apply(_to_listish)
            flags = series.apply(_has_fail_then_success)
            ci = flags if ci is None else (ci | flags)
            logging.info("Considered CI signal: %s", c)

    # Also accept simple boolean-ish columns if present
    bool_ci_candidates = ["ci_failed_then_fix", "ci_failed", "build_failed", "qa_failed_flag"]
    for c in bool_ci_candidates:
        if c in df.columns:
            flags = _truthy_series(df[c])
            ci = flags if ci is None else (ci | flags)
            logging.info("Considered CI boolean-ish signal: %s", c)

    if ci is not None:
        df["ci_failed_then_fix"] = ci.astype(bool)
    else:
        logging.warning("Could not derive ci_failed_then_fix from data (no CI candidates found).")

    # ---------- dev_user / tester ----------
    # Prefer real Jira/GitHub identity columns you actually have
    dev_candidates = [
        "fields.assignee.name", "fields.assignee.displayName",
        "assignee.login", "user.login",
        "author_login", "pr_author_login",
        "dev_user", "developer",
        "fields.assignee"  # raw object (rarely useful), last resort
    ]
    test_candidates = ["ci_runner", "ci_agent", "jenkins_node", "build_agent", "runner_name", "runner_id", "qa_user", "testing_user"]

    if "dev_user" not in df.columns or df["dev_user"].notna().sum() == 0:
        picked = None
        for c in dev_candidates:
            if c in df.columns and df[c].notna().sum() > 0:
                df["dev_user"] = df[c]
                picked = c
                break
        if picked:
            logging.info("dev_user sourced from: %s", picked)
        else:
            logging.warning("Could not populate dev_user (no suitable columns with values found).")

    if "tester" not in df.columns or df["tester"].notna().sum() == 0:
        picked = None
        for c in test_candidates:
            if c in df.columns and df[c].notna().sum() > 0:
                df["tester"] = df[c]
                picked = c
                break
        if picked:
            logging.info("tester sourced from: %s", picked)

    return df


# ----------------------------- CLI ----------------------------- #

def main():
    parser = argparse.ArgumentParser(description="Enrich ETL with feedback & capacity columns (data-only).")
    parser.add_argument("--in-csv",  default=PROJECT_ROOT + "/etl/output/csv/tickets_prs_merged.csv")
    parser.add_argument("--out-csv", default=PROJECT_ROOT + "/etl/output/csv/tickets_prs_merged.csv",
                        help="Where to write enriched CSV (can overwrite input).")
    args = parser.parse_args()

    _setup_logging()
    logging.info("Reading: %s", args.in_csv)
    df = pd.read_csv(args.in_csv)
    logging.info("Rows: %d | Cols: %d", len(df), len(df.columns))

    df2 = enrich(df)

    # Coverage stats
    def nn(col): return int(df2[col].notna().sum()) if col in df2.columns else 0
    cov = {
        "review_rounds_nonnull": nn("review_rounds"),
        "review_rework_flag_nonnull": nn("review_rework_flag"),
        "ci_failed_then_fix_nonnull": nn("ci_failed_then_fix"),
        "dev_user_nonnull": nn("dev_user"),
        "tester_nonnull": nn("tester"),
    }
    logging.info("Coverage: %s", json.dumps(cov))

    # Final sanity: at least one of review_* and ci_* should exist
    missing = []
    if "review_rounds" not in df2.columns and "review_rework_flag" not in df2.columns:
        missing.append("review_rounds / review_rework_flag")
    if "ci_failed_then_fix" not in df2.columns:
        missing.append("ci_failed_then_fix")
    if "dev_user" not in df2.columns:
        missing.append("dev_user")
    if "tester" not in df2.columns:
        missing.append("tester")
    if missing:
        logging.warning("Some columns could not be derived from your current data: %s", missing)
        logging.warning("Consider extending ETL to include PR review states and CI status histories.")

    logging.info("Writing: %s", args.out_csv)
    df2.to_csv(args.out_csv, index=False)
    logging.info("Done.")


if __name__ == "__main__":
    main()
