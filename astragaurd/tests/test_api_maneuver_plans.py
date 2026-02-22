#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from apps.api import main as api_main


class ApiManeuverPlansTests(unittest.TestCase):
    def test_include_plans_embeds_nullable_fields_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            top_path = tmp / "top_conjunctions.json"
            manifest_path = tmp / "artifacts_latest.json"

            top_payload = {
                "schema_version": "1.1.0",
                "generated_at_utc": "2026-02-22T00:00:00Z",
                "event_count": 1,
                "events": [
                    {
                        "event_id": "EVT-1-2-2026-02-23T00:00:00Z",
                        "primary_id": 1,
                        "secondary_id": 2,
                        "tca_utc": "2026-02-23T00:00:00Z",
                        "tca_index_snapshot": 0,
                        "miss_distance_m": 123.0,
                        "relative_speed_mps": 10.0,
                        "pc_assumed": 1e-6,
                        "risk_score": 1e-6,
                        "window_start_utc": "2026-02-22T23:00:00Z",
                        "window_end_utc": "2026-02-23T01:00:00Z",
                        "model_version": "test",
                        "assumptions": {},
                        "schema_version": "1.1.0",
                    }
                ],
            }
            top_path.write_text(json.dumps(top_payload), encoding="utf-8")

            manifest_payload = {
                "generated_at_utc": "2026-02-22T00:00:00Z",
                "latest_run_id": None,
                "artifacts": {
                    "top_conjunctions": {
                        "path": str(top_path),
                        "schema_version": "1.1.0",
                        "model_version": "test",
                        "sha256": "x",
                        "generated_at_utc": "2026-02-22T00:00:00Z",
                    },
                    "cesium_snapshot": {
                        "path": str(tmp / "cesium_orbits_snapshot.json"),
                        "schema_version": "1.1.0",
                        "model_version": "test",
                        "sha256": "x",
                        "generated_at_utc": "2026-02-22T00:00:00Z",
                    },
                },
                "schema_version": "1.1.0",
            }
            manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

            old_top = api_main.TOP_CONJUNCTIONS_PATH
            old_manifest = api_main.ARTIFACTS_LATEST_PATH
            old_plans = api_main.MANEUVER_PLANS_PATH
            try:
                api_main.TOP_CONJUNCTIONS_PATH = top_path
                api_main.ARTIFACTS_LATEST_PATH = manifest_path
                api_main.MANEUVER_PLANS_PATH = tmp / "maneuver_plans.json"
                payload = api_main.get_top_conjunctions(include_plans=1)
                event = payload["events"][0]
                self.assertIn("decision_mode_hint", event)
                self.assertIsNone(event["decision_mode_hint"])
                self.assertIn("plan_delta_v_mps", event)
                self.assertIsNone(event["plan_delta_v_mps"])
            finally:
                api_main.TOP_CONJUNCTIONS_PATH = old_top
                api_main.ARTIFACTS_LATEST_PATH = old_manifest
                api_main.MANEUVER_PLANS_PATH = old_plans


if __name__ == "__main__":
    unittest.main()
