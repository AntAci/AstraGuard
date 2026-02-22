#!/usr/bin/env python3
"""Contracts for artifacts latest manifest payload."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional

from packages.contracts.versioning import SCHEMA_VERSION


@dataclass
class ArtifactEntry:
    path: str
    schema_version: str
    model_version: str
    sha256: str
    generated_at_utc: str


@dataclass
class ArtifactsLatest:
    generated_at_utc: str
    latest_run_id: Optional[str]
    artifacts: Dict[str, ArtifactEntry]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self):
        return asdict(self)
