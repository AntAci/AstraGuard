#!/usr/bin/env python3
"""Value-signal computation and append-only ledger persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def compute_value_signal(
    run_id: str,
    event: Dict[str, Any],
    decision: Dict[str, Any],
    asset_value_usd: float,
    expected_loss_usd: float,
    cost_usd: float,
    payment_obj: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute per-run economic value signal for the autonomy loop."""

    decision_value = str(decision.get("decision", "IGNORE")).upper().strip()
    expected_loss = _safe_float(expected_loss_usd, 0.0)
    cost = _safe_float(cost_usd, 0.0)
    if decision_value in {"INSURE", "MANEUVER"}:
        expected_loss_avoided = expected_loss
    else:
        expected_loss_avoided = 0.0

    llm_observability = decision.get("llm_observability")
    if not isinstance(llm_observability, dict):
        llm_observability = {}
    usage = llm_observability.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    llm_cost_usd = _safe_float(llm_observability.get("estimated_cost_usd"), decision.get("llm_cost_usd", 0.0))
    llm_input_tokens = _safe_float(usage.get("input_tokens"), 0.0)
    llm_output_tokens = _safe_float(usage.get("output_tokens"), 0.0)
    llm_total_tokens = _safe_float(usage.get("total_tokens"), llm_input_tokens + llm_output_tokens)

    roi = expected_loss_avoided / max(cost, 1e-9)
    return {
        "run_id": run_id,
        "timestamp_utc": _iso_utc_now(),
        "event_id": event.get("event_id"),
        "primary_id": event.get("primary_id"),
        "secondary_id": event.get("secondary_id"),
        "tca_utc": event.get("tca_utc"),
        "decision": decision_value,
        "asset_value_protected_usd": _safe_float(asset_value_usd, 0.0),
        "expected_loss_usd": expected_loss,
        "expected_loss_avoided_usd": expected_loss_avoided,
        "cost_usd": cost,
        "roi": roi,
        "stripe_status": payment_obj.get("status"),
        "stripe_id": payment_obj.get("id"),
        "llm_provider": decision.get("llm_provider", "unknown"),
        "llm_cost_usd": llm_cost_usd,
        "llm_input_tokens": llm_input_tokens,
        "llm_output_tokens": llm_output_tokens,
        "llm_total_tokens": llm_total_tokens,
    }


def append_ledger_record(record: Dict[str, Any], ledger_path: Path) -> None:
    """Append a single run record to immutable JSONL ledger."""

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True) + "\n")


def _read_ledger(ledger_path: Path) -> List[Dict[str, Any]]:
    if not ledger_path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                records.append(parsed)
        except json.JSONDecodeError:
            continue
    return records


def update_ledger_summary(ledger_path: Path, summary_path: Path) -> Dict[str, Any]:
    """Recompute and persist aggregate ledger summary metrics."""

    records = _read_ledger(ledger_path)
    runs = len(records)
    total_cost = sum(_safe_float(item.get("cost_usd"), 0.0) for item in records)
    total_value = sum(_safe_float(item.get("expected_loss_avoided_usd"), 0.0) for item in records)
    total_llm_cost = sum(_safe_float(item.get("llm_cost_usd"), 0.0) for item in records)
    total_llm_tokens = sum(_safe_float(item.get("llm_total_tokens"), 0.0) for item in records)

    roi_values = []
    for item in records:
        cost = _safe_float(item.get("cost_usd"), 0.0)
        if cost > 0.0:
            roi_values.append(_safe_float(item.get("roi"), 0.0))
    avg_roi = (sum(roi_values) / len(roi_values)) if roi_values else 0.0

    summary = {
        "runs": runs,
        "total_cost_usd": total_cost,
        "total_value_usd": total_value,
        "net_value_usd": total_value - total_cost,
        "avg_roi": avg_roi,
        "total_llm_cost_usd": total_llm_cost,
        "total_llm_tokens": total_llm_tokens,
        "avg_llm_cost_usd_per_run": (total_llm_cost / runs) if runs > 0 else 0.0,
        "updated_at_utc": _iso_utc_now(),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
