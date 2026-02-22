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

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/artifacts/latest` | Full artifacts manifest |
| GET | `/artifacts/top-conjunctions` | Top 5 conjunction events |
| GET | `/artifacts/cesium-snapshot` | Cesium orbit snapshot (streamed) |
| POST | `/run-autonomy-loop` | Execute autonomy decision loop |

Interactive docs: http://localhost:8000/docs
