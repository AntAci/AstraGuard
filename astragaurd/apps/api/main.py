#!/usr/bin/env python3
"""FastAPI contract-boundary endpoints for AstraGuard Phase 0."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.commerce.service import build_payment_result, build_value_signal  # noqa: E402
from packages.contracts.autonomy import (  # noqa: E402
    ArtifactRefs,
    AutonomyRunResult,
    ConsultantDecision,
    ProviderRequest,
    RunAutonomyLoopResponse,
    VALID_DECISIONS,
    VisionFinding,
    VisionReport,
    VoiceResult,
)
from packages.contracts.manifest import ArtifactEntry, ArtifactsLatest  # noqa: E402
from packages.contracts.versioning import AUTONOMY_MODEL_VERSION, SCHEMA_VERSION  # noqa: E402
from packages.telemetry.service import emit_event  # noqa: E402


app = FastAPI(title="AstraGuard API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_LATEST_PATH = PROCESSED_DIR / "artifacts_latest.json"
TOP_CONJUNCTIONS_PATH = PROCESSED_DIR / "top_conjunctions.json"
CESIUM_SNAPSHOT_PATH  = PROCESSED_DIR / "cesium_orbits_snapshot.json"


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _load_artifacts_latest() -> Dict[str, Any]:
    if not ARTIFACTS_LATEST_PATH.exists():
        raise HTTPException(status_code=404, detail={"schema_version": SCHEMA_VERSION, "error": "ARTIFACTS_LATEST_NOT_FOUND"})
    data = _read_json(ARTIFACTS_LATEST_PATH)
    return data


def _validate_request(payload: Dict[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(status_code=422, detail={"schema_version": SCHEMA_VERSION, "error": "INVALID_REQUEST", "details": ["schema_version mismatch"]})
    providers = payload.get("providers") or {}
    required_provider_keys = {"consultant", "vision", "payments", "value", "voice"}
    if set(providers.keys()) != required_provider_keys:
        raise HTTPException(status_code=422, detail={"schema_version": SCHEMA_VERSION, "error": "INVALID_REQUEST", "details": ["providers must contain consultant, vision, payments, value, voice"]})


@app.get("/artifacts/latest")
def get_artifacts_latest() -> Dict[str, Any]:
    return _load_artifacts_latest()


@app.get("/artifacts/top-conjunctions")
def get_top_conjunctions() -> Dict[str, Any]:
    if not TOP_CONJUNCTIONS_PATH.exists():
        raise HTTPException(status_code=404, detail={"schema_version": SCHEMA_VERSION, "error": "TOP_CONJUNCTIONS_NOT_FOUND"})
    return _read_json(TOP_CONJUNCTIONS_PATH)


@app.get("/artifacts/cesium-snapshot")
def get_cesium_snapshot() -> FileResponse:
    if not CESIUM_SNAPSHOT_PATH.exists():
        raise HTTPException(status_code=404, detail={"schema_version": SCHEMA_VERSION, "error": "CESIUM_SNAPSHOT_NOT_FOUND"})
    return FileResponse(str(CESIUM_SNAPSHOT_PATH), media_type="application/json")


@app.post("/run-autonomy-loop")
def run_autonomy_loop(payload: Dict[str, Any]) -> Dict[str, Any]:
    started_at = _iso_utc_now()
    _validate_request(payload)

    latest = _load_artifacts_latest()
    artifacts = latest.get("artifacts") or {}

    top_path = artifacts.get("top_conjunctions", {}).get("path")
    snapshot_path = artifacts.get("cesium_snapshot", {}).get("path")
    if not top_path or not snapshot_path:
        raise HTTPException(status_code=500, detail={"schema_version": SCHEMA_VERSION, "error": "AUTONOMY_LOOP_FAILED", "details": ["Required artifacts missing from artifacts_latest"]})

    top_json = _read_json(REPO_ROOT / top_path)
    events = top_json.get("events") or []
    if not events:
        raise HTTPException(status_code=500, detail={"schema_version": SCHEMA_VERSION, "error": "AUTONOMY_LOOP_FAILED", "details": ["No events in top_conjunctions artifact"]})

    target_event_id = payload.get("target_event_id")
    selected_event = None
    if target_event_id:
        for event in events:
            if event.get("event_id") == target_event_id:
                selected_event = event
                break
        if selected_event is None:
            raise HTTPException(status_code=422, detail={"schema_version": SCHEMA_VERSION, "error": "INVALID_REQUEST", "details": ["target_event_id not found"]})
    else:
        selected_event = events[0]

    run_id = "RUN-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    event_id = selected_event["event_id"]
    providers = payload["providers"]

    vision_report = VisionReport(
        vision_report_id="VR-" + run_id.split("RUN-")[1],
        event_id=event_id,
        provider=providers["vision"],
        model_version=providers["vision"],
        status="ok",
        confidence=0.8,
        summary="Phase-0 deterministic report placeholder.",
        findings=[VisionFinding(code="CLOSE_APPROACH_REVIEWED", severity="medium", detail="Event reviewed against current artifact set.")],
        generated_at_utc=_iso_utc_now(),
    )

    pc = float(selected_event.get("pc_assumed", 0.0))
    if pc >= 1e-4:
        decision_value = "INSURE"
        actions = ["issue_policy_quote", "monitor_6h"]
    elif pc >= 1e-6:
        decision_value = "MONITOR"
        actions = ["monitor_6h"]
    else:
        decision_value = "IGNORE"
        actions = ["no_action"]

    if decision_value not in VALID_DECISIONS:
        raise HTTPException(status_code=500, detail={"schema_version": SCHEMA_VERSION, "error": "AUTONOMY_LOOP_FAILED", "details": ["Invalid decision enum generated"]})

    consultant_decision = ConsultantDecision(
        decision_id="DEC-" + run_id.split("RUN-")[1],
        event_id=event_id,
        provider=providers["consultant"],
        model_version=providers["consultant"],
        decision=decision_value,
        confidence=0.75,
        rationale="Phase-0 deterministic policy using pc_assumed thresholds.",
        recommended_actions=actions,
        generated_at_utc=_iso_utc_now(),
    )

    payment_cfg = payload.get("payment") or {}
    payment_result = build_payment_result(
        payment_result_id="PAY-" + run_id.split("RUN-")[1],
        decision_id=consultant_decision.decision_id,
        event_id=event_id,
        provider=providers["payments"],
        mode=str(payload.get("mode", "dry_run")),
        payment_enabled=bool(payment_cfg.get("enabled", False)),
        amount_usd=float(payment_cfg.get("amount_usd", 0.0)),
        currency=str(payment_cfg.get("currency", "USD")),
    )

    value_signal = build_value_signal(
        value_signal_id="VAL-" + run_id.split("RUN-")[1],
        event_id=event_id,
        provider=providers["value"],
        model_version=providers["value"],
        pc_assumed=pc,
        miss_distance_m=float(selected_event.get("miss_distance_m", 0.0)),
        estimated_cost_usd=payment_result.amount_usd,
    )

    voice = VoiceResult(
        provider=providers["voice"],
        status="queued",
        audio_url=None,
        script_text="Potential conjunction risk reviewed. Recommendation generated.",
    )

    result = AutonomyRunResult(
        run_id=run_id,
        status="completed",
        started_at_utc=started_at,
        completed_at_utc=_iso_utc_now(),
        selected_event_id=event_id,
        top_event_ids=[event.get("event_id") for event in events[:5]],
        vision_report=vision_report,
        consultant_decision=consultant_decision,
        value_signal=value_signal,
        payment_result=payment_result,
        voice=voice,
        refs=ArtifactRefs(
            top_conjunctions_path=str(top_path),
            cesium_snapshot_path=str(snapshot_path),
        ),
        errors=[],
        model_version=AUTONOMY_MODEL_VERSION,
    )

    run_response = RunAutonomyLoopResponse(run_id=run_id, status="completed", result=result)

    autonomy_path = PROCESSED_DIR / "autonomy_run_result_latest.json"
    _write_json(autonomy_path, result.to_dict())

    updated_artifacts = dict(artifacts)
    updated_artifacts["autonomy_run_result"] = ArtifactEntry(
        path=str(autonomy_path.relative_to(REPO_ROOT)),
        schema_version=SCHEMA_VERSION,
        model_version=AUTONOMY_MODEL_VERSION,
        sha256=_sha256_file(autonomy_path),
        generated_at_utc=_iso_utc_now(),
    ).__dict__

    updated_manifest = ArtifactsLatest(
        generated_at_utc=_iso_utc_now(),
        latest_run_id=run_id,
        artifacts=updated_artifacts,
    )
    _write_json(ARTIFACTS_LATEST_PATH, updated_manifest.to_dict())

    emit_event(PROCESSED_DIR, "run_autonomy_loop.completed", {"run_id": run_id, "event_id": event_id})

    return run_response.to_dict()
