#!/usr/bin/env python3

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from packages.orbit.trend import TrendConfig, classify_trend_gate, compute_trend_metrics


class TrendGateTests(unittest.TestCase):
    def test_classification_from_synthetic_series(self) -> None:
        cfg = TrendConfig(window_minutes=5, cadence_seconds=60, threshold=1e-5, critical_override=1e-3)
        series = [
            {"t_utc": "2026-02-22T10:00:00Z", "miss_m": 1200.0, "pc": 1e-7},
            {"t_utc": "2026-02-22T10:01:00Z", "miss_m": 1100.0, "pc": 2e-6},
            {"t_utc": "2026-02-22T10:02:00Z", "miss_m": 1000.0, "pc": 2e-5},
            {"t_utc": "2026-02-22T10:03:00Z", "miss_m": 900.0, "pc": 4e-5},
        ]
        metrics = compute_trend_metrics(
            pc_series=series,
            tca_utc="2026-02-22T14:00:00Z",
            now_utc=datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc),
            config=cfg,
        )
        out = classify_trend_gate(
            trend_metrics=metrics,
            tca_utc="2026-02-22T14:00:00Z",
            now_utc=datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc),
            defer_hours=24.0,
        )
        self.assertEqual(out["decision_mode_hint"], "MANEUVER")

    def test_defer_when_far_from_tca(self) -> None:
        metrics = {
            "pc_peak": 1e-4,
            "pc_slope": 1e-6,
            "pc_stability": 0.8,
            "threshold": 1e-5,
            "critical_override": 1e-3,
            "time_to_tca_hours": 48.0,
        }
        out = classify_trend_gate(
            trend_metrics=metrics,
            tca_utc="2026-02-25T00:00:00Z",
            now_utc=datetime(2026, 2, 22, 0, 0, tzinfo=timezone.utc),
            defer_hours=24.0,
        )
        self.assertEqual(out["decision_mode_hint"], "DEFER")
        self.assertIsNotNone(out["defer_until_utc"])

    def test_ignore_below_threshold(self) -> None:
        metrics = {
            "pc_peak": 1e-8,
            "pc_slope": 1e-6,
            "pc_stability": 0.9,
            "threshold": 1e-5,
            "critical_override": 1e-3,
            "time_to_tca_hours": 6.0,
        }
        out = classify_trend_gate(
            trend_metrics=metrics,
            tca_utc="2026-02-23T00:00:00Z",
            now_utc=datetime(2026, 2, 22, 18, 0, tzinfo=timezone.utc),
            defer_hours=24.0,
        )
        self.assertEqual(out["decision_mode_hint"], "IGNORE")

    def test_maneuver_when_sustained(self) -> None:
        metrics = {
            "pc_peak": 5e-5,
            "pc_slope": 2e-6,
            "pc_stability": 0.55,
            "threshold": 1e-5,
            "critical_override": 1e-3,
            "time_to_tca_hours": 4.0,
        }
        out = classify_trend_gate(
            trend_metrics=metrics,
            tca_utc="2026-02-22T20:00:00Z",
            now_utc=datetime(2026, 2, 22, 16, 0, tzinfo=timezone.utc),
            defer_hours=24.0,
        )
        self.assertEqual(out["decision_mode_hint"], "MANEUVER")


if __name__ == "__main__":
    unittest.main()
