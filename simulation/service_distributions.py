# v2
# file: simulation/service_distributions.py

"""
Provides functions to sample service times for each stage using empirically fitted distributions.
Supports easy swapping of distribution type and parameters defined in config.
"""

from __future__ import annotations

import logging

import numpy as np

from .config import SERVICE_TIME_PARAMS


def sample_service_time(stage: str) -> float:
    """Sample a service time for the given stage using configured parameters."""
    if stage not in SERVICE_TIME_PARAMS:
        raise ValueError(f"Unknown stage {stage} requested for service time sampling.")

    stage_config = SERVICE_TIME_PARAMS[stage]
    dist_type = stage_config["dist"]
    params = stage_config["params"].copy()
    loc = params.pop("loc", 0.0)

    def draw_sample():
        if dist_type == "lognorm":
            s = params["s"]
            scale = params.get("scale", 1.0)
            return np.random.lognormal(mean=np.log(scale), sigma=s)
        if dist_type == "weibull":
            shape = params["shape"]
            scale = params.get("scale", 1.0)
            return np.random.weibull(shape) * scale
        if dist_type == "gamma":
            shape = params["shape"]
            scale = params.get("scale", 1.0)
            return np.random.gamma(shape, scale)
        if dist_type == "expon":
            scale = params.get("scale", 1.0)
            return np.random.exponential(scale)
        raise ValueError(f"Unsupported distribution '{dist_type}' for stage {stage}.")

    for attempt in range(50):
        sample = draw_sample()
        value = loc + sample
        if value > 0:
            return float(value)

    logging.warning(
        "Service time sampling for %s produced non-positive values; clipping to epsilon after retries.",
        stage,
    )
    return 1e-6
