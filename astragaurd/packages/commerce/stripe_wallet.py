#!/usr/bin/env python3
"""Stripe wallet and pricing helpers for Phase 3 autonomy runs."""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple


LOGGER = logging.getLogger(__name__)


def _build_ssl_context() -> ssl.SSLContext:
    """Build SSL context using explicit CA bundle when available."""

    ca_bundle = os.environ.get("ASTRA_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if ca_bundle:
        try:
            return ssl.create_default_context(cafile=ca_bundle)
        except Exception as err:
            LOGGER.warning("Failed to load CA bundle from env (%s): %s", ca_bundle, err)
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _env_float(name: str, default: float) -> float:
    return _safe_float(os.environ.get(name), default)


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = str(raw).strip()
    return value if value else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


def _safe_currency() -> str:
    return _env_str("STRIPE_CURRENCY", "usd").lower()


def quote_premium_usd(event: Dict[str, Any], asset_value_usd: float) -> float:
    """Compute risk-based premium for a conjunction event."""

    p_collision = _safe_float(event.get("p_collision", event.get("pc_assumed", 0.0)), 0.0)
    expected_loss = float(p_collision * max(asset_value_usd, 0.0))

    rate = _env_float("ASTRA_PREMIUM_RATE", 0.02)
    premium_min = _env_float("ASTRA_PREMIUM_MIN_USD", 200.0)
    premium_max = _env_float("ASTRA_PREMIUM_MAX_USD", 20000.0)
    if premium_min > premium_max:
        premium_min, premium_max = premium_max, premium_min

    premium = expected_loss * max(rate, 0.0)
    premium = max(premium_min, min(premium, premium_max))
    return round(float(premium), 2)


def enforce_spend_policy(
    premium_usd: float,
    decision: str,
    policy_ctx: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """Enforce delegated spend policy before any Stripe call."""

    policy = {
        "max_spend_per_run": _env_float("ASTRA_PREMIUM_MAX_USD", 20000.0),
        "allow_insure": True,
        "allow_maneuver": True,
        "ttl_hours": 24,
    }
    if policy_ctx:
        policy.update(policy_ctx)

    decision_upper = str(decision).upper().strip()
    if decision_upper == "INSURE" and not bool(policy["allow_insure"]):
        return False, "INSURE_NOT_ALLOWED"
    if decision_upper == "MANEUVER" and not bool(policy["allow_maneuver"]):
        return False, "MANEUVER_NOT_ALLOWED"
    if premium_usd > _safe_float(policy.get("max_spend_per_run"), 0.0):
        return False, "EXCEEDS_MAX_SPEND_PER_RUN"
    return True, "ALLOWED"


def _stripe_post(secret_key: str, endpoint: str, form_fields: Dict[str, Any], timeout_s: float = 12.0) -> Dict[str, Any]:
    encoded = urllib.parse.urlencode(form_fields).encode("utf-8")
    req = urllib.request.Request(
        url=f"https://api.stripe.com/v1/{endpoint}",
        method="POST",
        data=encoded,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    ssl_context = _build_ssl_context()
    with urllib.request.urlopen(req, timeout=timeout_s, context=ssl_context) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def _attempt_spt_charge(run_id: str, premium_usd: float, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort SPT hook; intentionally isolated to protect baseline Stripe flow."""

    spt_id = _env_str("STRIPE_SPT_ID", "")
    if not spt_id:
        return {"status": "SPT_UNAVAILABLE", "message": "SPT id missing"}

    # Placeholder for future SPT SDK integration.
    return {
        "status": "SPT_UNAVAILABLE",
        "message": f"SPT path requested for {spt_id} but SDK path is not available in this environment",
        "run_id": run_id,
        "amount_usd": premium_usd,
        "metadata_echo": {k: metadata.get(k) for k in ("run_id", "event_id", "decision")},
    }


def execute_insurance_purchase(run_id: str, premium_usd: float, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe Checkout Session or PaymentIntent for micro-insurance purchase."""

    mode = _env_str("STRIPE_MODE", "checkout").strip().lower()
    if mode not in {"checkout", "payment_intent"}:
        mode = "checkout"
    currency = _safe_currency()
    amount_usd = round(float(max(premium_usd, 0.0)), 2)

    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        return {
            "provider": "stripe",
            "status": "MOCKED",
            "mode": mode,
            "amount_usd": amount_usd,
            "currency": currency,
            "id": f"mock_{run_id}",
            "checkout_url": None,
        }

    spt_note: Optional[Dict[str, Any]] = None
    if _env_bool("STRIPE_SPT_TEST_MODE", False) and _env_str("STRIPE_SPT_ID", ""):
        try:
            spt_note = _attempt_spt_charge(run_id, amount_usd, metadata)
        except Exception as err:  # best-effort path must not block normal Stripe flow
            LOGGER.warning("SPT attempt failed, continuing with Stripe checkout: %s", err)
            spt_note = {"status": "SPT_UNAVAILABLE", "message": str(err)}

    amount_cents = int(round(amount_usd * 100))
    meta = {str(k): str(v) for k, v in metadata.items()}

    try:
        if mode == "payment_intent":
            form_fields: Dict[str, Any] = {
                "amount": amount_cents,
                "currency": currency,
            }
            for key, value in meta.items():
                form_fields[f"metadata[{key}]"] = value

            response = _stripe_post(secret_key, "payment_intents", form_fields)
            output = {
                "provider": "stripe",
                "status": "CREATED",
                "mode": "payment_intent",
                "amount_usd": amount_usd,
                "currency": currency,
                "id": response.get("id"),
                "checkout_url": None,
            }
        else:
            success_url = _env_str("STRIPE_SUCCESS_URL", "http://localhost:5173/?paid=success")
            cancel_url = _env_str("STRIPE_CANCEL_URL", "http://localhost:5173/?paid=cancel")
            form_fields = {
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items[0][price_data][currency]": currency,
                "line_items[0][price_data][product_data][name]": "AstraGuard Micro-Insurance (24h)",
                "line_items[0][price_data][unit_amount]": amount_cents,
                "line_items[0][quantity]": 1,
            }
            for key, value in meta.items():
                form_fields[f"metadata[{key}]"] = value

            response = _stripe_post(secret_key, "checkout/sessions", form_fields)
            output = {
                "provider": "stripe",
                "status": "CREATED",
                "mode": "checkout_session",
                "amount_usd": amount_usd,
                "currency": currency,
                "id": response.get("id"),
                "checkout_url": response.get("url"),
            }

        if spt_note:
            output["spt"] = spt_note
        return output
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as err:
        LOGGER.exception("Stripe purchase failed")
        output = {
            "provider": "stripe",
            "status": "FAILED",
            "mode": mode,
            "amount_usd": amount_usd,
            "currency": currency,
            "id": None,
            "checkout_url": None,
            "message": f"{type(err).__name__}: {err}",
        }
        if spt_note:
            output["spt"] = spt_note
        return output
