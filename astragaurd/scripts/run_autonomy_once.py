#!/usr/bin/env python3
"""Run one AstraGuard autonomy loop locally and print key outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.main import run_autonomy_loop_internal  # noqa: E402
from packages.contracts.versioning import SCHEMA_VERSION  # noqa: E402


def _build_payload(target_event_id: str | None) -> Dict[str, Any]:
    return {
        "request_id": "REQ-LOCAL-AUTONOMY",
        "mode": "live",
        "selection_strategy": "top_risk",
        "target_event_id": target_event_id,
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


def _read_last_line(path: Path) -> str:
    if not path.exists():
        return "<ledger file missing>"
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return "<ledger empty>"
    return lines[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one AstraGuard autonomy loop.")
    parser.add_argument("--event-index", type=int, default=0, help="Index in top_conjunctions events when target_event_id is unset.")
    parser.add_argument("--target-event-id", type=str, default=None, help="Explicit event_id to run.")
    args = parser.parse_args()

    payload = _build_payload(args.target_event_id)
    response = run_autonomy_loop_internal(payload=payload, event_index=args.event_index)
    result = response["result"]

    decision = result.get("decision") or {}
    payment = result.get("payment") or {}
    ledger = result.get("ledger") or {}

    ledger_path = Path(str(ledger.get("path", "")))
    last_line = _read_last_line(ledger_path)

    print("Decision:", decision.get("decision"))
    print("LLM Provider:", decision.get("llm_provider"))
    print("Premium Quote USD:", result.get("premium_quote_usd"))
    print("Stripe Status:", payment.get("status"))
    print("Stripe ID:", payment.get("id"))
    print("Stripe Checkout URL:", payment.get("checkout_url"))
    print("ROI:", result.get("roi"))
    print("Ledger Path:", ledger_path)
    print("Ledger Last Line:", last_line[:500])
    print("Run ID:", response.get("run_id"))
    print("Result JSON:")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
