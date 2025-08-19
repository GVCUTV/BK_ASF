# v2
# file: 8_export_fit_summary.py

"""
Legge i dettagli di fit per STAGE (development, review, testing) dai file:
  - ./output/csv/distribution_fit_stats_development.csv
  - ./output/csv/distribution_fit_stats_review.csv
  - ./output/csv/distribution_fit_stats_testing.csv

Seleziona per ciascuno stage il "winner" (MAE_KDE_PDF minimo; tie-breaker AIC, poi BIC, poi KS_pvalue)
e produce il file:
  - ./output/csv/fit_summary.csv

Formato di output (colonne):
  stage, dist, s, c, loc, scale, mu, sigma, mae, ks_pvalue, aic, bic

Note:
- dist usa i nomi SciPy: lognorm, weibull_min, expon, norm
- Parametri opzionali (non pertinenti alla distribuzione vincente) restano NaN
- Log completo su stdout e ./output/logs/export_fit_summary.log
"""

import os
import logging
import pandas as pd
import numpy as np
from ast import literal_eval

# === Costanti I/O ===
CSV_DIR = "./output/csv"
LOG_DIR = "./output/logs"
OUT_SUMMARY = os.path.join(CSV_DIR, "fit_summary.csv")

STAGE_FILES = {
    "development": os.path.join(CSV_DIR, "distribution_fit_stats_development.csv"),
    "review":      os.path.join(CSV_DIR, "distribution_fit_stats_review.csv"),
    "testing":     os.path.join(CSV_DIR, "distribution_fit_stats_testing.csv"),
}

# === Setup logging ===
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(CSV_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "export_fit_summary.log")),
        logging.StreamHandler()
    ]
)

def _parse_params_cell(cell):
    """
    I CSV 'distribution_fit_stats_*.csv' salvano la colonna 'Parametri'.
    A seconda della libreria usata in scrittura, la cella può essere:
      - lista Python-like in stringa: "[1.23, 0.0, 45.6]"
      - oggetto già lista (poco probabile, ma gestito)
      - stringa "nan" o vuota
    Usiamo literal_eval in modo sicuro; in fallback, ritorniamo None.
    """
    if cell is None or (isinstance(cell, float) and np.isnan(cell)):
        return None
    if isinstance(cell, (list, tuple)):
        return list(cell)
    if isinstance(cell, str):
        s = cell.strip()
        if not s or s.lower() == "nan":
            return None
        try:
            val = literal_eval(s)
            if isinstance(val, (list, tuple)):
                return list(val)
        except Exception:
            pass
    return None

def _to_summary_row(stage: str, dist_label: str, params_list, metrics: dict) -> dict:
    """
    Converte label "umana" in naming SciPy e mappa i parametri in colonne esplicite.
    Dist label possibili (coerenti con 7_fit_distributions.py):
      - Lognormale  -> lognorm (s, loc, scale)
      - Weibull     -> weibull_min (c, loc, scale)
      - Esponenziale-> expon (loc, scale)
      - Normale     -> norm (mu, sigma)
    """
    row = {
        "stage": stage,
        "dist": np.nan,
        "s": np.nan,
        "c": np.nan,
        "loc": np.nan,
        "scale": np.nan,
        "mu": np.nan,
        "sigma": np.nan,
        "mae": metrics.get("MAE_KDE_PDF", np.nan),
        "ks_pvalue": metrics.get("KS_pvalue", np.nan),
        "aic": metrics.get("AIC", np.nan),
        "bic": metrics.get("BIC", np.nan),
    }

    if dist_label == "Lognormale":
        row["dist"] = "lognorm"
        if params_list and len(params_list) >= 3:
            row["s"], row["loc"], row["scale"] = float(params_list[0]), float(params_list[1]), float(params_list[2])
            # Parametri comodi
            if row["scale"] and row["scale"] > 0:
                row["mu"] = float(np.log(row["scale"]))
            row["sigma"] = row["s"]

    elif dist_label == "Weibull":
        row["dist"] = "weibull_min"
        if params_list and len(params_list) >= 3:
            row["c"], row["loc"], row["scale"] = float(params_list[0]), float(params_list[1]), float(params_list[2])

    elif dist_label == "Esponenziale":
        row["dist"] = "expon"
        if params_list and len(params_list) >= 2:
            row["loc"], row["scale"] = float(params_list[0]), float(params_list[1])

    elif dist_label == "Normale":
        row["dist"] = "norm"
        if params_list and len(params_list) >= 2:
            row["mu"], row["sigma"] = float(params_list[0]), float(params_list[1])

    else:
        # Etichetta inattesa: esporto "as-is"
        row["dist"] = dist_label

    return row

