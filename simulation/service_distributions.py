# v1
# file: simulation/service_distributions.py

"""
Provides functions to sample service times for each stage using empirically fitted distributions.
Supports easy swapping of distribution type and parameters.
"""

import numpy as np
from config import SERVICE_TIME_PARAMS

def sample_service_time(stage):
    """
    Sample a service time for a given stage ('dev_review' or 'testing')
    using the empirically fitted distribution and parameters.
    """
    dist_type, params = SERVICE_TIME_PARAMS[stage]
    if dist_type == 'lognorm':
        mu, sigma = params
        return np.random.lognormal(mean=mu, sigma=sigma)
    elif dist_type == 'weibull':
        shape, scale = params
        return np.random.weibull(shape) * scale
    elif dist_type == 'gamma':
        shape, scale = params
        return np.random.gamma(shape, scale)
    elif dist_type == 'expon':
        scale, = params
        return np.random.exponential(scale)
    else:
        raise ValueError(f"Unknown distribution: {dist_type}")

