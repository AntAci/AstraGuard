#!/usr/bin/env python3
"""Minimal telemetry sink for Phase 0 orchestration traces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def emit_event(processed_dir: Path, event_type: str, payload: Dict[str, Any]) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    path = processed_dir / "telemetry_events.jsonl"
    record = {
        "event_type": event_type,
        "emitted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
