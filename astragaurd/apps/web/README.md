# AstraGuard Web — Operations UI

Light operations dashboard with a dark Cesium globe for AstraGuard.

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

- Light, high-clarity dashboard shell with restrained deep-blue + teal accents
- Dark Cesium globe with GPU-instanced orbit points (blue = active sats, warm amber = debris)
- Faint Natural Earth land outlines (public domain)
- Time slider — scrub through all propagated timesteps
- Click any conjunction event — globe flies to midpoint with pulsing alert line
- Run Autonomy Loop button — triggers AI decision pipeline, updates right panel
- Mission log — real-time status feed

## Design system

- Token-based theming in `src/styles/global.css` drives palette, typography, spacing, and states.
- Sans-first typography and neutral surfaces keep the UI readable for demos and judging.

## Build

```bash
npm run build
# Output in dist/
```
