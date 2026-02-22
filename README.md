# AstraGuard

Autonomous orbital risk operations stack: ingest TLEs, screen conjunction risk, run an AI decision loop (IGNORE/INSURE/MANEUVER), and visualize everything in a mission-control frontend.

## Problem Context (Why This Matters)

Orbital risk is no longer theoretical; congestion and debris growth now create a daily operations problem.

- **~44,870** objects are regularly tracked in catalogues maintained by space surveillance networks (ESA SDUP, **last update: 16 Jan 2026**).
- ESA estimates **>1.2 million** debris objects larger than 1 cm and **~140 million** between 1 mm and 1 cm, both capable of damaging spacecraft.
- Estimated fragmentation incidents are now **>650** (breakups, explosions, collisions, anomalous fragmentation events).
- In **2024 alone**, major and minor fragmentation events added **at least 3,000 tracked objects** (ESA Space Environment Report 2025).
- U.S. Space Force 18th SDS reports tracking **>47,000** man-made objects via Space-Track, underscoring global SSA workload at scale.

These are exactly the conditions AstraGuard targets: high-volume conjunction screening, decision support under uncertainty, and fast operational response.

### Why Now (2026)

The market has crossed a practical tipping point: object counts are rising, fragmentation is compounding, and operators now face recurring conjunction decisions under tight time windows. AstraGuard is built for this exact operating regime: automate screening, prioritize the highest-risk events, and turn analysis into action (monitor, insure, maneuver) with auditable economics and operator-ready UX.

### Sources

- ESA Space Environment Statistics (SDUP): https://sdup.esoc.esa.int/discosweb/statistics/
- ESA Space Environment Report 2025: https://www.esa.int/Space_Safety/Space_Debris/ESA_Space_Environment_Report_2025
- U.S. Space Force 18th SDS Fact Sheet: https://www.spaceforce.mil/About-Us/Fact-Sheets/Fact-Sheet-Display/Article/3740012/18th-space-defense-squadron/

## Core Capabilities

- TLE ingest from CelesTrak into SQLite (`data/processed/tles.sqlite`)
- 72h conjunction screening with SGP4 propagation + coarse/fine refinement
- Ranked risk artifacts (`top_conjunctions.json/.csv`)
- Cesium-ready ECEF snapshot export (`cesium_orbits_snapshot.json`)
- Contract-locked artifact manifest (`artifacts_latest.json`)
- FastAPI autonomy loop with:
  - LLM consultant (Claude/Gemini + deterministic fallback)
  - Earth impact scoring
  - Stripe premium quoting/purchase flow
  - Value-signal and ROI ledgering
  - Optional ElevenLabs voice briefing
  - Optional OpenTelemetry tracing to Phoenix/OTLP
- React + Cesium mission-control UI with timestep slider and event-driven globe focus

## Techniques Used

- **SGP4 orbit propagation** over configurable horizons (`packages/orbit/propagate.py`).
- **Spatial voxel hashing** for candidate pair generation at each timestep (`packages/orbit/spatial_hash.py`).
- **Two-stage conjunction detection**:
  - coarse sweep on propagated states
  - local high-resolution TCA refinement with smaller `dt_refine_s` (`packages/orbit/conjunction.py`).
- **Probabilistic risk scoring** using encounter probability assumptions (`pc_assumed`) and pairwise sigma modeling (`packages/orbit/risk.py`).
- **ECI -> ECEF frame transform** using GMST for Cesium-compatible globe rendering (`scripts/run_screening.py`).
- **Contract-first artifact pipeline** with schema/model versioning and manifest-addressable outputs (`packages/contracts/*`, `artifacts_latest.json`).
- **Hybrid autonomy policy**: LLM consultant (Claude/Gemini) with deterministic fallback guardrail path (`apps/api/main.py`, `packages/brain/consultant.py`).
- **Earth-impact scoring** to adjust expected loss with geospatial context (`packages/earth/impact.py`).
- **Commerce + policy controls** for insurance checkout / maneuver economics with ROI and ledger telemetry (`packages/commerce/*`, `packages/telemetry/*`).
- **Operational observability** via structured event telemetry, value signals, and optional OTLP/Phoenix tracing (`packages/telemetry/*`).

