#!/usr/bin/env python3
"""Normalized commerce/value-layer helpers for Phase 0 API contracts."""

from __future__ import annotations

from datetime import datetime, timezone

from packages.contracts.autonomy import PaymentResult, ValueSignal


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_payment_result(
    payment_result_id: str,
    decision_id: str,
    event_id: str,
    provider: str,
    mode: str,
    payment_enabled: bool,
    amount_usd: float,
    currency: str,
) -> PaymentResult:
    if not payment_enabled:
        status = "skipped"
        payment_intent_id = None
    elif mode == "dry_run":
        status = "dry_run"
        payment_intent_id = None
    else:
        status = "queued"
        payment_intent_id = None

    return PaymentResult(
        payment_result_id=payment_result_id,
        decision_id=decision_id,
        event_id=event_id,
        provider=provider,
        mode=mode,
        status=status,
        amount_usd=float(amount_usd),
        currency=currency,
        payment_intent_id=payment_intent_id,
        processed_at_utc=_iso_utc_now(),
    )


def build_value_signal(
    value_signal_id: str,
    event_id: str,
    provider: str,
    model_version: str,
    pc_assumed: float,
    miss_distance_m: float,
    estimated_cost_usd: float,
) -> ValueSignal:
    # Simple deterministic baseline estimator for Phase 0 boundary locking.
    loss_scale = max(1.0, 5000.0 - float(miss_distance_m))
    estimated_loss_avoided_usd = float(max(1000.0, pc_assumed * 2_000_000.0 + loss_scale * 25.0))
    cost = max(1.0, float(estimated_cost_usd))
    roi = estimated_loss_avoided_usd / cost

    return ValueSignal(
        value_signal_id=value_signal_id,
        event_id=event_id,
        provider=provider,
        model_version=model_version,
        estimated_loss_avoided_usd=estimated_loss_avoided_usd,
        estimated_cost_usd=float(estimated_cost_usd),
        roi_ratio=float(roi),
        confidence=0.6,
        generated_at_utc=_iso_utc_now(),
    )