def _choose_winner(df: pd.DataFrame) -> pd.Series | None:
    """
    Seleziona la riga vincente:
      1) min MAE_KDE_PDF
      2) tie-break: min AIC
      3) tie-break: min BIC
      4) tie-break: max KS_pvalue
    Restituisce una pd.Series (riga) o None se df è vuoto.
    """
    if df is None or df.empty:
        return None

    # pulizia numerica
    for c in ["MAE_KDE_PDF", "AIC", "BIC", "KS_pvalue"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # ordina
    df_ord = df.sort_values(
        by=["MAE_KDE_PDF", "AIC", "BIC", "KS_pvalue"],
        ascending=[True, True, True, False],
        na_position="last"
    )
    return df_ord.iloc[0]

def main():
    logging.info("=== INIZIO EXPORT FIT SUMMARY (per-stage) ===")

    summary_rows = []

    for stage, path in STAGE_FILES.items():
        if not os.path.exists(path):
            logging.warning("File per stage '%s' NON trovato: %s (salto)", stage, path)
            continue

        try:
            df = pd.read_csv(path, low_memory=False)
            logging.info("Caricato %s (%d righe)", path, len(df))
        except Exception as e:
            logging.error("Errore leggendo %s: %s", path, e)
            continue

        # Verifica colonne minime
        required = {"Distribuzione", "Parametri", "MAE_KDE_PDF"}
        if not required.issubset(df.columns):
            logging.error("Colonne richieste mancanti in %s. Trovate: %s", path, list(df.columns))
            continue

        # Scegli winner
        winner = _choose_winner(df)
        if winner is None or pd.isna(winner.get("Distribuzione", np.nan)):
            logging.warning("Nessun winner selezionabile per stage '%s' (file: %s).", stage, path)
            continue

        # Parse param list
        params_raw = winner.get("Parametri")
        params_list = _parse_params_cell(params_raw)

        # Costruisci riga di output
        metrics = {
            "MAE_KDE_PDF": winner.get("MAE_KDE_PDF"),
            "KS_pvalue": winner.get("KS_pvalue"),
            "AIC": winner.get("AIC"),
            "BIC": winner.get("BIC"),
        }
        row = _to_summary_row(stage, str(winner["Distribuzione"]), params_list, metrics)
        summary_rows.append(row)

        logging.info(
            "WINNER [%s]: %s | params=%s | MAE=%.6f | KS_p=%.4g | AIC=%s | BIC=%s",
            stage,
            winner["Distribuzione"],
            params_list,
            float(metrics["MAE_KDE_PDF"]) if metrics["MAE_KDE_PDF"] is not None and not pd.isna(metrics["MAE_KDE_PDF"]) else float("nan"),
            float(metrics["KS_pvalue"]) if metrics["KS_pvalue"] is not None and not pd.isna(metrics["KS_pvalue"]) else float("nan"),
            str(metrics["AIC"]),
            str(metrics["BIC"]),
        )

    if not summary_rows:
        logging.error("Nessuna riga di summary generata: controlla i file di input per-stage.")
        raise SystemExit(2)

    # Scrivi fit_summary.csv
    out_df = pd.DataFrame(summary_rows, columns=[
        "stage", "dist", "s", "c", "loc", "scale", "mu", "sigma", "mae", "ks_pvalue", "aic", "bic"
    ])
    out_df.to_csv(OUT_SUMMARY, index=False)
    logging.info("Salvato fit_summary in %s", OUT_SUMMARY)
    print(out_df.to_string(index=False))

    logging.info("=== EXPORT FIT SUMMARY COMPLETATO ===")

if __name__ == "__main__":
    main()