## Conjunction Events: Definition, Creation, Ranking

### Definition

A **Conjunction Event** is one refined close-approach candidate between:

- `ACTIVE` and `ACTIVE`, or
- `ACTIVE` and `DEBRIS`

represented by:

- `event_id` (`EVT-{primary_id}-{secondary_id}-{tca_utc}`)
- object IDs (`primary_id`, `secondary_id`)
- `tca_utc` + `tca_index_snapshot`
- `miss_distance_m`
- `relative_speed_mps`
- `pc_assumed` (collision probability estimate)
- `risk_score` (currently set equal to `pc_assumed`)
- encounter window bounds + model assumptions

Contract shape is defined in `astragaurd/packages/contracts/events.py`.

### Creation Conditions (Pipeline)

In `scripts/run_screening.py`, events are created with this flow:

1. Load TLE objects (default capped at `--max-objects 3000`) for selected groups.
2. Propagate with SGP4 for `--horizon-hours 72` at `--dt 600` seconds.
3. Generate candidate pairs via spatial voxel hashing (`--voxel-km 50`).
4. Refine each unique pair around local coarse minima using higher resolution (`--dt-refine 60`, ±2 coarse steps).
5. Keep only pairs where at least one object is `ACTIVE` (`ACTIVE/ACTIVE` and `ACTIVE/DEBRIS` allowed; `DEBRIS/DEBRIS` excluded).
6. Build one event per remaining refined pair:
   - enforce canonical ordering `primary_id < secondary_id`
   - compute pair sigma from group classes (`sigma_payload_m=200`, `sigma_debris_m=500`)
   - compute `pc_assumed` with isotropic assumed-covariance + hard-body radius (`hbr_m=25`)
   - set `risk_score = pc_assumed`

There is no separate hard threshold after refinement; ranking determines which events are kept in the top output.

### Ranking Conditions

Events are sorted by:

1. `risk_score` descending
2. `miss_distance_m` ascending (tie-break)

Then only `top_k` are written to `top_conjunctions` artifacts (default `--top-k 20`).

### UI Risk Tiers

The backend artifact stores `risk_score`/`pc_assumed`; UI risk tiers are inferred client-side for display:

- `CRITICAL` if `pc_assumed >= 1e-3`
- `HIGH` if `pc_assumed >= 1e-4`
- `MEDIUM` if `pc_assumed >= 1e-5`
- otherwise `LOW`

## Architecture

1. `scripts/fetch_tles.py` pulls catalog groups and upserts SQLite.
2. `scripts/run_screening.py` propagates objects, scores conjunctions, and writes artifacts.
3. `apps/api/main.py` serves artifacts and executes the autonomy loop.
4. `apps/web` consumes API payloads and renders mission control.

## Repository Layout

- `astragaurd/apps/api`: FastAPI app and API docs
- `astragaurd/apps/web`: Vite + React + TypeScript frontend
- `astragaurd/packages/contracts`: canonical payload contracts/version constants
- `astragaurd/packages/orbit`: propagation, candidate generation, conjunction refinement, risk math
- `astragaurd/packages/brain`: consultant decision engine
- `astragaurd/packages/commerce`: Stripe wallet and spend-policy enforcement
- `astragaurd/packages/earth`: geospatial Earth-impact scoring
- `astragaurd/packages/voice`: ElevenLabs TTS integration
- `astragaurd/packages/telemetry`: event sink, ledger metrics, LLM cost, OTLP tracing bootstrap
- `astragaurd/scripts`: ingest/screening/run helpers
- `astragaurd/data/raw`: raw fetched TLE text files
- `astragaurd/data/processed`: generated artifacts, manifests, telemetry, ledger

## Quickstart

### 1. Python backend + pipeline setup

```bash
cd astragaurd
python -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
pip install requests numpy sgp4 certifi
```

### 2. Frontend setup

```bash
cd apps/web
npm install
```

### 3. Build baseline orbital artifacts

```bash
cd astragaurd
python scripts/fetch_tles.py
python scripts/verify_tles.py
python scripts/run_screening.py
```

### 4. Start API

