#!/usr/bin/env python3
"""Fetch CelesTrak TLE data, persist raw files, parse, and upsert into SQLite."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

import requests


DEFAULT_GROUPS = (
    "ACTIVE",
    "COSMOS-1408-DEBRIS",
    "FENGYUN-1C-DEBRIS",
    "IRIDIUM-33-DEBRIS",
    "COSMOS-2251-DEBRIS",
)
URL_TEMPLATE = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class GroupResult:
    group: str
    raw_file_rel: str | None
    parsed_records: int
    sqlite_upserts: int
    skipped_malformed: int
    skipped_no_data: bool
    fetch_ok: bool


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_iso_utc_seconds(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_iso_utc_micros(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def file_timestamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_tle_epoch_to_utc(epoch_field: str) -> str:
    """Convert TLE epoch (YYDDD.DDDDDDDD) to ISO UTC string."""
    value = epoch_field.strip()
    if len(value) < 5:
        raise ValueError("epoch too short")

    year_two = int(value[0:2])
    day_of_year = float(value[2:])
    year = 1900 + year_two if year_two >= 57 else 2000 + year_two

    day_whole = int(day_of_year)
    day_fraction = day_of_year - day_whole

    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    dt = start + timedelta(days=day_whole - 1, seconds=day_fraction * 86400)
    return format_iso_utc_micros(dt)


def non_empty_lines(text: str) -> Iterable[str]:
    for raw in text.splitlines():
        line = raw.rstrip("\n").rstrip("\r")
        if line.strip():
            yield line


def parse_tle_text(text: str, source_group: str, fetched_at_utc: str) -> tuple[list[tuple], int]:
    lines = list(non_empty_lines(text))
    parsed: list[tuple] = []
    skipped = 0

    for idx in range(0, len(lines), 3):
        chunk = lines[idx : idx + 3]
        if len(chunk) < 3:
            skipped += 1
            continue

        name, line1, line2 = chunk
        try:
            if not line1.startswith("1 ") or not line2.startswith("2 "):
                raise ValueError("line prefix mismatch")
            norad_id = int(line1[2:7])
            epoch_utc = parse_tle_epoch_to_utc(line1[18:32])
        except Exception:
            skipped += 1
            continue

        parsed.append(
            (
                norad_id,
                name.strip(),
                epoch_utc,
                line1.rstrip(),
                line2.rstrip(),
                source_group,
                fetched_at_utc,
            )
        )

    return parsed, skipped


def parse_groups_arg(values: Sequence[str] | None) -> list[str]:
    if not values:
        return list(DEFAULT_GROUPS)
    parts: list[str] = []
    for value in values:
        parts.extend(token.strip() for token in value.split(","))
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        group = part.upper()
        if group in seen:
            continue
        normalized.append(group)
        seen.add(group)
    return normalized or list(DEFAULT_GROUPS)


def response_is_no_data(text: str) -> bool:
    lowered = text.lower()
    if "no gp data found" in lowered:
        return True
    if len(text.strip()) < 80:
        return True
    if sum(1 for _ in non_empty_lines(text)) < 3:
        return True
    return False


def ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tles (
            norad_id INTEGER,
            name TEXT,
            epoch_utc TEXT,
            line1 TEXT,
            line2 TEXT,
            source_group TEXT,
            fetched_at_utc TEXT,
            PRIMARY KEY (norad_id, epoch_utc, source_group)
        )
        """
    )


