#!/usr/bin/env python3
"""Contracts for conjunction and Cesium artifact payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from packages.contracts.versioning import ORBIT_MODEL_VERSION, SCHEMA_VERSION


@dataclass
class ConjunctionAssumptions:
    dt_s: int
    dt_refine_s: int
    horizon_hours: float
    hard_body_radius_m: float
    sigma_payload_m: float
    sigma_debris_m: float
    voxel_km: float
    catalog_groups_used: List[str]


@dataclass
class ConjunctionEvent:
    event_id: str
    primary_id: int
    secondary_id: int
    tca_utc: str
    tca_index_snapshot: int
    miss_distance_m: float
    relative_speed_mps: float
    pc_assumed: float
    risk_score: float
    window_start_utc: str
    window_end_utc: str
    model_version: str
    assumptions: Dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TopConjunctionsArtifact:
    generated_at_utc: str
    event_count: int
    events: List[ConjunctionEvent]
    artifact_type: str = "top_conjunctions"
    model_version: str = ORBIT_MODEL_VERSION
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["events"] = [event.to_dict() for event in self.events]
        return payload


@dataclass
class CesiumSnapshotMeta:
    native_dt_s: int
    export_dt_s: int
    downsample_step: int


@dataclass
class CesiumObject:
    object_index: int
    norad_id: int
    name: str
    source_group: str
    positions_ecef_m: List[List[float]]


@dataclass
class CesiumSnapshot:
    generated_at_utc: str
    times_utc: List[str]
    meta: CesiumSnapshotMeta
    notes: str
    objects: List[CesiumObject]
    artifact_type: str = "cesium_snapshot"
    frame: str = "ECEF"
    units: str = "meters"
    model_version: str = ORBIT_MODEL_VERSION
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendSample:
    t_utc: str
    miss_m: float
    pc: float


@dataclass
class TrendMetrics:
    pc_peak: float
    pc_slope: float
    pc_stability: float
    window_minutes: int
    cadence_seconds: int
    sample_count: int
    time_to_tca_hours: float
    threshold: float
    critical_override: float
    gate_decision: str
    gate_reason_code: str
    gate_reason: str


@dataclass
class ManeuverPlan:
    burn_time_utc: str
    frame: str
    direction: str
    delta_v_mps: float
    expected_miss_m: float
    feasibility: str
    early_vs_late_ratio: Optional[float]
    notes: str


@dataclass
class ManeuverPlanEntry:
    event_id: str
    trend_metrics: TrendMetrics
    pc_series: List[TrendSample]
    decision_mode_hint: str
    defer_until_utc: Optional[str] = None
    maneuver_plan: Optional[ManeuverPlan] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ManeuverPlansArtifact:
    generated_at_utc: str
    event_count: int
    plans_by_event_id: Dict[str, ManeuverPlanEntry]
    artifact_type: str = "maneuver_plans"
    model_version: str = ORBIT_MODEL_VERSION
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["plans_by_event_id"] = {
            event_id: entry.to_dict()
            for event_id, entry in self.plans_by_event_id.items()
        }
        return payload
