# v1

# file: USAGE_GUIDE.md

# BookKeeper Workflow Simulation – Environment Setup & ETL Instructions

This guide covers how to set up your Python environment for running the simulation, and provides ETL (Extract, Transform, Load) scripts to generate the input data/distribution parameters for the simulation from Jira/GitHub exports.

---

## 1. Environment Setup

### A. Install Python

* Make sure you have **Python 3.7+** installed:

  ```bash
  python --version
  ```

  If not, download from [https://www.python.org/downloads/](https://www.python.org/downloads/)

### B. Install Dependencies

* Install the required Python packages:

  ```bash
  pip install numpy pandas matplotlib scipy
  ```

* (Optional, for further development:)

  ```bash
  pip install jupyter requests
  ```

---

## 2. Directory Structure

Place all simulation files in a folder, e.g. `simulation/`. Create the following structure:

```
BK_ASF/
├── simulation/
│   ├── simulate.py
│   ├── events.py
│   ├── entities.py
│   ├── service_distributions.py
│   ├── config.py
│   ├── stats.py
│   ├── README.md
│   ├── logs/
│   ├── output/
│   └── ...
└── SETUP_AND_ETL_GUIDE.md
```

---

## 3. ETL (Extract, Transform, Load) Scripts

### A. Extract: Download Data

* Export raw data from Jira and GitHub as CSVs (e.g. issues, PRs, status changes)

  * Save as `raw_jira.csv`, `raw_github.csv` in `simulation/input/`

### B. Transform: Clean and Merge Data

* Use the script below to:

  1. Load CSVs
  2. Clean irrelevant/non-issue records
  3. Merge on common fields (e.g. issue key, PR link)
  4. Compute per-ticket lifetimes, #feedback cycles, etc.

```python
# v1
# file: simulation/etl_build_dataset.py

"""
ETL: Cleans and merges Jira/GitHub data, computes ticket lifecycles, feedback cycles, and service times.
Output: cleaned dataset for distribution fitting and simulation parameterization.
"""
import pandas as pd
import numpy as np
import os
import logging

os.makedirs("simulation/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("simulation/logs/etl.log", mode='w'),
        logging.StreamHandler()
    ]
)

def clean_jira(jira_path):
    df = pd.read_csv(jira_path)
    # Drop rows not representing tickets of interest
    df = df[df['fields.issuetype.name'].isin(['Bug', 'New Feature', 'Improvement'])]
    df = df[~df['fields.status.name'].isin(['Infra', 'Duplicate', "Won't Fix"])]
    return df

def clean_github(github_path):
    df = pd.read_csv(github_path)
    # Example: Filter only PRs linked to Jira issues
    df = df[df['pr_linked_to_jira'].notna()]
    return df

def merge_jira_github(jira_df, github_df):
    merged = pd.merge(jira_df, github_df, left_on='key', right_on='pr_linked_to_jira', how='left')
    return merged

def compute_lifetimes(df):
    # Compute resolution times, feedback cycles, etc.
    df['created'] = pd.to_datetime(df['fields.created'])
    df['resolved'] = pd.to_datetime(df['fields.resolutiondate'])
    df['resolution_time'] = (df['resolved'] - df['created']).dt.total_seconds() / 3600.0
    df['feedback_cycles'] = df['fields.customfield_feedback_count'].fillna(0).astype(int)
    return df

if __name__ == "__main__":
    jira_path = "simulation/input/raw_jira.csv"
    github_path = "simulation/input/raw_github.csv"
    os.makedirs("simulation/input", exist_ok=True)
    
    jira_df = clean_jira(jira_path)
    logging.info(f"Loaded and cleaned Jira: {len(jira_df)} tickets.")
    github_df = clean_github(github_path)
    logging.info(f"Loaded and cleaned GitHub: {len(github_df)} PRs.")
    merged_df = merge_jira_github(jira_df, github_df)
    logging.info(f"Merged dataset: {len(merged_df)} rows.")
    full_df = compute_lifetimes(merged_df)
    full_df.to_csv("simulation/output/tickets_prs_merged.csv", index=False)
    logging.info("Saved cleaned/merged dataset for fitting and simulation input.")
```

* Edit field names as needed to match your real exports.
* Output is `simulation/output/tickets_prs_merged.csv`

### C. Load: Fitting Distributions for Simulation

* Use this output to fit service time distributions (see your existing fitting scripts, e.g., `7_fit_distributions.py`).
* Place chosen distribution types and fitted parameters in `config.py` under `SERVICE_TIME_PARAMS`.

---

## 4. Running the Simulation

1. Configure your simulation parameters in `config.py` (arrival rate, feedback probabilities, etc.).
2. Make sure your fitted parameters from ETL/fitting are filled in.
3. Run:

   ```bash
   python simulation/simulate.py
   ```
4. Check logs in `simulation/logs/`, and output stats in `simulation/output/`.

---

## 5. Troubleshooting & Notes

* Always check `simulation/logs/etl.log` and `simulation/logs/simulation.log` for errors or process info.
* Edit column names as needed to match your exported Jira/GitHub fields.
* The provided ETL script is modular—extend it for extra cleaning/merging as needed.
* For advanced ETL (API extraction, advanced feedback cycles, etc.), build from this template.

---

*Contact the project maintainers for additional help, or to suggest improvements to this guide.*
