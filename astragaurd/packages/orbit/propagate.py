#!/usr/bin/env python3
"""Propagate TLE catalog positions with SGP4."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Sequence, Tuple

import numpy as np
from sgp4.api import Satrec, jday

from packages.orbit.load_catalog import TLE


def _to_utc_datetime(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_times(start_utc: datetime, horizon_hours: float, dt_s: int) -> List[datetime]:
    total_seconds = int(round(float(horizon_hours) * 3600.0))
    if dt_s <= 0:
        raise ValueError("dt_s must be > 0")
    steps = total_seconds // int(dt_s)
    times = [start_utc + timedelta(seconds=i * int(dt_s)) for i in range(steps + 1)]
    if times[-1] < start_utc + timedelta(seconds=total_seconds):
        times.append(start_utc + timedelta(seconds=total_seconds))
    return times


def propagate_positions(
    tles: Sequence[TLE],
    start_utc,
    horizon_hours=72,
    dt_s=600,
):
    start_dt = _to_utc_datetime(start_utc)
    times_utc = _build_times(start_dt, float(horizon_hours), int(dt_s))

    jd_fr: List[Tuple[float, float]] = []
    for dt in times_utc:
        jd, fr = jday(
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second + dt.microsecond / 1_000_000.0,
        )
        jd_fr.append((jd, fr))

    requested = len(tles)
    kept_tles: List[TLE] = []
    norad_ids: List[int] = []
    per_object_positions: List[np.ndarray] = []
    skipped = 0

    for tle in tles:
        try:
            sat = Satrec.twoline2rv(tle.line1, tle.line2)
        except Exception as exc:
            skipped += 1
            print(f"[WARN] Failed parsing TLE for NORAD {tle.norad_id}: {exc}")
            continue

        coords = np.empty((len(times_utc), 3), dtype=np.float64)
        valid = True
        for idx, (jd, fr) in enumerate(jd_fr):
            err, r, _ = sat.sgp4(jd, fr)
            if err != 0:
                valid = False
                break
            coords[idx, :] = r
            if not np.all(np.isfinite(coords[idx, :])):
                valid = False
                break

        if not valid:
            skipped += 1
            continue

        kept_tles.append(tle)
        norad_ids.append(int(tle.norad_id))
        per_object_positions.append(coords)

    if per_object_positions:
        positions_km = np.stack(per_object_positions, axis=1)
    else:
        positions_km = np.empty((len(times_utc), 0, 3), dtype=np.float64)

    print(
        "[INFO] Propagation complete: "
        f"requested={requested}, kept={len(kept_tles)}, skipped={skipped}, "
        f"timesteps={len(times_utc)}"
    )

    return times_utc, positions_km, norad_ids, kept_tles
