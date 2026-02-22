#!/usr/bin/env python3
"""Event contracts for conjunction screening outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class ConjunctionEvent:
    event_id: str
    primary_id: int
    secondary_id: int
    tca_utc: str
    miss_distance_m: float
    relative_speed_mps: float
    pc_assumed: float
    risk_score: float
    window_start_utc: str
    window_end_utc: str
    model_version: str
    assumptions: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
