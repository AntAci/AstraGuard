#!/usr/bin/env python3
"""FastAPI contract-boundary endpoints for AstraGuard autonomy loop."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.brain import consultant  # noqa: E402
from packages.commerce import stripe_wallet  # noqa: E402
from packages.earth.impact import compute_impact_score  # noqa: E402
from packages.voice.elevenlabs import synthesize_speech  # noqa: E402
from packages.contracts.manifest import ArtifactEntry, ArtifactsLatest  # noqa: E402
from packages.contracts.versioning import AUTONOMY_MODEL_VERSION, SCHEMA_VERSION, SUPPORTED_REQUEST_SCHEMA_VERSIONS  # noqa: E402
from packages.telemetry.phoenix import init_tracing_if_enabled  # noqa: E402
from packages.telemetry.service import emit_event  # noqa: E402
from packages.telemetry.value_signals import append_ledger_record, compute_value_signal, update_ledger_summary  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)

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
CESIUM_SNAPSHOT_PATH = PROCESSED_DIR / "cesium_orbits_snapshot.json"
MANEUVER_PLANS_PATH = PROCESSED_DIR / "maneuver_plans.json"


def _load_dotenv_file(path: Path) -> None:
    """Load KEY=VALUE lines into environment without overriding existing vars."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip())


_load_dotenv_file(REPO_ROOT / ".env")
init_tracing_if_enabled()

_CESIUM_CACHE: Optional[Dict[str, Any]] = None


def _ensure_cesium_cache() -> Optional[Dict[str, Any]]:
    global _CESIUM_CACHE
    if _CESIUM_CACHE is None and CESIUM_SNAPSHOT_PATH.exists():
        try:
            _CESIUM_CACHE = _read_json(CESIUM_SNAPSHOT_PATH)
            LOGGER.info("Cesium snapshot loaded into cache (%s)", CESIUM_SNAPSHOT_PATH)
        except Exception as err:
            LOGGER.warning("Failed to load cesium snapshot cache: %s", err)
    return _CESIUM_CACHE


@app.on_event("startup")
def _startup_cache() -> None:
    _ensure_cesium_cache()


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _resolve_path(raw_value: Optional[str], default_value: str) -> Path:
    value = (raw_value or default_value).strip()
    path = Path(value)
    if path.is_absolute():
        return path
    if value.startswith("astragaurd/"):
        return REPO_ROOT.parent / value
    return REPO_ROOT / value


def _artifact_path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        try:
            return str(path.relative_to(REPO_ROOT.parent))
        except ValueError:
            return str(path)


def _load_artifacts_latest() -> Dict[str, Any]:
    if not ARTIFACTS_LATEST_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail={"schema_version": SCHEMA_VERSION, "error": "ARTIFACTS_LATEST_NOT_FOUND"},
        )
    return _read_json(ARTIFACTS_LATEST_PATH)


def _validate_request(payload: Dict[str, Any]) -> None:
    request_schema = str(payload.get("schema_version", "")).strip()
    if request_schema not in SUPPORTED_REQUEST_SCHEMA_VERSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "INVALID_REQUEST",
                "details": [f"schema_version unsupported: {request_schema}"],
            },
        )
    providers = payload.get("providers") or {}
    required_provider_keys = {"consultant", "vision", "payments", "value", "voice"}
    if set(providers.keys()) != required_provider_keys:
        raise HTTPException(
            status_code=422,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "INVALID_REQUEST",
                "details": ["providers must contain consultant, vision, payments, value, voice"],
            },
        )


