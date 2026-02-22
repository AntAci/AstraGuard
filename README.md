# AstraGuard

Autonomous maneuver-tax optimization stack: ingest TLEs, screen conjunction risk, run an agentic decision loop (IGNORE/DEFER/MANEUVER, with optional contingency coverage), and minimize recurring operations cost with auditable economics.

## Business Model (2026 Pivot)

AstraGuard is positioned as an **operations-cost optimization platform** for satellite operators, not only a catastrophic-collision alerting tool.

- **Core value promise:** reduce recurring conjunction-response cost (unnecessary burns, fuel depletion, schedule disruption).
- **Primary KPI:** maneuver tax avoided and delta-v saved per operator fleet.
- **Commercial model:** software subscription + usage tiering by monitored spacecraft / autonomy runs.
- **Buyer:** mission operations teams and constellation risk owners who need deterministic, explainable action policies.
- **Product wedge:** trend-gated defer + minimum-delta-v planning with an auditable ledger and API-first integration.

## Problem Context (Why This Matters)

Orbital risk is no longer theoretical; congestion and debris growth now create a daily operations problem.

- **~44,870** objects are regularly tracked in catalogues maintained by space surveillance networks (ESA SDUP, **last update: 16 Jan 2026**).
- ESA estimates **>1.2 million** debris objects larger than 1 cm and **~140 million** between 1 mm and 1 cm, both capable of damaging spacecraft.
- Estimated fragmentation incidents are now **>650** (breakups, explosions, collisions, anomalous fragmentation events).
- In **2024 alone**, major and minor fragmentation events added **at least 3,000 tracked objects** (ESA Space Environment Report 2025).
- U.S. Space Force 18th SDS reports tracking **>47,000** man-made objects via Space-Track, underscoring global SSA workload at scale.

These are exactly the conditions AstraGuard targets: high-volume conjunction screening, deterministic cost-aware decisioning, and fast operational response.

### Why Now (2026)

The market has crossed a practical tipping point: object counts are rising, fragmentation is compounding, and operators now face recurring conjunction decisions under tight time windows. AstraGuard is built for this operating regime: automate screening, suppress spiky false positives, and optimize action economics (ignore, defer, maneuver, optional contingency coverage) with auditable operator-ready UX.

### Sources

- ESA Space Environment Statistics (SDUP): https://sdup.esoc.esa.int/discosweb/statistics/
- ESA Space Environment Report 2025: https://www.esa.int/Space_Safety/Space_Debris/ESA_Space_Environment_Report_2025
- U.S. Space Force 18th SDS Fact Sheet: https://www.spaceforce.mil/About-Us/Fact-Sheets/Fact-Sheet-Display/Article/3740012/18th-space-defense-squadron/

## Agentic AI System

AstraGuard runs an **agentic autonomy loop** with a strict LLM consultant:

1. Ingest and screen conjunction candidates (`scripts/fetch_tles.py`, `scripts/run_screening.py`).
2. Compute trend-gated risk state (`IGNORE` / `DEFER` / `MANEUVER` eligibility).
3. Generate minimum-delta-v maneuver options when eligible.
4. Evaluate economics (expected loss, maneuver cost, optional contingency coverage).
5. Ask a consultant model for rationale and recommendation (`packages/brain/consultant.py`).
6. Apply provider output normalization and execute selected action path.
7. Emit auditable outputs: decision, reason code, actions, value signal, ledger, telemetry.

LLM providers supported in the API loop:
- Anthropic Claude (config via `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`)
- Google Gemini (config via `GEMINI_API_KEY`, `GEMINI_MODEL`)
- No fallback path in strict mode: if provider output is unavailable/invalid, the run fails explicitly.
- No deterministic override guardrails: consultant decision is authoritative for action mode selection.

Optional external agents:
- Stripe for contingency coverage/payment execution
- ElevenLabs for voice briefing narration
- OTLP/Phoenix for tracing and observability

For hackathon demos, the web app also supports a deterministic frontend-only scenario:
- `VITE_DEMO_MODE=1 npm run dev`

## Core Capabilities

