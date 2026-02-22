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


def sigma_components_for_group(
    source_group_upper,
    delta_t_s: float,
    payload_base_r_m: float,
    payload_base_t_m: float,
    payload_base_n_m: float,
    debris_base_r_m: float,
    debris_base_t_m: float,
    debris_base_n_m: float,
    along_track_growth_mps: float,
) -> tuple[float, float, float]:
    group = str(source_group_upper or "").upper()
    is_debris = "DEBRIS" in group
    if is_debris:
        sigma_r = float(debris_base_r_m)
        sigma_t = float(debris_base_t_m)
        sigma_n = float(debris_base_n_m)
    else:
        sigma_r = float(payload_base_r_m)
        sigma_t = float(payload_base_t_m)
        sigma_n = float(payload_base_n_m)
    sigma_t = sigma_t + float(max(0.0, along_track_growth_mps)) * abs(float(delta_t_s))
    return max(0.0, sigma_r), max(0.0, sigma_t), max(0.0, sigma_n)


def sigma_effective_from_rtn(sigma_r_m: float, sigma_t_m: float, sigma_n_m: float) -> float:
    # Minimal deterministic effective sigma mapping for encounter-plane approximation.
    total = (float(sigma_r_m) ** 2) + (float(sigma_t_m) ** 2) + (float(sigma_n_m) ** 2)
    return float(math.sqrt(total / 3.0))


def sigma_pair_effective_m(
    primary_group_upper,
    secondary_group_upper,
    delta_t_s: float,
    payload_base_r_m: float,
    payload_base_t_m: float,
    payload_base_n_m: float,
    debris_base_r_m: float,
    debris_base_t_m: float,
    debris_base_n_m: float,
    along_track_growth_mps: float,
) -> float:
    p_r, p_t, p_n = sigma_components_for_group(
        source_group_upper=primary_group_upper,
        delta_t_s=delta_t_s,
        payload_base_r_m=payload_base_r_m,
        payload_base_t_m=payload_base_t_m,
        payload_base_n_m=payload_base_n_m,
        debris_base_r_m=debris_base_r_m,
        debris_base_t_m=debris_base_t_m,
        debris_base_n_m=debris_base_n_m,
        along_track_growth_mps=along_track_growth_mps,
    )
    s_r, s_t, s_n = sigma_components_for_group(
        source_group_upper=secondary_group_upper,
        delta_t_s=delta_t_s,
        payload_base_r_m=payload_base_r_m,
        payload_base_t_m=payload_base_t_m,
        payload_base_n_m=payload_base_n_m,
        debris_base_r_m=debris_base_r_m,
        debris_base_t_m=debris_base_t_m,
        debris_base_n_m=debris_base_n_m,
        along_track_growth_mps=along_track_growth_mps,
    )
    p_eff = sigma_effective_from_rtn(p_r, p_t, p_n)
    s_eff = sigma_effective_from_rtn(s_r, s_t, s_n)
    return float(math.sqrt((p_eff * p_eff) + (s_eff * s_eff)))