def _load_events_from_manifest(manifest: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str, str]:
    artifacts = manifest.get("artifacts") or {}
    top_path_str = (artifacts.get("top_conjunctions") or {}).get("path")
    snapshot_path_str = (artifacts.get("cesium_snapshot") or {}).get("path")
    if not top_path_str or not snapshot_path_str:
        raise HTTPException(
            status_code=500,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "AUTONOMY_LOOP_FAILED",
                "details": ["Required artifacts missing from artifacts_latest"],
            },
        )

    top_path = _resolve_path(top_path_str, "data/processed/top_conjunctions.json")
    top_json = _read_json(top_path)
    events = top_json.get("events") or []
    if not events:
        raise HTTPException(
            status_code=500,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "AUTONOMY_LOOP_FAILED",
                "details": ["No events in top_conjunctions artifact"],
            },
        )
    return events, top_path_str, snapshot_path_str


def _load_maneuver_plans_from_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = manifest.get("artifacts") or {}
    plans_path_str = (artifacts.get("maneuver_plans") or {}).get("path")
    plans_path = _resolve_path(plans_path_str, "data/processed/maneuver_plans.json")
    if not plans_path.exists():
        return {}
    payload = _read_json(plans_path)
    plans = payload.get("plans_by_event_id")
    if isinstance(plans, dict):
        return plans
    return {}


_EVENT_ID_RE = re.compile(r"^EVT-(\d+)-(\d+)-(.+)$")


