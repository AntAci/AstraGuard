#!/usr/bin/env python3
"""Trend-gated risk utilities for local conjunction windows around TCA."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
from sgp4.api import Satrec, jday

from packages.orbit.risk import pc_assumed_encounter_isotropic, sigma_pair_effective_m, sigma_pair_m


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso_utc(value: str) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class TrendConfig:
    window_minutes: int = 30
    cadence_seconds: int = 60
    threshold: float = 1e-5
    defer_hours: float = 24.0
    critical_override: float = 1e-3
    hard_body_radius_m: float = 25.0
    cov_model: str = "anisotropic_rtn"
    sigma_payload_m: float = 200.0
    sigma_debris_m: float = 500.0
    payload_base_r_m: float = 200.0
    payload_base_t_m: float = 260.0
    payload_base_n_m: float = 200.0
    debris_base_r_m: float = 500.0
    debris_base_t_m: float = 700.0
    debris_base_n_m: float = 500.0
    sigma_t_growth_mps: float = 0.02


def _build_sample_times(tca_utc: str, window_minutes: int, cadence_seconds: int) -> List[datetime]:
    tca = _parse_iso_utc(tca_utc)
    half_window_s = max(0, int(window_minutes)) * 60
    cadence_s = max(1, int(cadence_seconds))
    offsets = range(-half_window_s, half_window_s + 1, cadence_s)
    times = [tca + timedelta(seconds=int(offset)) for offset in offsets]
    if not times:
        times = [tca]
    if times[-1] != tca + timedelta(seconds=half_window_s):
        times.append(tca + timedelta(seconds=half_window_s))
    return times


def _propagate_sat(sat: Satrec, times_utc: Sequence[datetime]) -> Optional[np.ndarray]:
    coords = np.empty((len(times_utc), 3), dtype=np.float64)
    for idx, dt in enumerate(times_utc):
        jd, fr = jday(
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second + dt.microsecond / 1_000_000.0,
        )
        err, r, _ = sat.sgp4(jd, fr)
        if err != 0:
            return None
        coords[idx, :] = r
        if not np.all(np.isfinite(coords[idx, :])):
            return None
    return coords


def _sigma_pair_for_time(
    primary_group: str,
    secondary_group: str,
    delta_t_s: float,
    cfg: TrendConfig,
) -> float:
    if str(cfg.cov_model).strip().lower() == "legacy":
        return sigma_pair_m(
            primary_group,
            secondary_group,
            cfg.sigma_payload_m,
            cfg.sigma_debris_m,
        )
    return sigma_pair_effective_m(
        primary_group_upper=primary_group,
        secondary_group_upper=secondary_group,
        delta_t_s=delta_t_s,
        payload_base_r_m=cfg.payload_base_r_m,
        payload_base_t_m=cfg.payload_base_t_m,
        payload_base_n_m=cfg.payload_base_n_m,
        debris_base_r_m=cfg.debris_base_r_m,
        debris_base_t_m=cfg.debris_base_t_m,
        debris_base_n_m=cfg.debris_base_n_m,
        along_track_growth_mps=cfg.sigma_t_growth_mps,
    )


def build_local_pc_series(
    tca_utc: str,
    primary_line1: str,
    primary_line2: str,
    secondary_line1: str,
    secondary_line2: str,
    primary_group: str,
    secondary_group: str,
    config: TrendConfig,
) -> List[Dict[str, float | str]]:
    """Build local Pc time series around TCA using SGP4 for one pair only."""

    times_utc = _build_sample_times(
        tca_utc=tca_utc,
        window_minutes=config.window_minutes,
        cadence_seconds=config.cadence_seconds,
    )
    sat_primary = Satrec.twoline2rv(primary_line1, primary_line2)
    sat_secondary = Satrec.twoline2rv(secondary_line1, secondary_line2)

    primary_pos_km = _propagate_sat(sat_primary, times_utc)
    secondary_pos_km = _propagate_sat(sat_secondary, times_utc)
    if primary_pos_km is None or secondary_pos_km is None:
        return []

    tca_dt = _parse_iso_utc(tca_utc)
    rel_km = primary_pos_km - secondary_pos_km

    samples: List[Dict[str, float | str]] = []
    for idx, sample_dt in enumerate(times_utc):
        miss_m = float(np.linalg.norm(rel_km[idx]) * 1000.0)
        delta_t_s = float((sample_dt - tca_dt).total_seconds())
        sigma_pair = _sigma_pair_for_time(primary_group, secondary_group, delta_t_s, config)
        pc = pc_assumed_encounter_isotropic(
            miss_distance_m=miss_m,
            sigma_m=sigma_pair,
            hard_body_radius_m=config.hard_body_radius_m,
        )
        samples.append({
            "t_utc": _iso_utc(sample_dt),
            "miss_m": miss_m,
            "pc": float(pc),
        })
    return samples


def _series_time_seconds(series: Iterable[Dict[str, Any]]) -> np.ndarray:
    times = [_parse_iso_utc(str(item.get("t_utc"))) for item in series]
    if not times:
        return np.array([], dtype=np.float64)
    t0 = times[0]
    return np.array([(ts - t0).total_seconds() for ts in times], dtype=np.float64)


def compute_trend_metrics(
    pc_series: List[Dict[str, Any]],
    tca_utc: str,
    now_utc: Optional[datetime],
    config: TrendConfig,
) -> Dict[str, Any]:
    eps = 1e-16
    pcs = np.array([max(0.0, float(item.get("pc", 0.0))) for item in pc_series], dtype=np.float64)
    x = _series_time_seconds(pc_series)

    if pcs.size == 0:
        pc_peak = 0.0
        pc_slope = 0.0
        pc_stability = 0.0
    else:
        pc_peak = float(np.max(pcs))
        stable_cutoff = 0.5 * pc_peak
        pc_stability = float(np.mean(pcs >= stable_cutoff)) if pc_peak > 0.0 else 0.0
        if pcs.size >= 2 and np.max(x) > np.min(x):
            y = np.log10(pcs + eps)
            slope, _ = np.polyfit(x, y, 1)
            pc_slope = float(slope)
        else:
            pc_slope = 0.0

    now_dt = now_utc or datetime.now(timezone.utc)
    tca_dt = _parse_iso_utc(tca_utc)
    time_to_tca_hours = float((tca_dt - now_dt).total_seconds() / 3600.0)

    return {
        "pc_peak": pc_peak,
        "pc_slope": pc_slope,
        "pc_stability": pc_stability,
        "window_minutes": int(config.window_minutes),
        "cadence_seconds": int(config.cadence_seconds),
        "sample_count": int(len(pc_series)),
        "time_to_tca_hours": time_to_tca_hours,
        "threshold": float(config.threshold),
        "critical_override": float(config.critical_override),
    }


def compute_defer_until_utc(
    tca_utc: str,
    now_utc: Optional[datetime] = None,
    revisit_hours: float = 6.0,
    tca_guard_hours: float = 12.0,
) -> str:
    now_dt = now_utc or datetime.now(timezone.utc)
    tca_dt = _parse_iso_utc(tca_utc)
    candidate_a = tca_dt - timedelta(hours=float(tca_guard_hours))
    candidate_b = now_dt + timedelta(hours=float(revisit_hours))
    defer_until = min(candidate_a, candidate_b)
    min_allowed = now_dt + timedelta(minutes=10)
    if defer_until < min_allowed:
        defer_until = min_allowed
    return _iso_utc(defer_until)


def classify_trend_gate(
    trend_metrics: Dict[str, Any],
    tca_utc: str,
    now_utc: Optional[datetime],
    defer_hours: float,
) -> Dict[str, Any]:
    pc_peak = float(trend_metrics.get("pc_peak", 0.0))
    pc_slope = float(trend_metrics.get("pc_slope", 0.0))
    pc_stability = float(trend_metrics.get("pc_stability", 0.0))
    threshold = float(trend_metrics.get("threshold", 1e-5))
    critical_override = float(trend_metrics.get("critical_override", 1e-3))
    time_to_tca_hours = float(trend_metrics.get("time_to_tca_hours", 0.0))

    if time_to_tca_hours > float(defer_hours) and pc_peak < critical_override:
        return {
            "decision_mode_hint": "DEFER",
            "gate_reason_code": "FAR_FROM_TCA",
            "gate_reason": "Risk is too far from TCA and below critical override; defer for re-evaluation.",
            "defer_until_utc": compute_defer_until_utc(tca_utc=tca_utc, now_utc=now_utc),
        }

    if pc_peak < threshold:
        return {
            "decision_mode_hint": "IGNORE",
            "gate_reason_code": "BELOW_THRESHOLD",
            "gate_reason": "Peak collision probability in local window is below maneuver threshold.",
            "defer_until_utc": None,
        }

    if pc_slope <= 0.0 and pc_stability < 0.3:
        return {
            "decision_mode_hint": "DEFER",
            "gate_reason_code": "SPIKY_NOT_SUSTAINED",
            "gate_reason": "Risk profile is not sustained near peak; defer and re-evaluate.",
            "defer_until_utc": compute_defer_until_utc(tca_utc=tca_utc, now_utc=now_utc),
        }

    return {
        "decision_mode_hint": "MANEUVER",
        "gate_reason_code": "SUSTAINED_RISK",
        "gate_reason": "Risk is sustained/rising near TCA; event is maneuver-eligible.",
        "defer_until_utc": None,
    }


def evaluate_trend_gate(
    *,
    event: Dict[str, Any],
    primary_line1: str,
    primary_line2: str,
    secondary_line1: str,
    secondary_line2: str,
    primary_group: str,
    secondary_group: str,
    config: TrendConfig,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    pc_series = build_local_pc_series(
        tca_utc=str(event.get("tca_utc", "")),
        primary_line1=primary_line1,
        primary_line2=primary_line2,
        secondary_line1=secondary_line1,
        secondary_line2=secondary_line2,
        primary_group=primary_group,
        secondary_group=secondary_group,
        config=config,
    )

    if not pc_series:
        fallback_pc = float(event.get("pc_assumed", event.get("p_collision", 0.0)) or 0.0)
        fallback_miss = float(event.get("miss_distance_m", 0.0) or 0.0)
        pc_series = [{
            "t_utc": str(event.get("tca_utc", "")),
            "miss_m": fallback_miss,
            "pc": fallback_pc,
        }]

    trend_metrics = compute_trend_metrics(
        pc_series=pc_series,
        tca_utc=str(event.get("tca_utc", "")),
        now_utc=now_utc,
        config=config,
    )
    gate = classify_trend_gate(
        trend_metrics=trend_metrics,
        tca_utc=str(event.get("tca_utc", "")),
        now_utc=now_utc,
        defer_hours=config.defer_hours,
    )

    trend_metrics["gate_decision"] = gate["decision_mode_hint"]
    trend_metrics["gate_reason_code"] = gate["gate_reason_code"]
    trend_metrics["gate_reason"] = gate["gate_reason"]

    return {
        "pc_series": pc_series,
        "trend_metrics": trend_metrics,
        "decision_mode_hint": gate["decision_mode_hint"],
        "defer_until_utc": gate["defer_until_utc"],
        "gate_reason_code": gate["gate_reason_code"],
        "gate_reason": gate["gate_reason"],
    }
