#!/usr/bin/env python3
"""Consultant decision engine for Phase 3 autonomy runs."""

from __future__ import annotations

import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)

_DECISIONS = {"IGNORE", "INSURE", "MANEUVER"}


def _clean_env_key(name: str) -> str:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper.startswith("YOUR_") or "PLACEHOLDER" in upper or "REPLACE" in upper:
        return ""
    return raw


def _anthropic_key() -> str:
    key = _clean_env_key("ANTHROPIC_API_KEY")
    if key and not key.startswith("sk-ant-"):
        LOGGER.warning("Ignoring ANTHROPIC_API_KEY that does not match expected format")
        return ""
    return key


def _gemini_key() -> str:
    return _clean_env_key("GEMINI_API_KEY")


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _extract_json_substring(text: str) -> Optional[str]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _fallback_policy(expected_loss_usd: float, premium_quote_usd: float, maneuver_cost_usd: float) -> str:
    premium_ref = max(premium_quote_usd, 1e-9)
    if expected_loss_usd >= premium_ref * 3.0:
        return "INSURE"
    if expected_loss_usd >= maneuver_cost_usd:
        return "MANEUVER"
    return "IGNORE"


def _fallback_decision(
    expected_loss_usd: float,
    var_usd: float,
    premium_quote_usd: float,
    maneuver_cost_usd: float,
    reason: str,
) -> Dict[str, Any]:
    decision = _fallback_policy(expected_loss_usd, premium_quote_usd, maneuver_cost_usd)
    return {
        "decision": decision,
        "expected_loss_usd": float(expected_loss_usd),
        "var_usd": float(var_usd),
        "confidence": 0.72,
        "rationale": [
            "Fallback policy selected due to provider unavailability or invalid response.",
            reason,
            (
                f"Rule path: expected_loss={expected_loss_usd:.2f}, "
                f"premium={premium_quote_usd:.2f}, maneuver={maneuver_cost_usd:.2f}"
            ),
        ],
        "llm_provider": "fallback",
    }


def _build_prompt(event: Dict[str, Any], economics: Dict[str, float]) -> str:
    payload = {
        "event": {
            "event_id": event.get("event_id"),
            "tca_utc": event.get("tca_utc"),
            "primary_id": event.get("primary_id"),
            "secondary_id": event.get("secondary_id"),
            "p_collision": economics["p_collision"],
            "miss_distance_m": economics["miss_distance_m"],
            "relative_speed_mps": economics["relative_speed_mps"],
        },
        "economics": {
            "asset_value_usd": economics["asset_value_usd"],
            "expected_loss_usd": economics["expected_loss_usd"],
            "premium_quote_usd": economics["premium_quote_usd"],
            "maneuver_cost_usd": economics["maneuver_cost_usd"],
        },
        "instructions": [
            "Choose exactly one decision: IGNORE, INSURE, or MANEUVER.",
            "You must return strict JSON only with no markdown fences.",
            "Keep rationale concise and practical for an orbital operations operator.",
            "Confidence must be between 0 and 1.",
        ],
        "response_schema": {
            "decision": "IGNORE|INSURE|MANEUVER",
            "expected_loss_usd": "number",
            "var_usd": "number",
            "confidence": "number_0_to_1",
            "rationale": ["string"],
            "llm_provider": "claude|gemini|fallback",
        },
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _http_json(url: str, headers: Dict[str, str], body: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    req = urllib.request.Request(
        url=url,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
    )
    ssl_context = _build_ssl_context()
    with urllib.request.urlopen(req, timeout=timeout_s, context=ssl_context) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _call_claude(prompt: str, api_key: str, model: str, timeout_s: float) -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 400,
        "temperature": 0,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }
    response = _http_json(url, headers, body, timeout_s)
    content = response.get("content") or []
    if not content:
        raise ValueError("Claude response missing content")
    text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not text:
        raise ValueError("Claude response contained empty text")
    return text


def _call_gemini(prompt: str, api_key: str, model: str, timeout_s: float) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"content-type": "application/json"}
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    response = _http_json(url, headers, body, timeout_s)
    candidates = response.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini response missing candidates")
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text:
        raise ValueError("Gemini response contained empty text")
    return text


def _call_provider_with_retry(provider: str, prompt: str) -> str:
    timeout_s = _safe_float(os.environ.get("ASTRA_LLM_TIMEOUT_S"), 10.0)
    if provider == "claude":
        api_key = _anthropic_key()
        if not api_key:
            raise RuntimeError("claude provider unavailable: ANTHROPIC_API_KEY missing/invalid")
        model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        call = lambda: _call_claude(prompt, api_key, model, timeout_s)
    elif provider == "gemini":
        api_key = _gemini_key()
        if not api_key:
            raise RuntimeError("gemini provider unavailable: GEMINI_API_KEY missing/invalid")
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        call = lambda: _call_gemini(prompt, api_key, model, timeout_s)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    max_attempts = 2
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return call()
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, ValueError) as err:
            last_error = err
            LOGGER.warning("Decision provider call failed (provider=%s, attempt=%s): %s", provider, attempt, err)
    raise RuntimeError(f"{provider} provider failed after retry: {last_error}")