def _parse_utc_or_none(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _extract_event_pair_and_tca(event: Dict[str, Any]) -> tuple[Optional[tuple[int, int]], Optional[datetime]]:
    event_id = str(event.get("event_id", "")).strip()
    primary: Optional[int] = None
    secondary: Optional[int] = None
    tca = _parse_utc_or_none(event.get("tca_utc"))

    match = _EVENT_ID_RE.match(event_id)
    if match:
        try:
            primary = int(match.group(1))
            secondary = int(match.group(2))
        except Exception:
            primary = None
            secondary = None
        if tca is None:
            tca = _parse_utc_or_none(match.group(3))

    if primary is None:
        primary = _safe_int(event.get("primary_id", event.get("primary_norad_id")), -1)
        if primary < 0:
            primary = None
    if secondary is None:
        secondary = _safe_int(event.get("secondary_id", event.get("secondary_norad_id")), -1)
        if secondary < 0:
            secondary = None

    pair = tuple(sorted((primary, secondary))) if primary is not None and secondary is not None else None
    return pair, tca


def _resolve_plan_entry_for_event(event: Dict[str, Any], plans_by_event_id: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
    if not isinstance(plans_by_event_id, dict) or not plans_by_event_id:
        return {}, None

    event_id = str(event.get("event_id", "")).strip()
    exact = plans_by_event_id.get(event_id)
    if isinstance(exact, dict):
        return exact, event_id

    target_pair, target_tca = _extract_event_pair_and_tca(event)
    if target_pair is None:
        return {}, None

    best_entry: Optional[Dict[str, Any]] = None
    best_event_id: Optional[str] = None
    best_delta_seconds: Optional[float] = None

    for candidate_event_id, candidate_entry in plans_by_event_id.items():
        if not isinstance(candidate_entry, dict):
            continue
        candidate_identity = {"event_id": str(candidate_event_id)}
        candidate_pair, candidate_tca = _extract_event_pair_and_tca(candidate_identity)
        if candidate_pair != target_pair:
            continue
        if target_tca is not None and candidate_tca is not None:
            delta_seconds = abs((candidate_tca - target_tca).total_seconds())
        else:
            delta_seconds = float("inf")
        if best_delta_seconds is None or delta_seconds < best_delta_seconds:
            best_delta_seconds = delta_seconds
            best_entry = candidate_entry
            best_event_id = str(candidate_event_id)

    if best_entry is None:
        return {}, None
    return best_entry, best_event_id


def _compute_default_defer_until(tca_utc: str) -> Optional[str]:
    try:
        tca = datetime.fromisoformat(str(tca_utc).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
    now = datetime.now(timezone.utc)
    defer_until = min(tca - timedelta(hours=12), now + timedelta(hours=6))
    min_time = now + timedelta(minutes=10)
    if defer_until < min_time:
        defer_until = min_time
    return defer_until.strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_future_defer_until(raw_defer_until_utc: Optional[str], tca_utc: str) -> Optional[str]:
    if raw_defer_until_utc:
        try:
            defer_dt = datetime.fromisoformat(str(raw_defer_until_utc).replace("Z", "+00:00")).astimezone(timezone.utc)
            if defer_dt >= datetime.now(timezone.utc) + timedelta(minutes=10):
                return defer_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    return _compute_default_defer_until(tca_utc)


def _select_event(events: List[Dict[str, Any]], target_event_id: Optional[str], event_index: int) -> Dict[str, Any]:
    if target_event_id:
        for event in events:
            if event.get("event_id") == target_event_id:
                return event
        raise HTTPException(
            status_code=422,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "INVALID_REQUEST",
                "details": ["target_event_id not found"],
            },
        )
    if event_index < 0 or event_index >= len(events):
        raise HTTPException(
            status_code=422,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "INVALID_REQUEST",
                "details": [f"event_index out of range (0..{len(events)-1})"],
            },
        )
    return events[event_index]


def _event_looks_active(event: Dict[str, Any]) -> bool:
    assumptions = event.get("assumptions") or {}
    groups = assumptions.get("catalog_groups_used") or []
    if any("ACTIVE" in str(group).upper() for group in groups):
        return True
    for key in ("primary_group", "secondary_group", "primary_name", "secondary_name"):
        if "ACTIVE" in str(event.get(key, "")).upper():
            return True
    return False


def _decision_actions(decision: str) -> List[str]:
    if decision == "INSURE":
        return ["execute_insurance_purchase", "monitor_24h"]
    if decision == "MANEUVER":
        return ["schedule_maneuver", "monitor_24h"]
    if decision == "DEFER":
        return ["defer_and_rerun", "monitor_6h"]
    return ["no_action"]


def _llm_model_name(provider: str) -> str:
    if provider == "claude":
        return os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    return "unknown_provider"


def _build_loop_request() -> Dict[str, Any]:
    return {
        "request_id": f"REQ-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
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


def run_autonomy_loop_internal(payload: Dict[str, Any], event_index: int = 0) -> Dict[str, Any]:
    """Run one synchronous autonomy loop and return response payload."""

    started_at = _iso_utc_now()
    _validate_request(payload)
    providers = payload["providers"]

    latest_manifest = _load_artifacts_latest()
    events, top_path_str, snapshot_path_str = _load_events_from_manifest(latest_manifest)
    plans_path_str = ((latest_manifest.get("artifacts") or {}).get("maneuver_plans") or {}).get("path")
    plans_by_event_id = _load_maneuver_plans_from_manifest(latest_manifest)
    target_event_id = payload.get("target_event_id")
    selected_event = _select_event(events, target_event_id, event_index)
    LOGGER.info("Autonomy run started (event_index=%s, target_event_id=%s)", event_index, target_event_id)

    run_id = "RUN-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    event_id = str(selected_event.get("event_id"))
    plan_entry, matched_plan_event_id = _resolve_plan_entry_for_event(selected_event, plans_by_event_id)
    if matched_plan_event_id and matched_plan_event_id != event_id:
        LOGGER.warning(
            "Plan lookup fallback matched event_id=%s to plan_event_id=%s",
            event_id,
            matched_plan_event_id,
        )
    trend_metrics = plan_entry.get("trend_metrics")
    if not isinstance(trend_metrics, dict):
        trend_metrics = {}
    maneuver_plan = plan_entry.get("maneuver_plan")
    if not isinstance(maneuver_plan, dict):
        maneuver_plan = None
    decision_mode_hint = str(plan_entry.get("decision_mode_hint", "")).upper().strip() or "IGNORE"
    if decision_mode_hint not in {"IGNORE", "DEFER", "MANEUVER"}:
        decision_mode_hint = "IGNORE"
    defer_until_utc = plan_entry.get("defer_until_utc")
    p_collision = _safe_float(selected_event.get("p_collision", selected_event.get("pc_assumed", 0.0)), 0.0)
    miss_distance_m = _safe_float(selected_event.get("miss_distance_m", 0.0), 0.0)
    relative_speed_mps = _safe_float(selected_event.get("relative_speed_mps", 0.0), 0.0)

    active_value = _safe_float(os.environ.get("ASTRA_ASSET_VALUE_ACTIVE_USD"), 200_000_000.0)
    debris_value = _safe_float(os.environ.get("ASTRA_ASSET_VALUE_DEBRIS_USD"), 1_000_000.0)
    maneuver_cost_usd = _safe_float(os.environ.get("ASTRA_MANEUVER_COST_USD"), 5_000.0)
    asset_value_usd = active_value if _event_looks_active(selected_event) else debris_value

    premium_quote_usd = stripe_wallet.quote_premium_usd(selected_event, asset_value_usd)

    # Earth impact score
    impact_result = compute_impact_score(selected_event, _ensure_cesium_cache())
    impact_score = _safe_float(impact_result.get("impact_score"), 0.15)

    # Deterministic adjusted expected loss
    raw_expected_loss = p_collision * asset_value_usd
    expected_loss_adjusted = raw_expected_loss * (1 + 2 * impact_score)

    LOGGER.info(
        "Economics prepared event_id=%s asset_value=%.2f premium_quote=%.2f maneuver_cost=%.2f impact=%.4f adj_loss=%.2f",
        selected_event.get("event_id"),
        asset_value_usd,
        premium_quote_usd,
        maneuver_cost_usd,
        impact_score,
        expected_loss_adjusted,
    )
    try:
        decision_obj = consultant.decide(
            selected_event,
            {"asset_value_usd": asset_value_usd, "impact_score": impact_score},
            {
                "premium_quote_usd": premium_quote_usd,
                "maneuver_cost_usd": maneuver_cost_usd,
                "raw_expected_loss_usd": raw_expected_loss,
                "expected_loss_adjusted_usd": expected_loss_adjusted,
                "trend_metrics": trend_metrics,
                "maneuver_plan": maneuver_plan,
            },
        )
    except Exception as err:
        LOGGER.exception("Consultant decision failed without fallback: %s", err)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "CONSULTANT_UNAVAILABLE",
                "details": [f"{type(err).__name__}: {err}"],
            },
        ) from err
    llm_recommendation = str(decision_obj.get("decision", "")).upper().strip()
    if llm_recommendation not in {"IGNORE", "INSURE", "MANEUVER", "DEFER"}:
        LOGGER.error("Unexpected decision value from consultant: %s", llm_recommendation)
        raise HTTPException(
            status_code=503,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error": "CONSULTANT_INVALID_OUTPUT",
                "details": [f"Unexpected decision value: {llm_recommendation!r}"],
            },
        )

    decision = llm_recommendation
    decision_mode = decision
    decision_reason_code = str(plan_entry.get("gate_reason_code", trend_metrics.get("gate_reason_code", "MODEL_RECOMMENDATION")))
    decision_reason_text = str(plan_entry.get("gate_reason", trend_metrics.get("gate_reason", "Decision selected by consultant model output.")))
    if decision == "DEFER":
        defer_until_utc = _ensure_future_defer_until(
            raw_defer_until_utc=defer_until_utc,
            tca_utc=str(selected_event.get("tca_utc", "")),
        )
    else:
        defer_until_utc = None

    if decision == "MANEUVER":
        if not maneuver_plan:
            decision_reason_code = "MANEUVER_PLAN_MISSING"
            decision_reason_text = "Consultant selected maneuver; no precomputed maneuver plan artifact is available."
        elif str(maneuver_plan.get("feasibility", "infeasible")).lower() != "feasible":
            decision_reason_code = "MANEUVER_PLAN_INFEASIBLE"
            decision_reason_text = "Consultant selected maneuver; precomputed maneuver plan is marked infeasible."

    decision_obj["decision"] = decision
    decision_obj["decision_mode"] = decision_mode
    decision_obj["llm_recommendation"] = llm_recommendation
    decision_obj["decision_mode_hint"] = decision_mode_hint
    decision_obj["decision_reason_code"] = decision_reason_code
    decision_obj["decision_reason_text"] = decision_reason_text
    decision_obj["trend_metrics"] = trend_metrics
    decision_obj["defer_until_utc"] = defer_until_utc
    decision_obj["maneuver_plan"] = maneuver_plan
    expected_loss_usd = _safe_float(decision_obj.get("expected_loss_usd"), expected_loss_adjusted)
    decision_obj["expected_loss_usd"] = expected_loss_usd
    decision_obj["var_usd"] = _safe_float(decision_obj.get("var_usd"), expected_loss_usd)
    llm_observability = decision_obj.get("llm_observability")
    if not isinstance(llm_observability, dict):
        llm_observability = {
            "provider": str(decision_obj.get("llm_provider", "unknown")),
            "model": _llm_model_name(str(decision_obj.get("llm_provider", "unknown"))),
            "latency_ms": 0.0,
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "source": "none"},
            "pricing": {"input_per_million_usd": 0.0, "output_per_million_usd": 0.0, "estimation_mode": "legacy_default"},
            "estimated_cost_usd": _safe_float(decision_obj.get("llm_cost_usd"), 0.0),
            "trace": {"trace_id": None, "span_id": None},
        }
        decision_obj["llm_observability"] = llm_observability
    decision_obj["llm_usage"] = llm_observability.get("usage") or decision_obj.get("llm_usage", {})
    decision_obj["llm_cost_usd"] = _safe_float(llm_observability.get("estimated_cost_usd"), decision_obj.get("llm_cost_usd", 0.0))
    LOGGER.info("Consultant decision=%s provider=%s", decision, decision_obj.get("llm_provider"))

    stripe_currency = os.environ.get("STRIPE_CURRENCY", "usd").lower()
    payment_obj: Dict[str, Any]
    if decision == "INSURE":
        policy_ok, policy_reason = stripe_wallet.enforce_spend_policy(premium_quote_usd, decision, policy_ctx=None)
        if not policy_ok:
            payment_obj = {
                "provider": "stripe",
                "status": "DENIED_BY_POLICY",
                "mode": os.environ.get("STRIPE_MODE", "checkout"),
                "amount_usd": premium_quote_usd,
                "currency": stripe_currency,
                "id": None,
                "checkout_url": None,
                "reason": policy_reason,
            }
        else:
            metadata = {
                "run_id": run_id,
                "event_id": event_id,
                "primary_id": _safe_int(selected_event.get("primary_id"), 0),
                "secondary_id": _safe_int(selected_event.get("secondary_id"), 0),
                "tca_utc": selected_event.get("tca_utc"),
                "p_collision": p_collision,
                "miss_distance_m": miss_distance_m,
                "relative_speed_mps": relative_speed_mps,
                "asset_value_usd": asset_value_usd,
                "expected_loss_usd": expected_loss_usd,
                "expected_loss_adjusted_usd": expected_loss_adjusted,
                "impact_score": impact_score,
                "premium_usd": premium_quote_usd,
                "llm_provider": decision_obj.get("llm_provider", "unknown"),
                "decision": decision,
            }
            payment_obj = stripe_wallet.execute_insurance_purchase(run_id, premium_quote_usd, metadata)
        LOGGER.info("INSURE action complete stripe_status=%s", payment_obj.get("status"))
        cost_usd = premium_quote_usd
    elif decision == "MANEUVER":
        payment_obj = {
            "provider": "stripe",
            "status": "SCHEDULED",
            "mode": "maneuver",
            "amount_usd": maneuver_cost_usd,
            "currency": stripe_currency,
            "id": None,
            "checkout_url": None,
        }
        LOGGER.info("MANEUVER action selected cost=%.2f", maneuver_cost_usd)
        cost_usd = maneuver_cost_usd
    elif decision == "DEFER":
        payment_obj = {
            "provider": "stripe",
            "status": "DEFERRED",
            "mode": "defer",
            "amount_usd": 0.0,
            "currency": stripe_currency,
            "id": None,
            "checkout_url": None,
        }
        LOGGER.info("DEFER action selected defer_until=%s", defer_until_utc)
        cost_usd = 0.0
    else:
        payment_obj = {
            "provider": "stripe",
            "status": "SKIPPED",
            "mode": "none",
            "amount_usd": 0.0,
            "currency": stripe_currency,
            "id": None,
            "checkout_url": None,
        }
        LOGGER.info("IGNORE action selected")
        cost_usd = 0.0

    value_signal = compute_value_signal(
        run_id=run_id,
        event=selected_event,
        decision=decision_obj,
        asset_value_usd=asset_value_usd,
        expected_loss_usd=expected_loss_usd,
        cost_usd=cost_usd,
        payment_obj=payment_obj,
    )

    ledger_path = _resolve_path(
        os.environ.get("ASTRA_AGENT_LEDGER_PATH"),
        "astragaurd/data/processed/agent_ledger.jsonl",
    )
    ledger_summary_path = _resolve_path(
        os.environ.get("ASTRA_AGENT_LEDGER_SUMMARY_PATH"),
        "astragaurd/data/processed/agent_ledger_summary.json",
    )
    append_ledger_record(value_signal, ledger_path)
    ledger_summary = update_ledger_summary(ledger_path, ledger_summary_path)
    LOGGER.info("Ledger updated path=%s runs=%s", ledger_path, ledger_summary.get("runs"))

    zone_label = impact_result.get("nearest_zone") or "open ocean"
    decision_cost_text = (
        f"Contingency coverage quote ${premium_quote_usd:.2f}."
        if decision == "INSURE"
        else f"Action cost ${cost_usd:.2f}."
    )
    narration_text = (
        f"AstraGuard briefing. Collision probability {p_collision:.2e} with miss distance "
        f"{miss_distance_m:.0f} meters. Earth impact score {impact_score:.0%} near {zone_label}. "
        f"Adjusted expected loss ${expected_loss_adjusted:,.0f}. Decision: {decision}. "
        f"{decision_cost_text} ROI {value_signal['roi']:.1f}x. "
        f"Provider: {decision_obj.get('llm_provider', 'unknown')}."
    )

    voice_result = synthesize_speech(narration_text)

    completed_at = _iso_utc_now()
    top_event_ids = [event.get("event_id") for event in events[:5] if event.get("event_id")]
    llm_provider = str(decision_obj.get("llm_provider", "unknown"))
    llm_model = str((llm_observability or {}).get("model", _llm_model_name(llm_provider)))

    legacy_consultant = {
        "decision_id": "DEC-" + run_id.split("RUN-")[1],
        "event_id": event_id,
        "provider": llm_provider,
        "model_version": llm_model,
        "decision": decision,
        "confidence": _safe_float(decision_obj.get("confidence"), 0.5),
        "rationale": " ".join(str(r) for r in decision_obj.get("rationale", []) if str(r).strip()),
        "recommended_actions": _decision_actions(decision),
        "generated_at_utc": completed_at,
        "schema_version": SCHEMA_VERSION,
    }
    legacy_payment = {
        "payment_result_id": "PAY-" + run_id.split("RUN-")[1],
        "decision_id": legacy_consultant["decision_id"],
        "event_id": event_id,
        "provider": "stripe",
        "mode": str(payment_obj.get("mode", "none")),
        "status": str(payment_obj.get("status", "UNKNOWN")),
        "amount_usd": _safe_float(payment_obj.get("amount_usd"), 0.0),
        "currency": str(payment_obj.get("currency", stripe_currency)).upper(),
        "payment_intent_id": payment_obj.get("id"),
        "transaction_id": payment_obj.get("id"),
        "processed_at_utc": completed_at,
        "schema_version": SCHEMA_VERSION,
    }
    legacy_value = {
        "value_signal_id": "VAL-" + run_id.split("RUN-")[1],
        "event_id": event_id,
        "provider": providers.get("value", "paid_ai"),
        "model_version": providers.get("value", "paid_ai"),
        "estimated_loss_avoided_usd": _safe_float(value_signal.get("expected_loss_avoided_usd"), 0.0),
        "estimated_cost_usd": _safe_float(value_signal.get("cost_usd"), 0.0),
        "intervention_cost_usd": _safe_float(value_signal.get("cost_usd"), 0.0),
        "roi_ratio": _safe_float(value_signal.get("roi"), 0.0),
        "confidence": _safe_float(decision_obj.get("confidence"), 0.5),
        "generated_at_utc": completed_at,
        "schema_version": SCHEMA_VERSION,
    }

    result: Dict[str, Any] = {
        "run_id": run_id,
        "status": "completed",
        "run_at_utc": started_at,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "selected_event_id": event_id,
        "top_event_ids": top_event_ids,
        "event": selected_event,
        "decision": decision_obj,
        "payment": payment_obj,
        "premium_quote_usd": premium_quote_usd,
        "value_generated_usd": value_signal["expected_loss_avoided_usd"],
        "cost_usd": value_signal["cost_usd"],
        "llm_observability": llm_observability,
        "roi": value_signal["roi"],
        "narration_text": narration_text,
        "consultant_decision": legacy_consultant,
        "value_signal": legacy_value,
        "payment_result": legacy_payment,
        "vision_report": {
            "vision_report_id": "VR-" + run_id.split("RUN-")[1],
            "event_id": event_id,
            "provider": providers.get("vision", "vision"),
            "model_version": providers.get("vision", "vision"),
            "status": "ok",
            "confidence": _safe_float(decision_obj.get("confidence"), 0.5),
            "summary": "Phase 3 autonomy run used orbital economics and selected event artifacts.",
            "findings": [
                {
                    "code": "EVENT_SELECTED",
                    "severity": "medium",
                    "detail": f"Selected event {event_id} for closed-loop execution.",
                }
            ],
            "generated_at_utc": completed_at,
            "schema_version": SCHEMA_VERSION,
        },
        "earth_impact": impact_result,
        "expected_loss_adjusted_usd": expected_loss_adjusted,
        "decision_mode": decision_mode,
        "trend_metrics": trend_metrics,
        "defer_until_utc": defer_until_utc,
        "maneuver_plan": maneuver_plan,
        "voice": {
            "provider": voice_result.get("provider", providers.get("voice", "elevenlabs")),
            "status": voice_result.get("status", "skipped"),
            "audio_url": voice_result.get("audio_url"),
            "script_text": narration_text,
        },
        "refs": {
            "top_conjunctions_path": str(top_path_str),
            "cesium_snapshot_path": str(snapshot_path_str),
            "maneuver_plans_path": str(plans_path_str) if plans_path_str else None,
        },
        "ledger": {
            "path": str(ledger_path),
            "summary_path": str(ledger_summary_path),
            "summary": ledger_summary,
        },
        "errors": [],
        "model_version": AUTONOMY_MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
    }

    autonomy_latest_path = _resolve_path(
        os.environ.get("ASTRA_AUTONOMY_LATEST_PATH"),
        "astragaurd/data/processed/autonomy_run_result_latest.json",
    )
    _write_json(autonomy_latest_path, result)

    artifacts = latest_manifest.get("artifacts") or {}
    updated_artifacts = dict(artifacts)
    updated_artifacts["autonomy_run_result"] = ArtifactEntry(
        path=_artifact_path_for_manifest(autonomy_latest_path),
        schema_version=SCHEMA_VERSION,
        model_version=AUTONOMY_MODEL_VERSION,
        sha256=_sha256_file(autonomy_latest_path),
        generated_at_utc=_iso_utc_now(),
    ).__dict__
    updated_manifest = ArtifactsLatest(
        generated_at_utc=_iso_utc_now(),
        latest_run_id=run_id,
        artifacts=updated_artifacts,
    )
    _write_json(ARTIFACTS_LATEST_PATH, updated_manifest.to_dict())

    emit_event(
        PROCESSED_DIR,
        "run_autonomy_loop.completed",
        {
            "run_id": run_id,
            "event_id": event_id,
            "decision": decision,
            "llm_observability": llm_observability,
        },
    )
    LOGGER.info("Autonomy run completed run_id=%s event_id=%s decision=%s", run_id, event_id, decision)

    return {"run_id": run_id, "status": "completed", "result": result, "schema_version": SCHEMA_VERSION}


