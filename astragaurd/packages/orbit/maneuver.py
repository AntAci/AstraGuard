#!/usr/bin/env python3
"""Deterministic maneuver planning for minimal delta-v recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


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
class ManeuverPolicy:
    miss_distance_target_m: float
    max_delta_v_mps: float = 0.5
    candidate_offsets_h: List[float] = None  # type: ignore[assignment]
    late_burn_minutes: float = 30.0

    def __post_init__(self) -> None:
        if self.candidate_offsets_h is None:
            self.candidate_offsets_h = [24.0, 12.0, 6.0, 2.0]


def _direction_gains() -> Dict[str, float]:
    return {
        "+T": 1.0,
        "-T": 1.0,
        "+R": 0.3,
        "-R": 0.3,
        "+N": 0.3,
        "-N": 0.3,
    }


def _required_delta_v(gap_m: float, lead_time_s: float, gain: float) -> Optional[float]:
    if lead_time_s <= 0.0 or gain <= 0.0:
        return None
    if gap_m <= 0.0:
        return 0.0
    return float(gap_m / (lead_time_s * gain))


def _expected_miss(current_miss_m: float, delta_v_mps: float, lead_time_s: float, gain: float) -> float:
    delta_m = float(delta_v_mps) * float(lead_time_s) * float(gain)
    return float(current_miss_m + max(0.0, delta_m))


def plan_min_delta_v(
    event: Dict[str, Any],
    policy: ManeuverPolicy,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    tca_utc = str(event.get("tca_utc", ""))
    tca_dt = _parse_iso_utc(tca_utc)
    current_miss_m = float(event.get("miss_distance_m", 0.0) or 0.0)
    target_m = float(max(0.0, policy.miss_distance_target_m))
    gap_m = float(max(0.0, target_m - current_miss_m))
    max_delta_v = float(max(0.0, policy.max_delta_v_mps))

    candidates: List[Dict[str, Any]] = []
    gains = _direction_gains()

    for offset_h in sorted(float(v) for v in policy.candidate_offsets_h):
        burn_time = tca_dt - timedelta(hours=offset_h)
        lead_time_s = float((tca_dt - burn_time).total_seconds())
        for direction, gain in gains.items():
            delta_v_req = _required_delta_v(gap_m=gap_m, lead_time_s=lead_time_s, gain=gain)
            feasible = delta_v_req is not None and delta_v_req <= max_delta_v
            candidates.append(
                {
                    "burn_time_utc": _iso_utc(burn_time),
                    "frame": "RTN",
                    "direction": direction,
                    "delta_v_mps": float(delta_v_req if delta_v_req is not None else max_delta_v + 1.0),
                    "expected_miss_m": _expected_miss(
                        current_miss_m=current_miss_m,
                        delta_v_mps=float(delta_v_req or 0.0),
                        lead_time_s=lead_time_s,
                        gain=gain,
                    ),
                    "feasible": bool(feasible),
                    "lead_time_s": lead_time_s,
                    "gain": gain,
                }
            )

    feasible_candidates = [row for row in candidates if row["feasible"]]
    feasible_candidates.sort(key=lambda row: (row["delta_v_mps"], row["lead_time_s"], row["direction"]))

    late_burn_dt = tca_dt - timedelta(minutes=float(policy.late_burn_minutes))
    late_lead_s = float((tca_dt - late_burn_dt).total_seconds())
    late_delta_v = _required_delta_v(gap_m=gap_m, lead_time_s=late_lead_s, gain=1.0)

    if feasible_candidates:
        selected = feasible_candidates[0]
        early_vs_late_ratio = None
        if late_delta_v is not None and late_delta_v > 0.0:
            early_vs_late_ratio = float(selected["delta_v_mps"] / late_delta_v)
        notes = "Selected minimal feasible delta-v candidate across timing and RTN direction grid."
        return {
            "burn_time_utc": selected["burn_time_utc"],
            "frame": "RTN",
            "direction": selected["direction"],
            "delta_v_mps": float(selected["delta_v_mps"]),
            "expected_miss_m": float(selected["expected_miss_m"]),
            "feasibility": "feasible",
            "early_vs_late_ratio": early_vs_late_ratio,
            "notes": notes,
            "current_miss_m": current_miss_m,
            "target_miss_m": target_m,
            "late_baseline": {
                "burn_time_utc": _iso_utc(late_burn_dt),
                "direction": "+T",
                "delta_v_mps": float(late_delta_v if late_delta_v is not None else max_delta_v + 1.0),
            },
        }

    notes = "No feasible candidate met delta-v cap; event remains maneuver-eligible but operationally deferred."
    return {
        "burn_time_utc": None,
        "frame": "RTN",
        "direction": None,
        "delta_v_mps": None,
        "expected_miss_m": float(current_miss_m),
        "feasibility": "infeasible",
        "early_vs_late_ratio": None,
        "notes": notes,
        "current_miss_m": current_miss_m,
        "target_miss_m": target_m,
        "late_baseline": {
            "burn_time_utc": _iso_utc(late_burn_dt),
            "direction": "+T",
            "delta_v_mps": float(late_delta_v if late_delta_v is not None else max_delta_v + 1.0),
        },
    }