def _parse_model_json(raw_text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    repaired = _extract_json_substring(raw_text)
    if not repaired:
        raise ValueError("No JSON object found in model output")
    repaired = re.sub(r"[\x00-\x1f]", "", repaired)
    parsed = json.loads(repaired)
    if not isinstance(parsed, dict):
        raise ValueError("Parsed output is not a JSON object")
    return parsed


def _normalize_decision(
    parsed: Dict[str, Any],
    provider: str,
    expected_loss_usd: float,
    var_usd: float,
    premium_quote_usd: float,
    maneuver_cost_usd: float,
) -> Dict[str, Any]:
    decision = str(parsed.get("decision", "")).upper().strip()
    if decision not in _DECISIONS:
        raise ValueError(f"Invalid decision: {decision!r}")

    rationale_raw = parsed.get("rationale")
    if isinstance(rationale_raw, list):
        rationale = [str(item) for item in rationale_raw if str(item).strip()]
    elif isinstance(rationale_raw, str) and rationale_raw.strip():
        rationale = [rationale_raw.strip()]
    else:
        rationale = ["Model response did not include rationale; normalized by backend."]

    confidence = _safe_float(parsed.get("confidence"), 0.5)
    confidence = min(1.0, max(0.0, confidence))

    return {
        "decision": decision,
        "expected_loss_usd": float(expected_loss_usd),
        "var_usd": float(var_usd),
        "confidence": float(confidence),
        "rationale": rationale,
        "llm_provider": provider,
    }


def decide(event: Dict[str, Any], asset_ctx: Dict[str, Any], cost_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Decide IGNORE/INSURE/MANEUVER using Claude, Gemini, or deterministic fallback."""

    p_collision = _safe_float(event.get("p_collision", event.get("pc_assumed", 0.0)))
    miss_distance_m = _safe_float(event.get("miss_distance_m", 0.0))
    relative_speed_mps = _safe_float(event.get("relative_speed_mps", 0.0))
    asset_value_usd = _safe_float(asset_ctx.get("asset_value_usd", 0.0))
    premium_quote_usd = _safe_float(cost_ctx.get("premium_quote_usd", 0.0))
    maneuver_cost_usd = _safe_float(cost_ctx.get("maneuver_cost_usd", 0.0))

    expected_loss_usd = float(p_collision * asset_value_usd)
    var_usd = float(expected_loss_usd)

    economics = {
        "p_collision": p_collision,
        "miss_distance_m": miss_distance_m,
        "relative_speed_mps": relative_speed_mps,
        "asset_value_usd": asset_value_usd,
        "expected_loss_usd": expected_loss_usd,
        "premium_quote_usd": premium_quote_usd,
        "maneuver_cost_usd": maneuver_cost_usd,
    }
    prompt = _build_prompt(event, economics)

    provider = "fallback"
    # Gemini is prioritized for this deployment; Claude remains a fallback provider.
    if _gemini_key():
        provider = "gemini"
    elif _anthropic_key():
        provider = "claude"

    if provider == "fallback":
        LOGGER.info("Using consultant fallback decision path (no LLM keys configured)")
        return _fallback_decision(
            expected_loss_usd=expected_loss_usd,
            var_usd=var_usd,
            premium_quote_usd=premium_quote_usd,
            maneuver_cost_usd=maneuver_cost_usd,
            reason="No ANTHROPIC_API_KEY or GEMINI_API_KEY configured.",
        )

    try:
        raw_text = _call_provider_with_retry(provider, prompt)
        parsed = _parse_model_json(raw_text)
        decision = _normalize_decision(
            parsed=parsed,
            provider=provider,
            expected_loss_usd=expected_loss_usd,
            var_usd=var_usd,
            premium_quote_usd=premium_quote_usd,
            maneuver_cost_usd=maneuver_cost_usd,
        )
        LOGGER.info("Consultant decision generated via %s", provider)
        return decision
    except Exception as err:  # broad by design to guarantee run completion
        LOGGER.exception("Consultant provider failed; switching to fallback: %s", err)
        return _fallback_decision(
            expected_loss_usd=expected_loss_usd,
            var_usd=var_usd,
            premium_quote_usd=premium_quote_usd,
            maneuver_cost_usd=maneuver_cost_usd,
            reason=f"Provider failure: {type(err).__name__}: {err}",
        )
