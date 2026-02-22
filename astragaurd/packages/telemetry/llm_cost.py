#!/usr/bin/env python3
"""LLM usage normalization and cost estimation utilities."""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional


_DEFAULT_PRICING_PER_M = {
    "claude": {"input": 3.0, "output": 15.0},
    "gemini": {"input": 0.10, "output": 0.40},
    "fallback": {"input": 0.0, "output": 0.0},
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Lightweight token estimate for plain-English prompts/results.
    return max(1, int(math.ceil(len(text) / 4.0)))


def extract_usage(provider_response: Optional[Dict[str, Any]], provider: str) -> Optional[Dict[str, int]]:
    if not isinstance(provider_response, dict):
        return None

    if provider == "claude":
        usage = provider_response.get("usage") or {}
        input_tokens = _safe_int(usage.get("input_tokens"), 0)
        output_tokens = _safe_int(usage.get("output_tokens"), 0)
    elif provider == "gemini":
        usage = provider_response.get("usageMetadata") or {}
        input_tokens = _safe_int(usage.get("promptTokenCount"), 0)
        output_tokens = _safe_int(usage.get("candidatesTokenCount"), 0)
        total_tokens = _safe_int(usage.get("totalTokenCount"), input_tokens + output_tokens)
        if total_tokens <= 0 and (input_tokens > 0 or output_tokens > 0):
            total_tokens = input_tokens + output_tokens
        if input_tokens > 0 or output_tokens > 0 or total_tokens > 0:
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }
        return None
    else:
        return None

    total_tokens = input_tokens + output_tokens
    if input_tokens <= 0 and output_tokens <= 0 and total_tokens <= 0:
        return None
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def estimate_usage_fallback(prompt_text: str, completion_text: str) -> Dict[str, int]:
    input_tokens = _estimate_tokens(prompt_text)
    output_tokens = _estimate_tokens(completion_text)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _pricing_for_provider(provider: str) -> Dict[str, float]:
    provider_key = provider.lower().strip()
    defaults = _DEFAULT_PRICING_PER_M.get(provider_key, {"input": 0.0, "output": 0.0})

    input_price = _safe_float(
        os.environ.get(f"ASTRA_LLM_PRICE_INPUT_PER_M_{provider_key.upper()}"),
        defaults["input"],
    )
    output_price = _safe_float(
        os.environ.get(f"ASTRA_LLM_PRICE_OUTPUT_PER_M_{provider_key.upper()}"),
        defaults["output"],
    )
    return {
        "input_per_million_usd": max(0.0, input_price),
        "output_per_million_usd": max(0.0, output_price),
    }


def compute_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
    del model
    pricing = _pricing_for_provider(provider)
    input_cost = (max(0, input_tokens) / 1_000_000.0) * pricing["input_per_million_usd"]
    output_cost = (max(0, output_tokens) / 1_000_000.0) * pricing["output_per_million_usd"]

    return {
        "estimated_cost_usd": round(input_cost + output_cost, 8),
        "pricing": pricing,
    }


def build_llm_observability(
    provider: str,
    model: str,
    prompt_text: str,
    completion_text: str,
    provider_response: Optional[Dict[str, Any]],
    latency_ms: float,
    trace: Optional[Dict[str, Optional[str]]] = None,
    no_llm_call: bool = False,
) -> Dict[str, Any]:
    if no_llm_call:
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "source": "none"}
        mode = "fallback_policy_no_llm_call"
    else:
        extracted = extract_usage(provider_response, provider)
        if extracted is not None:
            usage = {
                "input_tokens": extracted["input_tokens"],
                "output_tokens": extracted["output_tokens"],
                "total_tokens": extracted["total_tokens"],
                "source": "provider",
            }
            mode = "provider_usage"
        else:
            estimated = estimate_usage_fallback(prompt_text, completion_text)
            usage = {
                "input_tokens": estimated["input_tokens"],
                "output_tokens": estimated["output_tokens"],
                "total_tokens": estimated["total_tokens"],
                "source": "estimated",
            }
            mode = "estimated_tokens"

    pricing_and_cost = compute_cost_usd(provider, model, usage["input_tokens"], usage["output_tokens"])

    return {
        "provider": provider,
        "model": model,
        "latency_ms": round(_safe_float(latency_ms, 0.0), 3),
        "usage": usage,
        "pricing": {
            "input_per_million_usd": pricing_and_cost["pricing"]["input_per_million_usd"],
            "output_per_million_usd": pricing_and_cost["pricing"]["output_per_million_usd"],
            "estimation_mode": mode,
        },
        "estimated_cost_usd": pricing_and_cost["estimated_cost_usd"],
        "trace": {
            "trace_id": (trace or {}).get("trace_id"),
            "span_id": (trace or {}).get("span_id"),
        },
    }
