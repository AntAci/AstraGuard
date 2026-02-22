# AstraGuard Phase 0 Contract Freeze

This file is the implementation-side lock for cross-layer boundaries.

## Ownership
- `packages/contracts`: canonical payload contracts and version constants.
- `apps/api`: serves/accepts only contract-compliant payloads.
- `apps/web`: reads contracts from API only.
- `scripts/run_screening.py`: produces orbit artifacts matching contracts.

## Immutable Invariants
1. `schema_version` is required on all top-level payloads.
2. `model_version` is required for model-derived outputs.
3. `event_id` format: `EVT-{primary_id}-{secondary_id}-{tca_utc}`.
4. `primary_id < secondary_id`.
5. Step 2 output groups must be uppercase.
6. Cesium snapshot positions are `ECEF` in `meters` (`positions_ecef_m`).
7. `tca_index_snapshot` indexes into `cesium_orbits_snapshot.times_utc`.
8. `data/processed/artifacts_latest.json` is the canonical latest locator.

## Decision Enum
`IGNORE | MONITOR | INSURE | MANEUVER`

## Artifact Paths
- `data/processed/top_conjunctions.json`
- `data/processed/top_conjunctions.csv`
- `data/processed/cesium_orbits_snapshot.json`
- `data/processed/artifacts_latest.json`
- `data/processed/autonomy_run_result_latest.json` (written by API loop)
