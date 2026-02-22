#!/usr/bin/env python3
"""Risk metric utilities for assumed-covariance conjunction scoring."""

from __future__ import annotations

import math

import numpy as np


def classify_sigma_m(source_group_upper, sigma_payload_m, sigma_debris_m) -> float:
    group = str(source_group_upper or "").upper()
    if "DEBRIS" in group:
        return float(sigma_debris_m)
    return float(sigma_payload_m)


def pc_assumed_encounter_isotropic(
    miss_distance_m,
    sigma_m,
    hard_body_radius_m,
    n_r=400,
    n_theta=360,
) -> float:
    """Deterministic Pc approximation for isotropic 2D Gaussian.

    We integrate the 2D Gaussian over the hard-body disk offset by miss distance.
    The angular term is handled analytically via I0 for speed and stability.
    """
    del n_theta  # API compatibility; deterministic path does not require angular discretization.

    r = float(max(0.0, miss_distance_m))
    sigma = float(sigma_m)
    radius = float(max(0.0, hard_body_radius_m))

    if sigma <= 0.0 or radius <= 0.0:
        return 0.0

    count = max(16, int(n_r))
    rho = np.linspace(0.0, radius, count, dtype=np.float64)

    scale = sigma * sigma
    exponent = -((rho * rho) + (r * r)) / (2.0 * scale)
    integrand = (rho / scale) * np.exp(exponent) * np.i0((rho * r) / scale)
    pc = float(np.trapz(integrand, rho))

    if not np.isfinite(pc):
        return 0.0
    return float(max(0.0, min(1.0, pc)))


def sigma_pair_m(primary_group_upper, secondary_group_upper, sigma_payload_m, sigma_debris_m) -> float:
    s1 = classify_sigma_m(primary_group_upper, sigma_payload_m, sigma_debris_m)
    s2 = classify_sigma_m(secondary_group_upper, sigma_payload_m, sigma_debris_m)
    return float(math.sqrt((s1 * s1) + (s2 * s2)))
