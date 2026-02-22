#!/usr/bin/env python3

from __future__ import annotations

import unittest

from packages.orbit.maneuver import ManeuverPolicy, plan_min_delta_v


class ManeuverPlannerTests(unittest.TestCase):
    def test_selects_minimum_delta_v_feasible_candidate(self) -> None:
        event = {
            "tca_utc": "2026-02-23T12:00:00Z",
            "miss_distance_m": 200.0,
            "relative_speed_mps": 10000.0,
        }
        policy = ManeuverPolicy(
            miss_distance_target_m=1000.0,
            max_delta_v_mps=0.5,
            candidate_offsets_h=[24.0, 12.0, 6.0, 2.0],
            late_burn_minutes=30.0,
        )
        plan = plan_min_delta_v(event=event, policy=policy)
        self.assertEqual(plan["feasibility"], "feasible")
        self.assertEqual(plan["direction"], "+T")
        self.assertAlmostEqual(float(plan["delta_v_mps"]), 800.0 / (24.0 * 3600.0), places=6)

    def test_marks_infeasible_when_cap_too_low(self) -> None:
        event = {
            "tca_utc": "2026-02-23T12:00:00Z",
            "miss_distance_m": 10.0,
            "relative_speed_mps": 10000.0,
        }
        policy = ManeuverPolicy(
            miss_distance_target_m=5000.0,
            max_delta_v_mps=1e-4,
            candidate_offsets_h=[2.0],
            late_burn_minutes=30.0,
        )
        plan = plan_min_delta_v(event=event, policy=policy)
        self.assertEqual(plan["feasibility"], "infeasible")
        self.assertIsNone(plan["delta_v_mps"])


if __name__ == "__main__":
    unittest.main()
