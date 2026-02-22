# AstraGuard API

FastAPI backend serving conjunction screening artifacts and the autonomy loop endpoint.

## Setup

```bash
cd astragaurd
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r apps/api/requirements.txt
```

## Run

```bash
# From the astragaurd/ directory:
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Optional: Phoenix Tracing + LLM Cost Config

Set these in `.env` to enable Arize Phoenix-compatible OTLP tracing and token-cost estimates:

```bash
ASTRA_PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
OTEL_SERVICE_NAME=astragaurd-api

# Optional headers for hosted OTLP endpoints:
# OTEL_EXPORTER_OTLP_HEADERS=api_key=YOUR_KEY

# Optional pricing overrides (USD per 1M tokens)
ASTRA_LLM_PRICE_INPUT_PER_M_GEMINI=0.10
ASTRA_LLM_PRICE_OUTPUT_PER_M_GEMINI=0.40
ASTRA_LLM_PRICE_INPUT_PER_M_CLAUDE=3.00
ASTRA_LLM_PRICE_OUTPUT_PER_M_CLAUDE=15.00
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/artifacts/latest` | Full artifacts manifest |
| GET | `/artifacts/top-conjunctions` | Top 5 conjunction events |
| GET | `/artifacts/cesium-snapshot` | Cesium orbit snapshot (streamed) |
| POST | `/run-autonomy-loop` | Execute autonomy decision loop |

Interactive docs: http://localhost:8000/docs
