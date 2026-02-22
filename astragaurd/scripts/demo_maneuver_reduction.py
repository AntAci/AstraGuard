#!/usr/bin/env python3
"""Deterministic demo script for trend-gated defer and maneuver delta-v reduction."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.main import run_autonomy_loop_internal  # noqa: E402
from packages.contracts.versioning import SCHEMA_VERSION  # noqa: E402


def _run_cmd(args: List[str]) -> None:
    proc = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)


def _build_payload() -> Dict[str, Any]:
    return {
        "request_id": "REQ-DEMO-MANEUVER",
        "mode": "live",
        "selection_strategy": "top_risk",
        "target_event_id": None,
        "providers": {
            "consultant": "claude-3-7-sonnet",
            "vision": "gemini-2.5-flash",
            "payments": "stripe",
            "value": "paid_ai",
            "voice": "elevenlabs",
        },
        "payment": {"enabled": True, "amount_usd": 0.0, "currency": "USD"},
        "schema_version": SCHEMA_VERSION,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic maneuver-reduction demo.")
    parser.add_argument("--fetch-tles", action="store_true", help="Fetch fresh TLEs before screening.")
    parser.add_argument("--start-utc", default="2026-02-22T00:00:00Z", help="Fixed screening start for deterministic outputs.")
    args = parser.parse_args()

    if args.fetch_tles:
        _run_cmd([sys.executable, "scripts/fetch_tles.py"])

    _run_cmd(
        [
            sys.executable,
            "scripts/run_screening.py",
            "--start-utc",
            str(args.start_utc),
            "--seed",
            "42",
            "--top-k",
            "20",
            "--trend-window-minutes",
            "30",
            "--trend-cadence-seconds",
            "60",
            "--candidate-burn-offsets-h",
            "24,12,6,2",
            "--max-delta-v-mps",
            "0.5",
        ]
    )

    rows: List[Dict[str, Any]] = []
    payload = _build_payload()
    for event_index in range(3):
        response = run_autonomy_loop_internal(payload=payload, event_index=event_index)
        result = response.get("result") or {}
        trend = result.get("trend_metrics") or {}
        plan = result.get("maneuver_plan") or {}
        rows.append(
            {
                "event_id": result.get("selected_event_id"),
                "pc_peak": trend.get("pc_peak"),
                "decision": result.get("decision_mode", (result.get("decision") or {}).get("decision")),
                "defer_until": result.get("defer_until_utc"),
                "plan_delta_v": plan.get("delta_v_mps"),
                "plan_time": plan.get("burn_time_utc"),
                "early_vs_late": plan.get("early_vs_late_ratio"),
            }
        )

    headers = [
        "event_id",
        "pc_peak",
        "decision",
        "defer_until",
        "plan_delta_v",
        "plan_time",
        "early_vs_late",
    ]
    print(" | ".join(headers))
    print("-" * 140)
    for row in rows:
        print(" | ".join(_fmt(row.get(col)) for col in headers))

    print("\n[INFO] Last run summary JSON:")
    latest = REPO_ROOT / "data" / "processed" / "autonomy_run_result_latest.json"
    if latest.exists():
        payload = json.loads(latest.read_text(encoding="utf-8"))
        print(json.dumps({
            "selected_event_id": payload.get("selected_event_id"),
            "decision_mode": payload.get("decision_mode"),
            "defer_until_utc": payload.get("defer_until_utc"),
            "maneuver_plan": payload.get("maneuver_plan"),
        }, indent=2))


if __name__ == "__main__":
    main()
