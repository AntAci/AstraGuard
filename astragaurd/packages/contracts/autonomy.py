#!/usr/bin/env python3
"""Contracts for autonomy-loop provider outputs and API payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from packages.contracts.versioning import AUTONOMY_MODEL_VERSION, SCHEMA_VERSION


DECISION_IGNORE = "IGNORE"
DECISION_MONITOR = "MONITOR"
DECISION_INSURE = "INSURE"
DECISION_MANEUVER = "MANEUVER"
VALID_DECISIONS = {
    DECISION_IGNORE,
    DECISION_MONITOR,
    DECISION_INSURE,
    DECISION_MANEUVER,
}


@dataclass
class VisionFinding:
    code: str
    severity: str
    detail: str


@dataclass
class VisionReport:
    vision_report_id: str
    event_id: str
    provider: str
    model_version: str
    status: str
    confidence: float
    summary: str
    findings: List[VisionFinding]
    generated_at_utc: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConsultantDecision:
    decision_id: str
    event_id: str
    provider: str
    model_version: str
    decision: str
    confidence: float
    rationale: str
    recommended_actions: List[str]
    generated_at_utc: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PaymentResult:
    payment_result_id: str
    decision_id: str
    event_id: str
    provider: str
    mode: str
    status: str
    amount_usd: float
    currency: str
    payment_intent_id: Optional[str]
    processed_at_utc: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValueSignal:
    value_signal_id: str
    event_id: str
    provider: str
    model_version: str
    estimated_loss_avoided_usd: float
    estimated_cost_usd: float
    roi_ratio: float
    confidence: float
    generated_at_utc: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VoiceResult:
    provider: str
    status: str
    audio_url: Optional[str]
    script_text: str


@dataclass
class ArtifactRefs:
    top_conjunctions_path: str
    cesium_snapshot_path: str


@dataclass
class AutonomyRunResult:
    run_id: str
    status: str
    started_at_utc: str
    completed_at_utc: str
    selected_event_id: str
    top_event_ids: List[str]
    vision_report: VisionReport
    consultant_decision: ConsultantDecision
    value_signal: ValueSignal
    payment_result: PaymentResult
    voice: VoiceResult
    refs: ArtifactRefs
    errors: List[str]
    model_version: str = AUTONOMY_MODEL_VERSION
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderRequest:
    consultant: str
    vision: str
    payments: str
    value: str
    voice: str


@dataclass
class PaymentRequest:
    enabled: bool
    amount_usd: float
    currency: str


@dataclass
class RunAutonomyLoopRequest:
    request_id: str
    mode: str
    selection_strategy: str
    target_event_id: Optional[str]
    providers: ProviderRequest
    payment: PaymentRequest
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunAutonomyLoopResponse:
    run_id: str
    status: str
    result: AutonomyRunResult
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
