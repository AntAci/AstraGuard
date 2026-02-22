#!/usr/bin/env python3
"""Load TLE catalog rows from SQLite with group normalization and dedupe."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


@dataclass
class TLE:
    norad_id: int
    name: str
    epoch_utc: str
    line1: str
    line2: str
    source_group: str
    fetched_at_utc: str


def _normalize_groups(groups: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for group in groups:
        value = (group or "").strip().upper()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _rows_to_tles(rows: List[Tuple]) -> List[TLE]:
    tles: List[TLE] = []
    for row in rows:
        tles.append(
            TLE(
                norad_id=int(row[0]),
                name=str(row[1]),
                epoch_utc=str(row[2]),
                line1=str(row[3]),
                line2=str(row[4]),
                source_group=str(row[5]).upper(),
                fetched_at_utc=str(row[6]),
            )
        )
    return tles


def load_latest_tles(
    db_path,
    groups,
    max_objects,
    prefer_latest_fetch=True,
    dedupe_by_norad=True,
) -> List[TLE]:
    db_path = Path(db_path)
    normalized_groups = _normalize_groups(groups)
    if not normalized_groups:
        print("[ERROR] No groups provided after normalization.")
        return []

    if max_objects <= 0:
        print("[WARN] max_objects <= 0 provided; returning empty catalog.")
        return []

    placeholders = ",".join(["?"] * len(normalized_groups))
    base_cte = (
        "WITH filtered AS ("
        " SELECT norad_id, name, epoch_utc, line1, line2, UPPER(source_group) AS source_group, fetched_at_utc"
        " FROM tles"
        " WHERE UPPER(source_group) IN ({})"
        ")"
    ).format(placeholders)

    if prefer_latest_fetch:
        sql = (
            base_cte
            + ", latest_fetch AS ("
            " SELECT source_group, MAX(fetched_at_utc) AS max_fetched_at_utc"
            " FROM filtered GROUP BY source_group"
            ")"
            " SELECT f.norad_id, f.name, f.epoch_utc, f.line1, f.line2, f.source_group, f.fetched_at_utc"
            " FROM filtered f"
            " JOIN latest_fetch lf"
            "   ON f.source_group = lf.source_group"
            "  AND f.fetched_at_utc = lf.max_fetched_at_utc"
        )
    else:
        sql = (
            base_cte
            + " SELECT norad_id, name, epoch_utc, line1, line2, source_group, fetched_at_utc"
            " FROM filtered"
        )

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(sql, normalized_groups).fetchall()
    finally:
        conn.close()

    raw_tles = _rows_to_tles(rows)
    pre_dedupe_count = len(raw_tles)

    if dedupe_by_norad:
        best_by_norad: Dict[int, TLE] = {}
        for tle in raw_tles:
            current = best_by_norad.get(tle.norad_id)
            if current is None:
                best_by_norad[tle.norad_id] = tle
                continue
            if (tle.epoch_utc, tle.fetched_at_utc) > (current.epoch_utc, current.fetched_at_utc):
                best_by_norad[tle.norad_id] = tle
        deduped_tles = list(best_by_norad.values())
    else:
        deduped_tles = list(raw_tles)

    duplicates_removed = pre_dedupe_count - len(deduped_tles)

    # Stable deterministic ordering for repeatable runs.
    deduped_tles.sort(key=lambda x: (x.norad_id, x.epoch_utc), reverse=False)

    selected = deduped_tles[: int(max_objects)]

    group_counts: Dict[str, int] = {}
    for tle in selected:
        group_counts[tle.source_group] = group_counts.get(tle.source_group, 0) + 1

    print(f"[INFO] Catalog load from {db_path}: rows={pre_dedupe_count}, selected={len(selected)}")
    print(f"[INFO] Groups requested (normalized): {normalized_groups}")
    print(f"[INFO] Duplicates removed by norad_id: {duplicates_removed}")
    if group_counts:
        for group in sorted(group_counts.keys()):
            print(f"[INFO] Group {group}: {group_counts[group]} objects")
    else:
        print("[WARN] No catalog rows selected after filtering.")

    return selected
