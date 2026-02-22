# AstraGuard Web — Mission Control UI

Neon Cesium globe + mission control dashboard for AstraGuard.

**Stack:** Vite 5 · React 18 · TypeScript · CesiumJS 1.116

## Prerequisites

API server must be running on `http://localhost:8000`.
See `apps/api/README.md` for setup instructions.

## Setup

```bash
cd astragaurd/apps/web
npm install
npm run dev
# → http://localhost:5173
```

## Features

- Dark Cesium globe with GPU-instanced orbit points (cyan = active sats, pink = debris)
- Faint Natural Earth land outlines (public domain)
- Time slider — scrub through all propagated timesteps
- Click any conjunction event — globe flies to midpoint with pulsing alert line
- Run Autonomy Loop button — triggers AI decision pipeline, updates right panel
- Mission log — real-time status feed

## Build

```bash
npm run build
# Output in dist/
```
