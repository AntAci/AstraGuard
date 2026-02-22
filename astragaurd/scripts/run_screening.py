#!/usr/bin/env python3
"""Run Step 2 conjunction screening and write ranked risk outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import numpy as np

# Ensure repo root is importable when running via: python3 scripts/run_screening.py
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.contracts.events import ConjunctionEvent
from packages.orbit.conjunction import find_refined_conjunctions
from packages.orbit.load_catalog import load_latest_tles
from packages.orbit.propagate import propagate_positions
from packages.orbit.risk import pc_assumed_encounter_isotropic, sigma_pair_m
from packages.orbit.spatial_hash import candidate_pairs_by_timestep


DEFAULT_GROUPS = [
    "ACTIVE",
    "COSMOS-1408-DEBRIS",
    "FENGYUN-1C-DEBRIS",
    "IRIDIUM-33-DEBRIS",
    "COSMOS-2251-DEBRIS",
]
MODEL_VERSION = "step2_v1_assumed_covariance"


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_groups(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        group = str(value).strip().upper()
        if not group or group in seen:
            continue
        out.append(group)
        seen.add(group)
    return out


def _datetime_to_julian(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    second = dt.second + dt.microsecond / 1_000_000.0
    if month <= 2:
        year -= 1
        month += 12
    a = math.floor(year / 100.0)
    b = 2 - a + math.floor(a / 4.0)
    frac_day = (hour + minute / 60.0 + second / 3600.0) / 24.0
    jd = (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
        + frac_day
    )
    return jd


def _gmst_rad(dt: datetime) -> float:
    jd = _datetime_to_julian(dt)
    t = (jd - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * t * t
        - (t * t * t) / 38710000.0
    )
    gmst_deg = gmst_deg % 360.0
    return math.radians(gmst_deg)


def _eci_to_ecef_snapshot(positions_km: np.ndarray, times_utc: List[datetime]) -> np.ndarray:
    ecef = np.empty_like(positions_km)
    for t_idx, dt in enumerate(times_utc):
        theta = _gmst_rad(dt)
        c = math.cos(theta)
        s = math.sin(theta)
        x = positions_km[t_idx, :, 0]
        y = positions_km[t_idx, :, 1]
        z = positions_km[t_idx, :, 2]
        ecef[t_idx, :, 0] = c * x + s * y
        ecef[t_idx, :, 1] = -s * x + c * y
        ecef[t_idx, :, 2] = z
    return ecef


def _write_top_outputs(processed_dir: Path, events: List[ConjunctionEvent]) -> None:
    json_path = processed_dir / "top_conjunctions.json"
    csv_path = processed_dir / "top_conjunctions.csv"

    json_path.write_text(
        json.dumps([event.to_dict() for event in events], indent=2) + "\n",
        encoding="utf-8",
    )

    fieldnames = [
        "event_id",
        "primary_id",
        "secondary_id",
        "tca_utc",
        "miss_distance_m",
        "relative_speed_mps",
        "pc_assumed",
        "risk_score",
        "window_start_utc",
        "window_end_utc",
        "model_version",
        "assumptions_json",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            row = event.to_dict()
            row["assumptions_json"] = json.dumps(event.assumptions, sort_keys=True)
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    print(f"[INFO] Wrote {json_path}")
    print(f"[INFO] Wrote {csv_path}")


def _write_cesium_snapshot(processed_dir: Path, generated_at_utc: str, times_utc, positions_km, valid_tles):
    snapshot_path = processed_dir / "cesium_orbits_snapshot.json"

    downsample_step = 3
    times_ds = list(times_utc[::downsample_step])
    pos_ds = positions_km[::downsample_step, :, :]

    frame = "ECEF_KM_APPROX"
    notes = "Approximate ECI->ECEF using GMST z-rotation for demo visualization."
    try:
        transformed = _eci_to_ecef_snapshot(pos_ds, times_ds)
        position_field = "positions_ecef_km"
    except Exception as exc:
        print(f"[WARN] ECI->ECEF conversion failed ({exc}); writing ECI snapshot instead.")
        transformed = pos_ds
        frame = "ECI_KM"
        notes = "ECI frame (fallback)."
        position_field = "positions_eci_km"

    objects = []
    object_count = int(transformed.shape[1]) if transformed.ndim == 3 else 0
    for idx in range(object_count):
        entry = {
            "norad_id": int(valid_tles[idx].norad_id),
            "name": valid_tles[idx].name,
            "source_group": str(valid_tles[idx].source_group).upper(),
            position_field: transformed[:, idx, :].round(6).tolist(),
        }
        objects.append(entry)

    payload = {
        "generated_at_utc": generated_at_utc,
        "frame": frame,
        "times_utc": [_iso_utc(ts) for ts in times_ds],
        "downsample_step": downsample_step,
        "notes": notes,
        "objects": objects,
    }

    snapshot_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    print(f"[INFO] Wrote {snapshot_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 72h conjunction screening with assumed-covariance Pc.")
    parser.add_argument("--db", default="data/processed/tles.sqlite")
    parser.add_argument("--groups", nargs="+", default=DEFAULT_GROUPS)
    parser.add_argument("--max-objects", type=int, default=3000)
    parser.add_argument("--horizon-hours", type=float, default=72.0)
    parser.add_argument("--dt", type=int, default=600)
    parser.add_argument("--dt-refine", type=int, default=60)
    parser.add_argument("--voxel-km", type=float, default=50.0)
    parser.add_argument("--hbr-m", type=float, default=25.0)
    parser.add_argument("--sigma-payload-m", type=float, default=200.0)
    parser.add_argument("--sigma-debris-m", type=float, default=500.0)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    groups = _normalize_groups(args.groups)
    if not groups:
        print("[ERROR] No valid groups after normalization.")
        return 1

    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = REPO_ROOT / db_path
    if not db_path.exists():
        print(f"[ERROR] DB path not found: {db_path}")
        return 1

    processed_dir = REPO_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    run_started = datetime.now(timezone.utc)
    print(f"[INFO] Step 2 screening start: {_iso_utc(run_started)}")
    print(f"[INFO] Model version: {MODEL_VERSION}")
    print(f"[INFO] Using deterministic Pc method; seed accepted for compatibility: {args.seed}")

    stage_start = time.time()
    tles = load_latest_tles(
        db_path=db_path,
        groups=groups,
        max_objects=args.max_objects,
        prefer_latest_fetch=True,
        dedupe_by_norad=True,
    )
    print(f"[INFO] Stage load_catalog took {time.time() - stage_start:.2f}s")
    if not tles:
        print("[ERROR] No TLEs loaded for screening.")
        return 1

    stage_start = time.time()
    times_utc, positions_km, norad_ids, valid_tles = propagate_positions(
        tles=tles,
        start_utc=run_started,
        horizon_hours=args.horizon_hours,
        dt_s=args.dt,
    )
    print(f"[INFO] Stage propagate took {time.time() - stage_start:.2f}s")
    if positions_km.shape[1] == 0:
        print("[ERROR] No valid propagated objects available.")
        return 1

    stage_start = time.time()
    candidate_stream = candidate_pairs_by_timestep(positions_km=positions_km, voxel_km=args.voxel_km)
    print(f"[INFO] Stage candidate_generation took {time.time() - stage_start:.2f}s")

    stage_start = time.time()
    refined = find_refined_conjunctions(
        valid_tles=valid_tles,
        norad_ids=norad_ids,
        times_utc=times_utc,
        positions_km=positions_km,
        candidate_stream=candidate_stream,
        dt_s=args.dt,
        dt_refine_s=args.dt_refine,
        refine_half_window_steps=2,
    )
    print(f"[INFO] Stage refine_conjunctions took {time.time() - stage_start:.2f}s")

    assumptions_base = {
        "dt_s": int(args.dt),
        "dt_refine_s": int(args.dt_refine),
        "horizon_hours": float(args.horizon_hours),
        "hard_body_radius_m": float(args.hbr_m),
        "sigma_payload_m": float(args.sigma_payload_m),
        "sigma_debris_m": float(args.sigma_debris_m),
        "voxel_km": float(args.voxel_km),
        "catalog_groups_used": groups,
    }

    stage_start = time.time()
    events: List[ConjunctionEvent] = []
    for row in refined:
        primary_id = int(row["primary_id"])
        secondary_id = int(row["secondary_id"])
        primary_group = str(row["primary_group"]).upper()
        secondary_group = str(row["secondary_group"]).upper()

        if secondary_id < primary_id:
            primary_id, secondary_id = secondary_id, primary_id
            primary_group, secondary_group = secondary_group, primary_group

        sigma_pair = sigma_pair_m(
            primary_group,
            secondary_group,
            args.sigma_payload_m,
            args.sigma_debris_m,
        )
        miss_distance_m = float(row["miss_distance_m"])
        pc = pc_assumed_encounter_isotropic(
            miss_distance_m=miss_distance_m,
            sigma_m=sigma_pair,
            hard_body_radius_m=args.hbr_m,
        )
        risk_score = pc

        assumptions = dict(assumptions_base)
        event = ConjunctionEvent(
            event_id=f"{primary_id}_{secondary_id}_{row['tca_utc']}",
            primary_id=primary_id,
            secondary_id=secondary_id,
            tca_utc=str(row["tca_utc"]),
            miss_distance_m=miss_distance_m,
            relative_speed_mps=float(row["relative_speed_mps"]),
            pc_assumed=float(pc),
            risk_score=float(risk_score),
            window_start_utc=str(row["window_start_utc"]),
            window_end_utc=str(row["window_end_utc"]),
            model_version=MODEL_VERSION,
            assumptions=assumptions,
        )
        events.append(event)

    events.sort(key=lambda e: (-e.risk_score, e.miss_distance_m))
    top_events = events[: max(0, int(args.top_k))]
    print(f"[INFO] Stage risk_scoring took {time.time() - stage_start:.2f}s")

    _write_top_outputs(processed_dir, top_events)
    _write_cesium_snapshot(
        processed_dir=processed_dir,
        generated_at_utc=_iso_utc(datetime.now(timezone.utc)),
        times_utc=times_utc,
        positions_km=positions_km,
        valid_tles=valid_tles,
    )

    print("[INFO] Top 10 conjunctions:")
    preview = top_events[:10]
    if not preview:
        print("[WARN] No conjunction events found.")
    for event in preview:
        print(
            "  "
            f"{event.tca_utc}, {event.primary_id}, {event.secondary_id}, "
            f"{event.miss_distance_m:.3f}, {event.pc_assumed:.6e}, {event.relative_speed_mps:.3f}"
        )

    print(
        f"[INFO] Completed screening with {len(events)} events scored; "
        f"top_k_written={len(top_events)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