```bash
cd astragaurd
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start Web UI

```bash
cd astragaurd/apps/web
npm run dev
```

- Web: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

## API Surface

- `GET /artifacts/latest`
- `GET /artifacts/top-conjunctions`
- `GET /artifacts/cesium-snapshot`
- `POST /run-autonomy-loop`

Frontend uses Vite proxy `/api -> http://localhost:8000`.

## Core Artifacts

- `astragaurd/data/processed/tle_manifest_latest.json`
- `astragaurd/data/processed/top_conjunctions.json`
- `astragaurd/data/processed/top_conjunctions.csv`
- `astragaurd/data/processed/cesium_orbits_snapshot.json`
- `astragaurd/data/processed/artifacts_latest.json`
- `astragaurd/data/processed/autonomy_run_result_latest.json`
- `astragaurd/data/processed/telemetry_events.jsonl`
- `astragaurd/data/processed/agent_ledger.jsonl`
- `astragaurd/data/processed/agent_ledger_summary.json`

## Contract Invariants (Core)

Defined in `astragaurd/packages/contracts/PHASE0_SPEC.md`.

- `schema_version` required on top-level payloads
- `model_version` required on model-derived payloads
- `event_id` format locked: `EVT-{primary_id}-{secondary_id}-{tca_utc}`
- `primary_id < secondary_id`
- Snapshot coordinates are ECEF meters
- `tca_index_snapshot` indexes snapshot timeline
- Canonical latest locator is `artifacts_latest.json`

## Environment Variables

### LLM + consultant

- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `ANTHROPIC_MODEL` (default `claude-3-5-sonnet-latest`)
- `GEMINI_MODEL` (default `gemini-2.5-flash`)
- `ASTRA_LLM_TIMEOUT_S` (default `10`)
- `ASTRA_LLM_PRICE_INPUT_PER_M_CLAUDE` / `ASTRA_LLM_PRICE_OUTPUT_PER_M_CLAUDE`
- `ASTRA_LLM_PRICE_INPUT_PER_M_GEMINI` / `ASTRA_LLM_PRICE_OUTPUT_PER_M_GEMINI`

### Economics + value

- `ASTRA_ASSET_VALUE_ACTIVE_USD` (default `200000000`)
- `ASTRA_ASSET_VALUE_DEBRIS_USD` (default `1000000`)
- `ASTRA_MANEUVER_COST_USD` (default `5000`)

### Stripe / payments

- `STRIPE_SECRET_KEY`
- `STRIPE_MODE` (`checkout` or `payment_intent`, default `checkout`)
- `STRIPE_CURRENCY` (default `usd`)
- `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL`
- `ASTRA_PREMIUM_RATE` (default `0.02`)
- `ASTRA_PREMIUM_MIN_USD` (default `200`)
- `ASTRA_PREMIUM_MAX_USD` (default `20000`)
- `STRIPE_SPT_TEST_MODE`
- `STRIPE_SPT_ID`

### Voice

- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `ELEVENLABS_MODEL_ID`

### Telemetry / tracing

- `ASTRA_PHOENIX_ENABLED` (`true|false`)
- `PHOENIX_COLLECTOR_ENDPOINT`
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_HEADERS`
- `OTEL_SERVICE_NAME` (default `astragaurd-api`)

### Paths / TLS

- `ASTRA_AUTONOMY_LATEST_PATH`
- `ASTRA_AGENT_LEDGER_PATH`
- `ASTRA_AGENT_LEDGER_SUMMARY_PATH`
- `ASTRA_CA_BUNDLE`
- `SSL_CERT_FILE`

## Useful Commands

### Run one autonomy loop locally (without hitting HTTP)

```bash
cd astragaurd
python scripts/run_autonomy_once.py --event-index 0
```

### Build frontend

```bash
cd astragaurd/apps/web
npm run build
```

## Decision Modes

- `IGNORE`: no payment action, monitor only
- `INSURE`: quote/enforce policy, then Stripe purchase path
- `MANEUVER`: operational action path with configured maneuver cost

## Notes

- If API shows `ARTIFACTS_MISSING`, run screening first.
- If API shows offline in web UI, start Uvicorn on port `8000`.
- `data/processed` files are runtime artifacts; regenerate as needed.