@app.get("/artifacts/latest")
def get_artifacts_latest() -> Dict[str, Any]:
    return _load_artifacts_latest()


@app.get("/artifacts/top-conjunctions")
def get_top_conjunctions(include_plans: int = Query(0, ge=0, le=1)) -> Dict[str, Any]:
    if not TOP_CONJUNCTIONS_PATH.exists():
        raise HTTPException(status_code=404, detail={"schema_version": SCHEMA_VERSION, "error": "TOP_CONJUNCTIONS_NOT_FOUND"})
    top_payload = _read_json(TOP_CONJUNCTIONS_PATH)
    if int(include_plans) != 1:
        return top_payload

    manifest = _load_artifacts_latest()
    plans_by_event_id = _load_maneuver_plans_from_manifest(manifest)
    events = top_payload.get("events") or []
    enriched_events: List[Dict[str, Any]] = []
    for event in events:
        event_payload = dict(event) if isinstance(event, dict) else {}
        plan_entry, _ = _resolve_plan_entry_for_event(event_payload, plans_by_event_id)
        trend_metrics = plan_entry.get("trend_metrics") if isinstance(plan_entry.get("trend_metrics"), dict) else {}
        maneuver_plan = plan_entry.get("maneuver_plan") if isinstance(plan_entry.get("maneuver_plan"), dict) else {}
        event_payload["decision_mode_hint"] = plan_entry.get("decision_mode_hint")
        event_payload["defer_until_utc"] = plan_entry.get("defer_until_utc")
        event_payload["trend_pc_peak"] = trend_metrics.get("pc_peak")
        event_payload["trend_pc_slope"] = trend_metrics.get("pc_slope")
        event_payload["trend_pc_stability"] = trend_metrics.get("pc_stability")
        event_payload["plan_delta_v_mps"] = maneuver_plan.get("delta_v_mps")
        event_payload["plan_burn_time_utc"] = maneuver_plan.get("burn_time_utc")
        enriched_events.append(event_payload)
    top_payload["events"] = enriched_events
    return top_payload


@app.get("/artifacts/maneuver-plans")
def get_maneuver_plans() -> Dict[str, Any]:
    if not MANEUVER_PLANS_PATH.exists():
        raise HTTPException(status_code=404, detail={"schema_version": SCHEMA_VERSION, "error": "MANEUVER_PLANS_NOT_FOUND"})
    return _read_json(MANEUVER_PLANS_PATH)


@app.get("/artifacts/cesium-snapshot")
def get_cesium_snapshot() -> FileResponse:
    if not CESIUM_SNAPSHOT_PATH.exists():
        raise HTTPException(status_code=404, detail={"schema_version": SCHEMA_VERSION, "error": "CESIUM_SNAPSHOT_NOT_FOUND"})
    return FileResponse(str(CESIUM_SNAPSHOT_PATH), media_type="application/json")


@app.post("/run-autonomy-loop")
def run_autonomy_loop(payload: Dict[str, Any], event_index: int = Query(0, ge=0)) -> Dict[str, Any]:
    return run_autonomy_loop_internal(payload, event_index=event_index)


if __name__ == "__main__":
    demo_payload = _build_loop_request()
    print(json.dumps(run_autonomy_loop_internal(demo_payload), indent=2))
