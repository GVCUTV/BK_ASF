# v4
# file: simulation/config.py

"""
Central configuration for simulation parameters.
All times are in DAYS. Arrival rate is tickets per DAY.
Distributions are SciPy-style with explicit params (shape/scale/loc) and include 'loc' if a sliding fit was selected.
Generated automatically by simulation/generate_sim_config.py on 2025-11-16 18:50:44.
Repo: https://github.com/GVCUTV/BK_ASF.git
"""
import os

# ----------------------------- General ----------------------------- #
SIM_DURATION = 365.000000  # days of simulated time

# ----------------------------- Logging ----------------------------- #
LOG_FILE = "logs/simulation.log"

# --------------------------- Arrival process --------------------------- #
# Estimated from ETL data in window [2009-04-01 .. 2017-10-18)
ARRIVAL_RATE = 0.3074951954  # tickets/day (lambda)

# --------------------------- Service capacity --------------------------- #
# Derived from ETL distinct actors in the same window
N_DEVS = 44        # source=dev_user
N_TESTERS = 22  # source=heuristic_ratio
TOTAL_CONTRIBUTORS = 44

# --------------------------- Feedback probabilities --------------------------- #
# Estimated from ETL within the same window
FEEDBACK_P_DEV  = 0.0000000000
FEEDBACK_P_TEST = 0.0000000000

# --------------------------- Service time distributions --------------------------- #
# Names follow SciPy; params are explicit and include 'loc' (shift), if any.
SERVICE_TIME_PARAMS = {
    "dev_review": {
        "dist": "lognorm",
        "params": {"s": 0.151668487, "loc": -1042.86559, "scale": 1069.60338}
    },
    "testing": {
        "dist": "lognorm",
        "params": {"s": 0.151668487, "loc": -1042.86559, "scale": 1069.60338}
    }
}

# --------------------------- State parameter inputs --------------------------- #
STATE_PARAMETER_PATHS = {
    "matrix_P": "data/state_parameters/matrix_P.csv",
    "service_params": "data/state_parameters/service_params.json",
    "stint_pmfs": [
        "data/state_parameters/stint_PMF_DEV.csv",
        "data/state_parameters/stint_PMF_OFF.csv",
        "data/state_parameters/stint_PMF_REV.csv",
        "data/state_parameters/stint_PMF_TEST.csv"
    ]
}

# --------------------------- Churn weighting --------------------------- #
CHURN_WEIGHT_ADD = 1.0
CHURN_WEIGHT_MOD = 1.0
CHURN_WEIGHT_DEL = 0.5

# --------------------------- Random seeds --------------------------- #
GLOBAL_RANDOM_SEED = 22015001
seed = os.getenv("BK_ASF_SIM_SEED", GLOBAL_RANDOM_SEED)
GLOBAL_RANDOM_SEED = int(seed)
SEED_OVERRIDE_ENV_VAR = "SIMULATION_RANDOM_SEED"
ARRIVAL_STREAM_SEED = 22015002
SERVICE_TIME_STREAM_SEED = 22015003
STATE_TRANSITION_STREAM_SEED = 22015004
