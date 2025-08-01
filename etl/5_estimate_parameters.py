# v4
# file: estimate_parameters.py

"""
Extracts queueing model parameters and key workflow metrics from tickets_prs_merged.csv,
logs all operations, and outputs results/plots for PMCSN BookKeeper project.
"""

import pandas as pd
import numpy as np
import logging
import os
from scipy.stats import lognorm, kstest
import matplotlib.pyplot as plt


def setup_logging():
    """
    Configures logging to file and stdout.
    """
    os.makedirs('./output/logs', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("./output/logs/estimate_parameters.log"),
            logging.StreamHandler()
        ]
    )


def parse_date_column(df, colname):
    """
    Converts the specified column to datetime, if it exists in the dataframe.
    """
    if colname in df.columns:
        df[colname] = pd.to_datetime(df[colname], errors='coerce')
        logging.info(f"Parsed dates in column '{colname}'.")


def compute_phase_duration(df, start, end, name):
    """
    Computes duration in hours between two date columns and adds it to the dataframe.
    Returns the name of the new duration column.
    """
    if start in df.columns and end in df.columns:
        duration_col = f'{name}_duration_hours'
        df[duration_col] = (df[end] - df[start]).dt.total_seconds() / 3600
        logging.info(f"Computed '{duration_col}' for {name} phase.")
        return duration_col
    else:
        logging.warning(f"Cannot compute {name} duration: missing columns '{start}' or '{end}'.")
        return None


def fit_and_plot(times, phase_name):
    """
    Fits a lognormal distribution to the given durations, saves a plot, and logs fit results.
    Returns fit parameters and p-value for goodness of fit.
    """
    times = times.dropna()
    if len(times) < 5:
        logging.warning(f"Too few samples for {phase_name} (n={len(times)}). Skipping fit.")
        return None, None, None, None
    shape, loc, scale = lognorm.fit(times, floc=0)
    logging.info(f"{phase_name}: lognormal fit (shape={shape:.3f}, loc={loc:.3f}, scale={scale:.3f})")
    ks_stat, ks_pval = kstest(times, 'lognorm', args=(shape, loc, scale))
    logging.info(f"{phase_name}: K-S test stat={ks_stat:.3f}, p={ks_pval:.3f}")
    # Plot
    plt.figure()
    plt.hist(times, bins=30, density=True, alpha=0.5, label="Empirical")
    x = np.linspace(times.min(), times.max(), 100)
    plt.plot(x, lognorm.pdf(x, shape, loc, scale), label="Lognormal fit")
    plt.title(f"{phase_name}: Fitted Lognormal")
    plt.xlabel('Duration (hours)')
    plt.ylabel('Density')
    plt.legend()
    os.makedirs('./output/png', exist_ok=True)
    plt.savefig(f'./output/png/{phase_name}_lognormal_fit.png')
    plt.close()
    logging.info(f"{phase_name} lognormal fit plot saved.")
    return shape, loc, scale, ks_pval


def feedback_probability(df, column, label):
    """
    Calculates the probability that the specified feedback column is > 0.
    """
    if column in df.columns:
        prob = (df[column].fillna(0) > 0).mean()
        logging.info(f"{label} feedback probability: {prob:.3f}")
        return prob
    else:
        logging.warning(f"Missing column '{column}' for feedback calculation.")
        return np.nan


