# v2
# file: simulation/config.py

"""
Central configuration for simulation parameters.
All times are in DAYS. Arrival rate is tickets per DAY.
Distributions are SciPy-style with explicit params (shape/scale/loc) and include 'loc' if a sliding fit was selected.
Generated automatically by simulation/generate_sim_config.py on 2025-08-19 15:33:48.
Repo: https://github.com/GVCUTV/BK_ASF.git
"""

# ----------------------------- General ----------------------------- #
SIM_DURATION = 365.000000  # days of simulated time

# ----------------------------- Logging ----------------------------- #
LOG_FILE = "logs/simulation.log"

# --------------------------- Arrival process --------------------------- #
# Estimated from ETL data in window [2009-04-01 .. 2017-10-18)
ARRIVAL_RATE = 0.3074951954  # tickets/day (lambda)

# --------------------------- Service capacity --------------------------- #
# Calibrated to observed capacity or tuned to keep utilizations reasonable
N_DEVS = 3
N_TESTERS = 2

# --------------------------- Feedback probabilities --------------------------- #
# Estimated from ETL (review/test cycles); defaults used if columns not available
FEEDBACK_P_DEV  = 0.2000000000   # after Dev/Review
FEEDBACK_P_TEST = 0.1500000000   # after Testing

# --------------------------- Service time distributions --------------------------- #
# Names follow SciPy; params are explicit and include 'loc' (shift), if any.
SERVICE_TIME_PARAMS = {
    "dev_review": {
        "dist": "lognorm",
        "params": {"loc": -1042.86549, "s": 0.1516685, "scale": 1069.60329}
    },
    "testing": {
        "dist": "lognorm",
        "params": {"loc": -1042.86549, "s": 0.1516685, "scale": 1069.60329}
    }
}
