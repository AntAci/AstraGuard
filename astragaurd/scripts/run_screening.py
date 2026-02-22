#!/usr/bin/env python3
"""Run Step 2 conjunction screening and write ranked risk outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# Ensure repo root is importable when running via: python3 scripts/run_screening.py
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.contracts.events import (  # noqa: E402
    CesiumObject,
    CesiumSnapshot,
    CesiumSnapshotMeta,
    ConjunctionAssumptions,
    ConjunctionEvent,
    ManeuverPlan,
    ManeuverPlanEntry,
    ManeuverPlansArtifact,
    TrendMetrics,
    TrendSample,
    TopConjunctionsArtifact,
)
from packages.contracts.manifest import ArtifactEntry, ArtifactsLatest  # noqa: E402
from packages.contracts.versioning import ORBIT_MODEL_VERSION, SCHEMA_VERSION  # noqa: E402
from packages.orbit.conjunction import find_refined_conjunctions  # noqa: E402
from packages.orbit.load_catalog import load_latest_tles  # noqa: E402
from packages.orbit.propagate import propagate_positions  # noqa: E402
from packages.orbit.risk import pc_assumed_encounter_isotropic, sigma_pair_m  # noqa: E402
from packages.orbit.maneuver import ManeuverPolicy, plan_min_delta_v  # noqa: E402
from packages.orbit.spatial_hash import candidate_pairs_by_timestep  # noqa: E402
from packages.orbit.trend import TrendConfig, evaluate_trend_gate  # noqa: E402


DEFAULT_GROUPS = [
    "ACTIVE",
    "COSMOS-1408-DEBRIS",
    "FENGYUN-1C-DEBRIS",
    "IRIDIUM-33-DEBRIS",
    "COSMOS-2251-DEBRIS",
]


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


def _is_active_group(group: str) -> bool:
    return str(group).upper() == "ACTIVE"


def _is_debris_group(group: str) -> bool:
    return "DEBRIS" in str(group).upper()


def _is_active_vs_debris(primary_group: str, secondary_group: str) -> bool:
    p_active = _is_active_group(primary_group)
    s_active = _is_active_group(secondary_group)
    p_debris = _is_debris_group(primary_group)
    s_debris = _is_debris_group(secondary_group)
    return (p_active and s_active) or (p_active and s_debris) or (s_active and p_debris)


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


def _eci_to_ecef(positions_km: np.ndarray, times_utc: List[datetime]) -> np.ndarray:
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


def _nearest_time_index(target_utc: str, timeline_utc: List[str]) -> int:
    target = _parse_iso_utc(target_utc)
    if not timeline_utc:
        return 0
    best_idx = 0
    best_delta = None
    for idx, ts in enumerate(timeline_utc):
        delta = abs((_parse_iso_utc(ts) - target).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_idx = idx
    return best_idx


def _validate_event_links(events: List[ConjunctionEvent], snapshot: CesiumSnapshot) -> List[ConjunctionEvent]:
    if not events:
        return events
    norad_set = {obj.norad_id for obj in snapshot.objects}
    max_index = len(snapshot.times_utc) - 1
    kept: List[ConjunctionEvent] = []
    dropped = 0
    for event in events:
        if event.primary_id not in norad_set or event.secondary_id not in norad_set:
            dropped += 1
            continue
        if event.tca_index_snapshot < 0 or event.tca_index_snapshot > max_index:
            dropped += 1
            continue
        kept.append(event)
    if dropped:
        print(f"[WARN] Dropped {dropped} events with invalid snapshot links.")
    return kept


def _write_json(path: Path, payload: Dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_top_outputs(processed_dir: Path, events: List[ConjunctionEvent], generated_at_utc: str) -> Path:
    json_path = processed_dir / "top_conjunctions.json"
    csv_path = processed_dir / "top_conjunctions.csv"

    artifact = TopConjunctionsArtifact(
        generated_at_utc=generated_at_utc,
        event_count=len(events),
        events=events,
        model_version=ORBIT_MODEL_VERSION,
    )
    _write_json(json_path, artifact.to_dict())

    fieldnames = [
        "schema_version",
        "event_id",
        "primary_id",
        "secondary_id",
        "tca_utc",
        "tca_index_snapshot",
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
    return json_path


def _parse_float_list(value: str, default_values: List[float]) -> List[float]:
    raw = str(value or "").strip()
    if not raw:
        return list(default_values)
    out: List[float] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            out.append(float(token))
        except ValueError:
            continue
    return out or list(default_values)


def _build_snapshot(
    generated_at_utc: str,
    times_utc: List[datetime],
    positions_km: np.ndarray,
    valid_tles,
    dt_s: int,
    downsample_step: int,
) -> CesiumSnapshot:
    times_ds_dt = list(times_utc[::downsample_step])
    pos_ds_km = positions_km[::downsample_step, :, :]

    transformed_km = _eci_to_ecef(pos_ds_km, times_ds_dt)
    transformed_m = transformed_km * 1000.0

    objects: List[CesiumObject] = []
    object_count = int(transformed_m.shape[1]) if transformed_m.ndim == 3 else 0
    for idx in range(object_count):
        entry = CesiumObject(
            object_index=idx,
            norad_id=int(valid_tles[idx].norad_id),
            name=valid_tles[idx].name,
            source_group=str(valid_tles[idx].source_group).upper(),
            positions_ecef_m=transformed_m[:, idx, :].round(3).tolist(),
        )
        objects.append(entry)

    export_dt_s = int(dt_s) * int(downsample_step)
    snapshot = CesiumSnapshot(
        generated_at_utc=generated_at_utc,
        model_version=ORBIT_MODEL_VERSION,
        times_utc=[_iso_utc(ts) for ts in times_ds_dt],
        meta=CesiumSnapshotMeta(
            native_dt_s=int(dt_s),
            export_dt_s=export_dt_s,
            downsample_step=int(downsample_step),
        ),
        notes="Coordinates are ECEF meters for Cesium compatibility.",
        objects=objects,
    )
    return snapshot


def _balanced_snapshot_indices(
    valid_tles,
    seed: int,
    active_target: int,
    debris_target: int,
    max_total: int,
    required_norad_ids: Optional[set] = None,
) -> List[int]:
    required_norad_ids = required_norad_ids or set()
    active_indices: List[int] = []
    debris_indices: List[int] = []
    required_indices: List[int] = []

    for idx, tle in enumerate(valid_tles):
        group = str(tle.source_group).upper()
        is_active = group == "ACTIVE"
        if is_active:
            active_indices.append(idx)
        else:
            debris_indices.append(idx)
        if int(tle.norad_id) in required_norad_ids:
            required_indices.append(idx)

    required_set = set(required_indices)
    active_required = [i for i in required_indices if i in active_indices]
    debris_required = [i for i in required_indices if i in debris_indices]

    active_pool = [i for i in active_indices if i not in required_set]
    debris_pool = [i for i in debris_indices if i not in required_set]

    rng = np.random.default_rng(int(seed))

    active_take = max(0, min(int(active_target) - len(active_required), len(active_pool)))
    debris_take = max(0, min(int(debris_target) - len(debris_required), len(debris_pool)))

    sampled_active = (
        rng.choice(active_pool, size=active_take, replace=False).tolist()
        if active_take > 0
        else []
    )
    sampled_debris = (
        rng.choice(debris_pool, size=debris_take, replace=False).tolist()
        if debris_take > 0
        else []
    )

    combined = required_indices + sampled_active + sampled_debris

    if max_total and len(combined) > int(max_total):
        if len(required_indices) > int(max_total):
            print(
                "[WARN] snapshot-max is smaller than required event objects; "
                "expanding snapshot to include required ids."
            )
            max_total = len(required_indices)
        remaining_slots = int(max_total) - len(required_indices)
        extra_pool = [i for i in combined if i not in required_set]
        rng.shuffle(extra_pool)
        combined = required_indices + extra_pool[: max(0, remaining_slots)]

    rng.shuffle(combined)
    return combined


def _write_snapshot(processed_dir: Path, snapshot: CesiumSnapshot) -> Path:
    snapshot_path = processed_dir / "cesium_orbits_snapshot.json"
    _write_json(snapshot_path, snapshot.to_dict())
    print(f"[INFO] Wrote {snapshot_path}")
    return snapshot_path


def _write_maneuver_plans_output(
    processed_dir: Path,
    generated_at_utc: str,
    entries: Dict[str, ManeuverPlanEntry],
) -> Path:
    plans_path = processed_dir / "maneuver_plans.json"
    artifact = ManeuverPlansArtifact(
        generated_at_utc=generated_at_utc,
        event_count=len(entries),
        plans_by_event_id=entries,
        model_version=ORBIT_MODEL_VERSION,
    )
    _write_json(plans_path, artifact.to_dict())
    print(f"[INFO] Wrote {plans_path}")
    return plans_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _build_artifact_entry(path: Path, model_version: str, generated_at_utc: str) -> ArtifactEntry:
    rel_path = str(path.relative_to(REPO_ROOT))
    return ArtifactEntry(
        path=rel_path,
        schema_version=SCHEMA_VERSION,
        model_version=model_version,
        sha256=_sha256_file(path),
        generated_at_utc=generated_at_utc,
    )


def _write_artifacts_latest(
    processed_dir: Path,
    generated_at_utc: str,
    top_conjunctions_path: Path,
    cesium_snapshot_path: Path,
    maneuver_plans_path: Optional[Path] = None,
    latest_run_id: Optional[str] = None,
) -> Path:
    manifest_path = processed_dir / "artifacts_latest.json"
    artifacts = {
        "top_conjunctions": _build_artifact_entry(
            top_conjunctions_path,
            ORBIT_MODEL_VERSION,
            generated_at_utc,
        ),
        "cesium_snapshot": _build_artifact_entry(
            cesium_snapshot_path,
            ORBIT_MODEL_VERSION,
            generated_at_utc,
        ),
    }
    if maneuver_plans_path is not None:
        artifacts["maneuver_plans"] = _build_artifact_entry(
            maneuver_plans_path,
            ORBIT_MODEL_VERSION,
            generated_at_utc,
        )
    manifest = ArtifactsLatest(
        generated_at_utc=generated_at_utc,
        latest_run_id=latest_run_id,
        artifacts=artifacts,
    )
    _write_json(manifest_path, manifest.to_dict())
    print(f"[INFO] Wrote {manifest_path}")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 72h conjunction screening with assumed-covariance Pc.")
    parser.add_argument("--db", default="data/processed/tles.sqlite")
    parser.add_argument("--start-utc", type=str, default=None)
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
    parser.add_argument("--snapshot-downsample", type=int, default=3)
    parser.add_argument("--snapshot-balanced", dest="snapshot_balanced", action="store_true", default=True)
    parser.add_argument("--no-snapshot-balanced", dest="snapshot_balanced", action="store_false")
    parser.add_argument("--snapshot-active", type=int, default=1000)
    parser.add_argument("--snapshot-debris", type=int, default=1000)
    parser.add_argument("--snapshot-max", type=int, default=2000)
    parser.add_argument("--trend-window-minutes", type=int, default=int(os.environ.get("ASTRA_TREND_WINDOW_MINUTES", "30")))
    parser.add_argument("--trend-cadence-seconds", type=int, default=int(os.environ.get("ASTRA_TREND_CADENCE_SECONDS", "60")))
    parser.add_argument("--trend-threshold", type=float, default=float(os.environ.get("ASTRA_TREND_THRESHOLD", "1e-5")))
    parser.add_argument("--trend-defer-hours", type=float, default=float(os.environ.get("ASTRA_TREND_DEFER_HOURS", "24")))
    parser.add_argument("--trend-critical-override", type=float, default=float(os.environ.get("ASTRA_TREND_CRITICAL_OVERRIDE", "1e-3")))
    parser.add_argument("--cov-model", type=str, default=os.environ.get("ASTRA_COV_MODEL", "anisotropic_rtn"))
    parser.add_argument("--sigma-base-payload-r-m", type=float, default=float(os.environ.get("ASTRA_SIGMA_BASE_PAYLOAD_R_M", "200")))
    parser.add_argument("--sigma-base-payload-t-m", type=float, default=float(os.environ.get("ASTRA_SIGMA_BASE_PAYLOAD_T_M", "260")))
    parser.add_argument("--sigma-base-payload-n-m", type=float, default=float(os.environ.get("ASTRA_SIGMA_BASE_PAYLOAD_N_M", "200")))
    parser.add_argument("--sigma-base-debris-r-m", type=float, default=float(os.environ.get("ASTRA_SIGMA_BASE_DEBRIS_R_M", "500")))
    parser.add_argument("--sigma-base-debris-t-m", type=float, default=float(os.environ.get("ASTRA_SIGMA_BASE_DEBRIS_T_M", "700")))
    parser.add_argument("--sigma-base-debris-n-m", type=float, default=float(os.environ.get("ASTRA_SIGMA_BASE_DEBRIS_N_M", "500")))
    parser.add_argument("--sigma-t-growth-mps", type=float, default=float(os.environ.get("ASTRA_SIGMA_T_GROWTH_MPS", "0.02")))
    parser.add_argument("--max-delta-v-mps", type=float, default=float(os.environ.get("ASTRA_MAX_DELTA_V_MPS", "0.5")))
    parser.add_argument("--candidate-burn-offsets-h", type=str, default=os.environ.get("ASTRA_CANDIDATE_BURN_OFFSETS_H", "24,12,6,2"))
    parser.add_argument("--late-burn-minutes", type=float, default=float(os.environ.get("ASTRA_LATE_BURN_MINUTES", "30")))
    parser.add_argument("--miss-distance-target-m", type=float, default=float(os.environ.get("ASTRA_MISS_DISTANCE_TARGET_M", "1000")))
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

    run_started = _parse_iso_utc(args.start_utc) if args.start_utc else datetime.now(timezone.utc)
    generated_at_utc = _iso_utc(run_started)
    print(f"[INFO] Step 2 screening start: {generated_at_utc}")
    print(f"[INFO] Schema version: {SCHEMA_VERSION}")
    print(f"[INFO] Model version: {ORBIT_MODEL_VERSION}")
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

    downsample_step = max(1, int(args.snapshot_downsample))
    snapshot_times_utc = [_iso_utc(ts) for ts in list(times_utc)[::downsample_step]]

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

    assumptions_base = ConjunctionAssumptions(
        dt_s=int(args.dt),
        dt_refine_s=int(args.dt_refine),
        horizon_hours=float(args.horizon_hours),
        hard_body_radius_m=float(args.hbr_m),
        sigma_payload_m=float(args.sigma_payload_m),
        sigma_debris_m=float(args.sigma_debris_m),
        voxel_km=float(args.voxel_km),
        catalog_groups_used=groups,
    )

    stage_start = time.time()
    events: List[ConjunctionEvent] = []
    event_groups: Dict[str, tuple[str, str]] = {}
    filtered_disallowed_pairs = 0
    for row in refined:
        primary_id = int(row["primary_id"])
        secondary_id = int(row["secondary_id"])
        primary_group = str(row["primary_group"]).upper()
        secondary_group = str(row["secondary_group"]).upper()

        if not _is_active_vs_debris(primary_group, secondary_group):
            filtered_disallowed_pairs += 1
            continue

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

        tca_utc = str(row["tca_utc"])
        tca_idx = _nearest_time_index(tca_utc, snapshot_times_utc)

        event = ConjunctionEvent(
            event_id=f"EVT-{primary_id}-{secondary_id}-{tca_utc}",
            primary_id=primary_id,
            secondary_id=secondary_id,
            tca_utc=tca_utc,
            tca_index_snapshot=tca_idx,
            miss_distance_m=miss_distance_m,
            relative_speed_mps=float(row["relative_speed_mps"]),
            pc_assumed=float(pc),
            risk_score=float(risk_score),
            window_start_utc=str(row["window_start_utc"]),
            window_end_utc=str(row["window_end_utc"]),
            model_version=ORBIT_MODEL_VERSION,
            assumptions=assumptions_base.__dict__,
        )
        events.append(event)
        event_groups[event.event_id] = (primary_group, secondary_group)

    events.sort(key=lambda e: (-e.risk_score, e.miss_distance_m))
    top_events = events[: max(0, int(args.top_k))]
    if filtered_disallowed_pairs:
        print(
            "[INFO] Filtered conjunctions (disallowed pair types): "
            f"{filtered_disallowed_pairs}"
        )
    print(f"[INFO] Stage risk_scoring took {time.time() - stage_start:.2f}s")

    required_norads = {e.primary_id for e in top_events} | {e.secondary_id for e in top_events}
    snapshot_valid_tles = valid_tles
    snapshot_positions_km = positions_km
    if args.snapshot_balanced:
        selected_idx = _balanced_snapshot_indices(
            valid_tles=valid_tles,
            seed=args.seed,
            active_target=args.snapshot_active,
            debris_target=args.snapshot_debris,
            max_total=args.snapshot_max,
            required_norad_ids=required_norads,
        )
        snapshot_valid_tles = [valid_tles[i] for i in selected_idx]
        snapshot_positions_km = positions_km[:, selected_idx, :]
        active_count = sum(1 for tle in snapshot_valid_tles if str(tle.source_group).upper() == "ACTIVE")
        debris_count = len(snapshot_valid_tles) - active_count
        print(
            "[INFO] Snapshot composition: "
            f"ACTIVE={active_count}, DEBRIS={debris_count}, TOTAL={len(snapshot_valid_tles)} (balanced)"
        )
    else:
        print(f"[INFO] Snapshot composition: TOTAL={len(snapshot_valid_tles)} (unbalanced)")

    stage_start = time.time()
    snapshot = _build_snapshot(
        generated_at_utc=generated_at_utc,
        times_utc=times_utc,
        positions_km=snapshot_positions_km,
        valid_tles=snapshot_valid_tles,
        dt_s=args.dt,
        downsample_step=downsample_step,
    )
    events = _validate_event_links(events, snapshot)
    top_events = events[: max(0, int(args.top_k))]
    cesium_snapshot_path = _write_snapshot(processed_dir, snapshot)
    print(f"[INFO] Stage build_snapshot took {time.time() - stage_start:.2f}s")

    stage_start = time.time()
    tle_by_norad = {int(tle.norad_id): tle for tle in valid_tles}
    candidate_offsets_h = _parse_float_list(args.candidate_burn_offsets_h, [24.0, 12.0, 6.0, 2.0])
    trend_cfg = TrendConfig(
        window_minutes=max(1, int(args.trend_window_minutes)),
        cadence_seconds=max(1, int(args.trend_cadence_seconds)),
        threshold=max(0.0, float(args.trend_threshold)),
        defer_hours=max(0.0, float(args.trend_defer_hours)),
        critical_override=max(0.0, float(args.trend_critical_override)),
        hard_body_radius_m=max(0.0, float(args.hbr_m)),
        cov_model=str(args.cov_model),
        sigma_payload_m=float(args.sigma_payload_m),
        sigma_debris_m=float(args.sigma_debris_m),
        payload_base_r_m=float(args.sigma_base_payload_r_m),
        payload_base_t_m=float(args.sigma_base_payload_t_m),
        payload_base_n_m=float(args.sigma_base_payload_n_m),
        debris_base_r_m=float(args.sigma_base_debris_r_m),
        debris_base_t_m=float(args.sigma_base_debris_t_m),
        debris_base_n_m=float(args.sigma_base_debris_n_m),
        sigma_t_growth_mps=float(args.sigma_t_growth_mps),
    )
    maneuver_target_m = max(float(args.miss_distance_target_m), 3.0 * float(args.hbr_m), 1000.0)
    maneuver_policy = ManeuverPolicy(
        miss_distance_target_m=maneuver_target_m,
        max_delta_v_mps=float(args.max_delta_v_mps),
        candidate_offsets_h=candidate_offsets_h,
        late_burn_minutes=float(args.late_burn_minutes),
    )
    plans_entries: Dict[str, ManeuverPlanEntry] = {}
    for event in top_events:
        event_dict = event.to_dict()
        groups = event_groups.get(event.event_id, ("UNKNOWN", "UNKNOWN"))
        primary_tle = tle_by_norad.get(int(event.primary_id))
        secondary_tle = tle_by_norad.get(int(event.secondary_id))

        if primary_tle is not None and secondary_tle is not None:
            trend_eval = evaluate_trend_gate(
                event=event_dict,
                primary_line1=primary_tle.line1,
                primary_line2=primary_tle.line2,
                secondary_line1=secondary_tle.line1,
                secondary_line2=secondary_tle.line2,
                primary_group=groups[0],
                secondary_group=groups[1],
                config=trend_cfg,
                now_utc=run_started,
            )
        else:
            fallback_pc = float(event.pc_assumed)
            trend_eval = {
                "pc_series": [{"t_utc": event.tca_utc, "miss_m": float(event.miss_distance_m), "pc": fallback_pc}],
                "trend_metrics": {
                    "pc_peak": fallback_pc,
                    "pc_slope": 0.0,
                    "pc_stability": 1.0 if fallback_pc > 0 else 0.0,
                    "window_minutes": int(trend_cfg.window_minutes),
                    "cadence_seconds": int(trend_cfg.cadence_seconds),
                    "sample_count": 1,
                    "time_to_tca_hours": float((_parse_iso_utc(event.tca_utc) - run_started).total_seconds() / 3600.0),
                    "threshold": float(trend_cfg.threshold),
                    "critical_override": float(trend_cfg.critical_override),
                    "gate_decision": "IGNORE",
                    "gate_reason_code": "MISSING_TLE",
                    "gate_reason": "Unable to compute local trend due to missing TLE pair.",
                },
                "decision_mode_hint": "IGNORE",
                "defer_until_utc": None,
                "gate_reason_code": "MISSING_TLE",
                "gate_reason": "Unable to compute local trend due to missing TLE pair.",
            }

        selected_plan: Optional[ManeuverPlan] = None
        if trend_eval["decision_mode_hint"] == "MANEUVER":
            planned = plan_min_delta_v(event=event_dict, policy=maneuver_policy, now_utc=run_started)
            if planned.get("burn_time_utc") is not None and planned.get("direction") is not None and planned.get("delta_v_mps") is not None:
                selected_plan = ManeuverPlan(
                    burn_time_utc=str(planned["burn_time_utc"]),
                    frame="RTN",
                    direction=str(planned["direction"]),
                    delta_v_mps=float(planned["delta_v_mps"]),
                    expected_miss_m=float(planned["expected_miss_m"]),
                    feasibility=str(planned["feasibility"]),
                    early_vs_late_ratio=planned.get("early_vs_late_ratio"),
                    notes=str(planned["notes"]),
                )
            else:
                selected_plan = ManeuverPlan(
                    burn_time_utc="",
                    frame="RTN",
                    direction="",
                    delta_v_mps=0.0,
                    expected_miss_m=float(planned["expected_miss_m"]),
                    feasibility=str(planned["feasibility"]),
                    early_vs_late_ratio=planned.get("early_vs_late_ratio"),
                    notes=str(planned["notes"]),
                )

        metrics = trend_eval["trend_metrics"]
        plans_entries[event.event_id] = ManeuverPlanEntry(
            event_id=event.event_id,
            trend_metrics=TrendMetrics(
                pc_peak=float(metrics.get("pc_peak", 0.0)),
                pc_slope=float(metrics.get("pc_slope", 0.0)),
                pc_stability=float(metrics.get("pc_stability", 0.0)),
                window_minutes=int(metrics.get("window_minutes", trend_cfg.window_minutes)),
                cadence_seconds=int(metrics.get("cadence_seconds", trend_cfg.cadence_seconds)),
                sample_count=int(metrics.get("sample_count", 0)),
                time_to_tca_hours=float(metrics.get("time_to_tca_hours", 0.0)),
                threshold=float(metrics.get("threshold", trend_cfg.threshold)),
                critical_override=float(metrics.get("critical_override", trend_cfg.critical_override)),
                gate_decision=str(metrics.get("gate_decision", trend_eval["decision_mode_hint"])),
                gate_reason_code=str(metrics.get("gate_reason_code", trend_eval["gate_reason_code"])),
                gate_reason=str(metrics.get("gate_reason", trend_eval["gate_reason"])),
            ),
            pc_series=[
                TrendSample(
                    t_utc=str(item.get("t_utc", event.tca_utc)),
                    miss_m=float(item.get("miss_m", event.miss_distance_m)),
                    pc=float(item.get("pc", event.pc_assumed)),
                )
                for item in trend_eval["pc_series"]
            ],
            decision_mode_hint=str(trend_eval["decision_mode_hint"]),
            defer_until_utc=trend_eval.get("defer_until_utc"),
            maneuver_plan=selected_plan,
        )
    maneuver_plans_path = _write_maneuver_plans_output(processed_dir, generated_at_utc, plans_entries)
    print(f"[INFO] Stage trend_and_plans took {time.time() - stage_start:.2f}s")

    top_conjunctions_path = _write_top_outputs(processed_dir, top_events, generated_at_utc)
    _write_artifacts_latest(
        processed_dir=processed_dir,
        generated_at_utc=generated_at_utc,
        top_conjunctions_path=top_conjunctions_path,
        cesium_snapshot_path=cesium_snapshot_path,
        maneuver_plans_path=maneuver_plans_path,
        latest_run_id=None,
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
