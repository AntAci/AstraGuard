#!/usr/bin/env python3
"""Run Step 2 conjunction screening and write ranked risk outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
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
    TopConjunctionsArtifact,
)
from packages.contracts.manifest import ArtifactEntry, ArtifactsLatest  # noqa: E402
from packages.contracts.versioning import ORBIT_MODEL_VERSION, SCHEMA_VERSION  # noqa: E402
from packages.orbit.conjunction import find_refined_conjunctions  # noqa: E402
from packages.orbit.load_catalog import load_latest_tles  # noqa: E402
from packages.orbit.propagate import propagate_positions  # noqa: E402
from packages.orbit.risk import pc_assumed_encounter_isotropic, sigma_pair_m  # noqa: E402
from packages.orbit.spatial_hash import candidate_pairs_by_timestep  # noqa: E402


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


def _write_snapshot(processed_dir: Path, snapshot: CesiumSnapshot) -> Path:
    snapshot_path = processed_dir / "cesium_orbits_snapshot.json"
    _write_json(snapshot_path, snapshot.to_dict())
    print(f"[INFO] Wrote {snapshot_path}")
    return snapshot_path


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
    latest_run_id: Optional[str] = None,
) -> Path:
    manifest_path = processed_dir / "artifacts_latest.json"
    manifest = ArtifactsLatest(
        generated_at_utc=generated_at_utc,
        latest_run_id=latest_run_id,
        artifacts={
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
        },
    )
    _write_json(manifest_path, manifest.to_dict())
    print(f"[INFO] Wrote {manifest_path}")
    return manifest_path


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
    parser.add_argument("--snapshot-downsample", type=int, default=3)
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

    stage_start = time.time()
    snapshot = _build_snapshot(
        generated_at_utc=generated_at_utc,
        times_utc=times_utc,
        positions_km=positions_km,
        valid_tles=valid_tles,
        dt_s=args.dt,
        downsample_step=max(1, int(args.snapshot_downsample)),
    )
    cesium_snapshot_path = _write_snapshot(processed_dir, snapshot)
    print(f"[INFO] Stage build_snapshot took {time.time() - stage_start:.2f}s")

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

        tca_utc = str(row["tca_utc"])
        tca_idx = _nearest_time_index(tca_utc, snapshot.times_utc)

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

    events.sort(key=lambda e: (-e.risk_score, e.miss_distance_m))
    events = _validate_event_links(events, snapshot)
    top_events = events[: max(0, int(args.top_k))]
    print(f"[INFO] Stage risk_scoring took {time.time() - stage_start:.2f}s")

    top_conjunctions_path = _write_top_outputs(processed_dir, top_events, generated_at_utc)
    _write_artifacts_latest(
        processed_dir=processed_dir,
        generated_at_utc=generated_at_utc,
        top_conjunctions_path=top_conjunctions_path,
        cesium_snapshot_path=cesium_snapshot_path,
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