- TLE ingest from CelesTrak into SQLite (`data/processed/tles.sqlite`)
- 72h conjunction screening with SGP4 propagation + coarse/fine refinement
- Ranked risk artifacts (`top_conjunctions.json/.csv`)
- Trend-gated local risk analysis around TCA (`pc_series`, peak/slope/stability metrics)
- First-class `DEFER` windowing for non-sustained or too-early risk profiles
- Deterministic maneuver planner (timing + RTN direction) selecting minimum feasible delta-v
- Cesium-ready ECEF snapshot export (`cesium_orbits_snapshot.json`)
- Maneuver planning artifact export (`maneuver_plans.json`)
- Contract-locked artifact manifest (`artifacts_latest.json`)
- FastAPI autonomy loop with:
  - LLM consultant (Claude/Gemini, strict no-fallback mode)
  - Earth impact scoring
  - Optional Stripe-backed contingency coverage flow
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
- **Trend-gated risk classification** from local Pc time-series around TCA with `DEFER`/`MANEUVER` gating (`packages/orbit/trend.py`).
- **Minimal delta-v maneuver optimization** across candidate burn times and RTN directions (`packages/orbit/maneuver.py`).
- **ECI -> ECEF frame transform** using GMST for Cesium-compatible globe rendering (`scripts/run_screening.py`).
- **Contract-first artifact pipeline** with schema/model versioning and manifest-addressable outputs (`packages/contracts/*`, `artifacts_latest.json`).
- **Hybrid autonomy policy**: deterministic economics + LLM rationale/decision in strict provider mode (`apps/api/main.py`, `packages/brain/consultant.py`).
- **Earth-impact scoring** to adjust expected loss with geospatial context (`packages/earth/impact.py`).
- **Commerce + policy controls** for optional contingency coverage and maneuver-tax economics with ROI and ledger telemetry (`packages/commerce/*`, `packages/telemetry/*`).
- **Operational observability** via structured event telemetry, value signals, and optional OTLP/Phoenix tracing (`packages/telemetry/*`).

## Data Usage

### Data Inputs

- Public orbital catalog data (TLEs) from CelesTrak groups (for example `ACTIVE`, `COSMOS-1408-DEBRIS`, `FENGYUN-1C-DEBRIS`, `IRIDIUM-33-DEBRIS`, `COSMOS-2251-DEBRIS`).
- Runtime configuration and policy parameters from environment variables (risk thresholds, sigma model, maneuver constraints, pricing assumptions).

### Derived Data (Generated by AstraGuard)

- Propagated states and conjunction candidates.
- Ranked conjunction artifacts (`top_conjunctions.json/.csv`).
- Trend and maneuver-plan artifacts (`maneuver_plans.json`).
- Visualization snapshot (`cesium_orbits_snapshot.json`).
- Autonomy outputs (`autonomy_run_result_latest.json`), telemetry events, and value ledger records.

### How Data Is Used In Decisions

- Collision-risk features (`pc_assumed`, miss distance, relative speed) drive ranking and tiering.
- Trend metrics (`pc_peak`, slope, stability, time-to-TCA) gate `DEFER` vs `MANEUVER`.
- Maneuver planner data (burn time, direction, delta-v, feasibility) determines executable action quality.
- Economics data (asset value, expected loss, maneuver cost, optional coverage cost) drives ROI-aware action selection.

### External Data Sharing (Only When Enabled)

- LLM providers receive decision context for rationale generation.
- Stripe receives payment metadata only for coverage/payment flows.
- ElevenLabs receives narration text only for voice synthesis.
- OTLP/Phoenix receives telemetry spans/events when tracing is enabled.

By default, artifacts are stored locally under `astragaurd/data/processed`.

## Hackathon Demo Walkthrough (Real Data Example)

Example run captured from `astragaurd/data/processed/autonomy_run_result_latest.json`
(`run_id: RUN-20260222083645`, generated on February 22, 2026):

### 1. Input Event

- `event_id`: `EVT-31698-36605-2026-02-22T15:49:00Z`
- `pc_assumed`: `3.689e-03`
- `miss_distance_m`: `94.03`
- `tca_utc`: `2026-02-22T15:49:00Z`

### 2. Decision Output

- `decision_mode`: `MANEUVER`
- `decision_reason_code`: `SUSTAINED_RISK`
- `confidence`: `0.95`
- `recommended_actions`: `schedule_maneuver`, `monitor_24h`

### 3. Maneuver Timing Advantage

- Selected burn delta-v: `0.0105 m/s`
- `early_vs_late_ratio`: `0.0208x`
- Derived late-baseline delta-v: `0.5033 m/s`
- Timing savings vs late baseline: `0.4928 m/s` (`97.9%` lower delta-v)

### 4. Economics

