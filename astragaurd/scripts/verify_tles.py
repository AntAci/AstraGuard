#!/usr/bin/env python3
"""Simple verification helper for ingested TLE data."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = repo_root / "data" / "processed" / "tles.sqlite"

    if not db_path.exists():
        print(f"[ERROR] SQLite database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM tles").fetchone()[0]
    except sqlite3.Error as exc:
        print(f"[ERROR] Unable to query table 'tles': {exc}")
        conn.close()
        return 1

    print(f"[INFO] DB: data/processed/tles.sqlite")
    print(f"[INFO] Total rows: {total}")

    rows = conn.execute(
        "SELECT source_group, COUNT(*) FROM tles GROUP BY source_group ORDER BY source_group"
    ).fetchall()
    print("[INFO] Count by source_group:")
    if rows:
        for source_group, count in rows:
            print(f"  - {source_group}: {count}")
    else:
        print("  - (no rows)")

    sample = conn.execute(
        """
        SELECT norad_id, name, epoch_utc, source_group, fetched_at_utc
        FROM tles
        ORDER BY fetched_at_utc DESC, norad_id ASC
        LIMIT 1
        """
    ).fetchone()
    if sample:
        norad_id, name, epoch_utc, source_group, fetched_at_utc = sample
        print("[INFO] Sample row:")
        print(f"  - norad_id: {norad_id}")
        print(f"  - name: {name}")
        print(f"  - epoch_utc: {epoch_utc}")
        print(f"  - source_group: {source_group}")
        print(f"  - fetched_at_utc: {fetched_at_utc}")
    else:
        print("[INFO] Sample row: (no rows)")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