def upsert_tles(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO tles (
            norad_id, name, epoch_utc, line1, line2, source_group, fetched_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(norad_id, epoch_utc, source_group) DO UPDATE SET
            name = excluded.name,
            line1 = excluded.line1,
            line2 = excluded.line2,
            fetched_at_utc = excluded.fetched_at_utc
        """,
        rows,
    )
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and ingest CelesTrak TLE groups.")
    parser.add_argument(
        "--groups",
        nargs="*",
        help="Groups to fetch (space or comma separated, case-insensitive).",
    )
    args = parser.parse_args()
    groups = parse_groups_arg(args.groups)

    repo_root = Path(__file__).resolve().parents[1]
    raw_dir = repo_root / "data" / "raw"
    processed_dir = repo_root / "data" / "processed"
    sqlite_path = processed_dir / "tles.sqlite"
    manifest_path = processed_dir / "tle_manifest_latest.json"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    run_started = utc_now()
    run_stamp = file_timestamp(run_started)
    fetched_at_utc = format_iso_utc_seconds(run_started)

    print(f"[INFO] Starting TLE ingest at {fetched_at_utc}")

    conn = sqlite3.connect(sqlite_path)
    ensure_db(conn)

    group_results: list[GroupResult] = []
    total_parsed = 0
    total_upserts = 0
    total_skipped = 0
    successful_groups = 0

    for group in groups:
        url = URL_TEMPLATE.format(group=group)
        print(f"[INFO] Fetching group='{group}' from {url}")

        raw_group = group.lower()
        raw_file_rel = f"data/raw/tles_{raw_group}_{run_stamp}.tle"
        raw_file_abs = repo_root / raw_file_rel

        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            text = response.text
            if response_is_no_data(text):
                print(f"[WARN] Group {group} returned no data; skipping")
                group_results.append(
                    GroupResult(
                        group=group,
                        raw_file_rel=None,
                        parsed_records=0,
                        sqlite_upserts=0,
                        skipped_malformed=0,
                        skipped_no_data=True,
                        fetch_ok=True,
                    )
                )
                continue

            raw_file_abs.write_text(text, encoding="utf-8")
            print(
                f"[INFO] Saved raw {group} response to {raw_file_rel} ({len(text.encode('utf-8'))} bytes)"
            )

            rows, skipped = parse_tle_text(
                text=text, source_group=group, fetched_at_utc=fetched_at_utc
            )
            upserts = upsert_tles(conn, rows)
            conn.commit()

            print(
                f"[INFO] Parsed {len(rows)} records for group='{group}', "
                f"skipped malformed={skipped}, sqlite upserts={upserts}"
            )

            group_results.append(
                GroupResult(
                    group=group,
                    raw_file_rel=raw_file_rel,
                    parsed_records=len(rows),
                    sqlite_upserts=upserts,
                    skipped_malformed=skipped,
                    skipped_no_data=False,
                    fetch_ok=True,
                )
            )
            total_parsed += len(rows)
            total_upserts += upserts
            total_skipped += skipped
            successful_groups += 1
        except Exception as exc:
            print(f"[ERROR] Failed processing group='{group}': {exc}")
            group_results.append(
                GroupResult(
                    group=group,
                    raw_file_rel=None,
                    parsed_records=0,
                    sqlite_upserts=0,
                    skipped_malformed=0,
                    skipped_no_data=False,
                    fetch_ok=False,
                )
            )

    conn.close()

    manifest = {
        "fetched_at_utc": fetched_at_utc,
        "groups": {
            result.group: {
                "parsed_records": result.parsed_records,
                "sqlite_upserts": result.sqlite_upserts,
                "skipped_malformed": result.skipped_malformed,
                "skipped_no_data": result.skipped_no_data,
                "fetch_ok": result.fetch_ok,
                **({"raw_file": result.raw_file_rel} if result.raw_file_rel else {}),
            }
            for result in group_results
        },
        "parsed_records": total_parsed,
        "sqlite_upserts": total_upserts,
        "skipped_malformed": total_skipped,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"[INFO] Wrote manifest: data/processed/tle_manifest_latest.json")
    print(
        f"[INFO] Run totals: parsed_records={total_parsed}, "
        f"sqlite_upserts={total_upserts}, skipped_malformed={total_skipped}"
    )

    if successful_groups == 0:
        print("[ERROR] No groups fetched successfully; ingest failed.")
        return 1

    print(f"[INFO] Ingest complete. Successful groups: {successful_groups}/{len(groups)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
