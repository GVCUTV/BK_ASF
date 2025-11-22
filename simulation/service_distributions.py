# v3
# file: simulation/service_distributions.py

"""
Provides functions to sample service times for each stage using empirically fitted distributions.
Supports easy swapping of distribution type and parameters defined in config.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np

from .config import SERVICE_TIME_PARAMS

SUPPORTED_DISTRIBUTIONS = {
    "lognorm",
    "lognormal",
    "weibull",
    "weibull_min",
    "gamma",
    "expon",
    "pareto",
    "norm",
    "normal",
}

_DISTRIBUTION_LOGGED = False


def _log_service_configuration_once() -> None:
    """Emit the service-time distribution choices once at startup."""
    global _DISTRIBUTION_LOGGED
    if _DISTRIBUTION_LOGGED:
        return

    logger = logging.getLogger(__name__)
    for stage, cfg in SERVICE_TIME_PARAMS.items():
        logger.info(
            "Service time config for %s: dist=%s params=%s", stage, cfg.get("dist"), cfg.get("params"),
        )
    _DISTRIBUTION_LOGGED = True


def _draw_sample(dist_type: str, params: Dict[str, Any]) -> float:
    """Draw a raw sample from the requested distribution."""
    if dist_type in {"lognorm", "lognormal"}:
        sigma = params.get("s") or params.get("sigma")
        if sigma is None:
            raise ValueError("Lognormal distribution requires 's' or 'sigma' parameter.")
        scale = params.get("scale", 1.0)
        return float(np.random.lognormal(mean=np.log(scale), sigma=sigma))

    if dist_type in {"weibull", "weibull_min"}:
        shape = params.get("shape") or params.get("k")
        if shape is None:
            raise ValueError("Weibull distribution requires 'shape' or 'k' parameter.")
        scale = params.get("scale", 1.0)
        return float(np.random.weibull(shape) * scale)

    if dist_type == "gamma":
        shape = params.get("shape") or params.get("k")
        if shape is None:
            raise ValueError("Gamma distribution requires 'shape' or 'k' parameter.")
        scale = params.get("scale", 1.0)
        return float(np.random.gamma(shape, scale))

    if dist_type == "expon":
        scale = params.get("scale", 1.0)
        return float(np.random.exponential(scale))

    if dist_type == "pareto":
        shape = params.get("shape") or params.get("alpha")
        if shape is None:
            raise ValueError("Pareto distribution requires 'shape' or 'alpha' parameter.")
        scale = params.get("scale", 1.0)
        return float(np.random.pareto(shape) * scale)

    if dist_type in {"norm", "normal"}:
        mean = params.get("mean", 0.0)
        scale = params.get("scale", 1.0)
        return float(np.random.normal(loc=mean, scale=scale))

    raise ValueError(
        f"Unsupported distribution '{dist_type}'. Supported options: {sorted(SUPPORTED_DISTRIBUTIONS)}.")


def sample_service_time(stage: str) -> float:
    """Sample a service time for the given stage using configured parameters."""
    _log_service_configuration_once()

    if stage not in SERVICE_TIME_PARAMS:
        raise ValueError(f"Unknown stage {stage} requested for service time sampling.")

    stage_config = SERVICE_TIME_PARAMS[stage]
    dist_type = stage_config.get("dist")
    params = dict(stage_config.get("params", {}))
    if dist_type is None:
        raise ValueError(f"No distribution configured for stage {stage} in SERVICE_TIME_PARAMS.")
    if dist_type not in SUPPORTED_DISTRIBUTIONS:
        raise ValueError(
            f"Unsupported distribution '{dist_type}' for stage {stage}. Supported options: {sorted(SUPPORTED_DISTRIBUTIONS)}.")

    loc = float(params.pop("loc", 0.0))

    for attempt in range(50):
        sample = _draw_sample(dist_type, params)
        value = loc + sample
        if value > 0:
            return float(value)

    logging.warning(
        "Service time sampling for %s produced non-positive values; clipping to epsilon after retries.",
        stage,
    )
    return 1e-6