- Immediate maneuver cost: `$5,000.00`
- Adjusted expected loss at risk state: `$832,337.82`
- Estimated loss avoided: `$832,337.82`
- ROI: `166.5x`

### 5. Minimal Artifact Snippet

```json
{
  "selected_event_id": "EVT-31698-36605-2026-02-22T15:49:00Z",
  "decision_mode": "MANEUVER",
  "decision": { "decision_reason_code": "SUSTAINED_RISK", "confidence": 0.95 },
  "maneuver_plan": {
    "burn_time_utc": "2026-02-21T15:49:00Z",
    "direction": "+T",
    "delta_v_mps": 0.010485783026016089,
    "early_vs_late_ratio": 0.020833333333333336
  },
  "cost_usd": 5000.0,
  "value_generated_usd": 832337.822693037,
  "roi": 166.4675645386074
}
```

### 6. Reproduce This Flow

```bash
cd astragaurd
python scripts/fetch_tles.py
python scripts/verify_tles.py
python scripts/run_screening.py
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal:

```bash
cd astragaurd/apps/web
npm run dev
```

Then run the optimization loop from the UI (select top risk event or specific `event_id`).

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

Note: in strict no-fallback mode, `POST /run-autonomy-loop` requires at least one consultant key:
`ANTHROPIC_API_KEY` or `GEMINI_API_KEY`.

### 5. Start Web UI

```bash
cd astragaurd/apps/web
npm run dev
```

### 6. Optional: Hackathon Demo UI (curated data)

```bash
cd astragaurd/apps/web
VITE_DEMO_MODE=1 npm run dev
```

- Web: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

## API Surface

- `GET /artifacts/latest`
- `GET /artifacts/top-conjunctions`
- `GET /artifacts/top-conjunctions?include_plans=1`
- `GET /artifacts/cesium-snapshot`
- `GET /artifacts/maneuver-plans`
- `POST /run-autonomy-loop`

Frontend uses Vite proxy `/api -> http://localhost:8000`.

## Core Artifacts

- `astragaurd/data/processed/tle_manifest_latest.json`
- `astragaurd/data/processed/top_conjunctions.json`
- `astragaurd/data/processed/top_conjunctions.csv`
- `astragaurd/data/processed/cesium_orbits_snapshot.json`
- `astragaurd/data/processed/maneuver_plans.json`
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

### Trend gate + maneuver planning

- `ASTRA_TREND_WINDOW_MINUTES` (default `30`)
- `ASTRA_TREND_CADENCE_SECONDS` (default `60`)
- `ASTRA_TREND_THRESHOLD` (default `1e-5`)
- `ASTRA_TREND_DEFER_HOURS` (default `24`)
- `ASTRA_TREND_CRITICAL_OVERRIDE` (default `1e-3`)
- `ASTRA_COV_MODEL` (`legacy` or `anisotropic_rtn`, default `anisotropic_rtn`)
- `ASTRA_SIGMA_BASE_PAYLOAD_R_M`, `ASTRA_SIGMA_BASE_PAYLOAD_T_M`, `ASTRA_SIGMA_BASE_PAYLOAD_N_M`
- `ASTRA_SIGMA_BASE_DEBRIS_R_M`, `ASTRA_SIGMA_BASE_DEBRIS_T_M`, `ASTRA_SIGMA_BASE_DEBRIS_N_M`
- `ASTRA_SIGMA_T_GROWTH_MPS` (default `0.02`)
- `ASTRA_MISS_DISTANCE_TARGET_M` (default `1000`, runtime floor `max(1000, 3*hbr_m)`)
- `ASTRA_MAX_DELTA_V_MPS` (default `0.5`)
- `ASTRA_CANDIDATE_BURN_OFFSETS_H` (default `24,12,6,2`)
- `ASTRA_LATE_BURN_MINUTES` (default `30`)

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

### Deterministic trend+plan demo

```bash
cd astragaurd
python scripts/demo_maneuver_reduction.py
```

## Decision Modes

- `IGNORE`: no payment action, monitor only
- `DEFER`: postpone action and re-evaluate at `defer_until_utc`
- `INSURE`: optional contingency-coverage action (quote/enforce policy, then Stripe purchase path)
- `MANEUVER`: operational action path with configured maneuver cost

## Notes

- If API shows `ARTIFACTS_MISSING`, run screening first.
- If API shows offline in web UI, start Uvicorn on port `8000`.
- `data/processed` files are runtime artifacts; regenerate as needed.