def main():
    setup_logging()
    logging.info("=== PMCSN BookKeeper Parameter Estimation Started ===")
    # --- Load dataset ---
    IN_CSV = "./output/csv/tickets_prs_merged.csv"
    try:
        df = pd.read_csv(IN_CSV)
        logging.info(f"Loaded dataset: {IN_CSV} ({len(df)} rows)")
    except Exception as e:
        logging.error(f"Failed to load input CSV: {e}")
        return

    # --- Convert date columns ---
    date_cols = ['created', 'closed', 'dev_review_start', 'dev_review_end', 'test_start', 'test_end']
    for col in date_cols:
        parse_date_column(df, col)

    # --- Estimate Arrival Rate ---
    if 'created' in df.columns:
        df = df.sort_values('created')
        df['inter_arrival'] = df['created'].diff().dt.total_seconds() / 3600  # hours
        mean_interarrival = df['inter_arrival'].mean()
        arrival_rate = 1 / mean_interarrival if mean_interarrival > 0 else float('nan')
        logging.info(f"Estimated arrival rate (tickets/hour): {arrival_rate:.5f}")
    else:
        logging.warning("'created' column missing. Cannot estimate arrival rate.")
        arrival_rate = np.nan

    # --- Phase Duration Extraction ---
    devrev_col = compute_phase_duration(df, 'dev_review_start', 'dev_review_end', 'dev_review')
    test_col = compute_phase_duration(df, 'test_start', 'test_end', 'test')

    # --- Distribution Fitting for Each Phase ---
    phase_results = {}
    for col, label in [(devrev_col, 'DevReview'), (test_col, 'TestQA')]:
        if col:
            m = df[col].mean()
            md = df[col].median()
            shape, loc, scale, pval = fit_and_plot(df[col], label)
            phase_results[label] = {
                "mean": m, "median": md, "lognorm_shape": shape, "lognorm_loc": loc, "lognorm_scale": scale,
                "ks_pval": pval
            }

    # --- Feedback/Loop Probabilities ---
    p_review = feedback_probability(df, 'review_feedback_count', 'Review')
    p_test = feedback_probability(df, 'test_feedback_count', 'Test')

    # --- Reopen Rate ---
    reopen_rate = feedback_probability(df, 'reopened_count', 'Reopen')

    # --- Key Metrics: Resolution Time ---
    if {'created', 'closed'}.issubset(df.columns):
        df['resolution_time_hours'] = (df['closed'] - df['created']).dt.total_seconds() / 3600
        mean_res = df['resolution_time_hours'].mean()
        median_res = df['resolution_time_hours'].median()
        logging.info(f"Mean resolution time: {mean_res:.2f} h, median: {median_res:.2f} h")
    else:
        mean_res = median_res = np.nan
        logging.warning("Cannot compute resolution time (missing columns).")

    # --- Backlog Over Time Plot ---
    if {'created', 'closed'}.issubset(df.columns):
        date_range = pd.date_range(df['created'].min(), df['closed'].max(), freq='D')
        backlog = []
        for day in date_range:
            n_open = ((df['created'] <= day) & ((df['closed'] > day) | df['closed'].isnull())).sum()
            backlog.append(n_open)
        plt.figure()
        plt.plot(date_range, backlog)
        plt.title("Backlog (Open tickets) over time")
        plt.xlabel("Date")
        plt.ylabel("Open tickets")
        os.makedirs('./output/png', exist_ok=True)
        plt.savefig('./output/png/backlog_over_time.png')
        plt.close()
        logging.info("Backlog over time plot saved.")
    else:
        logging.warning("Cannot plot backlog (missing date columns).")

    # --- Feedback Iterations Per Ticket ---
    if {'review_feedback_count', 'test_feedback_count'}.issubset(df.columns):
        df['total_feedback'] = df['review_feedback_count'].fillna(0) + df['test_feedback_count'].fillna(0)
        mean_loops = df['total_feedback'].mean()
        median_loops = df['total_feedback'].median()
        logging.info(f"Mean feedback iterations: {mean_loops:.2f}, median: {median_loops:.2f}")
    else:
        mean_loops = median_loops = np.nan
        logging.warning("Cannot compute feedback iterations (missing columns).")

    # --- Throughput (Tickets Closed per Month) ---
    if 'closed' in df.columns:
        df['closed_month'] = pd.to_datetime(df['closed']).dt.to_period('M')
        throughput_monthly = df.groupby('closed_month').size()
        throughput_mean = throughput_monthly.mean()
        logging.info(f"Mean monthly throughput: {throughput_mean:.2f} tickets/month")
    else:
        throughput_mean = np.nan
        logging.warning("Cannot compute throughput (missing 'closed').")

    # --- Utilization Estimate ---
    if arrival_rate and devrev_col:
        utilization = arrival_rate * df[devrev_col].mean()  # Assuming single resource/server
        logging.info(f"Estimated utilization (Dev+Review): {utilization:.3f}")
    else:
        utilization = np.nan
        logging.warning("Cannot estimate utilization (missing data).")

    # --- Export Results ---
    results = {
        "arrival_rate_per_hour": arrival_rate,
        "mean_resolution_time_hours": mean_res,
        "median_resolution_time_hours": median_res,
        "feedback_review_prob": p_review,
        "feedback_test_prob": p_test,
        "reopen_rate": reopen_rate,
        "mean_feedback_iterations": mean_loops,
        "median_feedback_iterations": median_loops,
        "throughput_monthly_mean": throughput_mean,
        "utilization_estimate": utilization,
    }

    # Add phase stats
    for phase in phase_results:
        for key in phase_results[phase]:
            results[f"{phase}_{key}"] = phase_results[phase][key]

    results_df = pd.DataFrame([results])
    os.makedirs('./output/csv', exist_ok=True)
    results_df.to_csv('./output/csv/parameter_estimates.csv', index=False)
    logging.info("Parameter estimates and key metrics saved to CSV.")

    logging.info("=== Parameter estimation and metrics computation complete ===")


if __name__ == "__main__":
    main()

"""
Usage notes:
- Place tickets_prs_merged.csv in ./output/csv/ or adjust the IN_CSV path.
- Run: python estimate_parameters.py
- Outputs:
    - ./output/logs/estimate_parameters.log   (detailed log)
    - ./output/png/*.png                     (plots)
    - ./output/csv/parameter_estimates.csv   (summary results)
All operations are logged. Adapt column names if your file uses different ones.
"""
