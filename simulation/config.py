# v1
# file: simulation/config.py

"""
Central configuration for simulation parameters.
Tune all parameters and distributions here.
"""

# General
SIM_DURATION = 5000.0  # Simulated time units (can be hours, days...)

# Logging
LOG_FILE = "logs/simulation.log"

# Arrival process
ARRIVAL_RATE = 0.15  # tickets per time unit (lambda for Poisson process)

# Service process
N_DEVS = 3  # parallel dev/review servers
N_TESTERS = 2  # parallel testers

# Feedback probabilities
FEEDBACK_P_DEV = 0.2  # feedback after dev/review (empirical estimate)
FEEDBACK_P_TEST = 0.15  # feedback after testing

# Service time distributions, fitted from data: {'stage': ('distribution', (params))}
# Examples below: replace with your own fitted params!
SERVICE_TIME_PARAMS = {
    'dev_review': ('lognorm', (2.0, 0.7)),  # lognormal(mu, sigma)
    'testing':    ('weibull', (1.5, 5.0)),  # weibull(shape, scale)
}

