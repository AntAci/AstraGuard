#!/usr/bin/env python3
"""Conjunction coarse screening and local TCA refinement."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from sgp4.api import Satrec, jday

from packages.orbit.load_catalog import TLE


def _to_iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _propagate_sat(sat: Satrec, times_utc: Sequence[datetime]):
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


def _relative_speed_mps(rel_km: np.ndarray, idx: int, dt_s: int) -> float:
    rel_m = rel_km * 1000.0
    n = rel_m.shape[0]
    if n < 2:
        return 0.0
    if 0 < idx < n - 1:
        delta = rel_m[idx + 1] - rel_m[idx - 1]
        return float(np.linalg.norm(delta) / (2.0 * float(dt_s)))
    if idx == 0:
        delta = rel_m[1] - rel_m[0]
        return float(np.linalg.norm(delta) / float(dt_s))
    delta = rel_m[n - 1] - rel_m[n - 2]
    return float(np.linalg.norm(delta) / float(dt_s))


def find_refined_conjunctions(
    valid_tles: Sequence[TLE],
    norad_ids: Sequence[int],
    times_utc: Sequence[datetime],
    positions_km: np.ndarray,
    candidate_stream: Iterable[Tuple[int, List[Tuple[int, int]]]],
    dt_s,
    dt_refine_s,
    refine_half_window_steps=2,
):
    best_by_pair: Dict[Tuple[int, int], Tuple[float, int]] = {}

    for t_idx, pairs in candidate_stream:
        if not pairs:
            continue
        arr = np.array(pairs, dtype=np.int64)
        if arr.size == 0:
            continue
        diffs = positions_km[t_idx, arr[:, 0], :] - positions_km[t_idx, arr[:, 1], :]
        dists_m = np.linalg.norm(diffs, axis=1) * 1000.0
        for idx in range(arr.shape[0]):
            pair = (int(arr[idx, 0]), int(arr[idx, 1]))
            dist_m = float(dists_m[idx])
            prev = best_by_pair.get(pair)
            if prev is None or dist_m < prev[0]:
                best_by_pair[pair] = (dist_m, int(t_idx))

    print(f"[INFO] Unique candidate pairs selected for refinement: {len(best_by_pair)}")

    sat_cache: Dict[int, Satrec] = {}
    for idx, tle in enumerate(valid_tles):
        try:
            sat_cache[idx] = Satrec.twoline2rv(tle.line1, tle.line2)
        except Exception:
            continue

    refined_events: List[dict] = []
    refine_failures = 0

    time_count = len(times_utc)
    for (i, j), (_, coarse_idx) in best_by_pair.items():
        sat_i = sat_cache.get(i)
        sat_j = sat_cache.get(j)
        if sat_i is None or sat_j is None:
            refine_failures += 1
            continue

        i0 = max(0, coarse_idx - int(refine_half_window_steps))
        i1 = min(time_count - 1, coarse_idx + int(refine_half_window_steps))
        t_start = times_utc[i0]
        t_end = times_utc[i1]

        refine_times: List[datetime] = []
        cursor = t_start
        while cursor <= t_end:
            refine_times.append(cursor)
            cursor = cursor + timedelta(seconds=int(dt_refine_s))
        if refine_times[-1] < t_end:
            refine_times.append(t_end)

        pos_i = _propagate_sat(sat_i, refine_times)
        pos_j = _propagate_sat(sat_j, refine_times)
        if pos_i is None or pos_j is None:
            refine_failures += 1
            continue

        rel_km = pos_i - pos_j
        dists_m = np.linalg.norm(rel_km, axis=1) * 1000.0
        min_idx = int(np.argmin(dists_m))

        tca = refine_times[min_idx]
        miss_distance_m = float(dists_m[min_idx])
        relative_speed_mps = _relative_speed_mps(rel_km, min_idx, int(dt_refine_s))

        primary_id = int(norad_ids[i])
        secondary_id = int(norad_ids[j])
        primary_group = str(valid_tles[i].source_group).upper()
        secondary_group = str(valid_tles[j].source_group).upper()

        refined_events.append(
            {
                "primary_id": primary_id,
                "secondary_id": secondary_id,
                "tca_utc": _to_iso_utc(tca),
                "miss_distance_m": miss_distance_m,
                "relative_speed_mps": relative_speed_mps,
                "primary_group": primary_group,
                "secondary_group": secondary_group,
                "window_start_utc": _to_iso_utc(t_start),
                "window_end_utc": _to_iso_utc(t_end),
            }
        )

    if refine_failures > 0:
        print(f"[WARN] Refinement propagation failures dropped: {refine_failures}")
    print(f"[INFO] Refined conjunction events produced: {len(refined_events)}")

    return refined_events
