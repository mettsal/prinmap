# AGENTS.md — prinmap (Urban Fabric Generator)

Operational guide for coding agents. The full product vision lives in
[`DESIGN.md`](./DESIGN.md); **this file is the source of truth for how to build,
run, test, and extend the code.** When the two disagree about *implementation*,
this file wins; when they disagree about *intent*, DESIGN.md wins.

## What this is

A web app to select a geographic rectangle, fetch OSM road data, and
procedurally generate a black-and-white **SVG** of the urban road morphology.
The map is only a viewport for selection — the artwork is generated
algorithmically from vector data on the backend, never screenshotted.

Pipeline: `select bbox → fetch OSM roads → reproject to UTM → simplify → buffer
by road class → union → clip → normalize → render SVG`.

## Layout

```
backend/app/
  main.py            FastAPI app + routes (/health, /api/v1/generate, /api/v1/geocode)
  config.py          Settings (limits, service URLs, canvas size)
  errors.py          FabricError + structured error factories
  models/schemas.py  Pydantic request/response models
  providers/         GeographicDataProvider protocol + OSMProvider (Overpass)
  geometry/          projection.py (UTM), processing.py (the pipeline)
  rendering/         styles.py (FabricStyle + presets), svg.py (renderer)
frontend/src/
  map/               MapLibre viewport + rectangle selection + basemap styles
  selection/         selection types/helpers
  generation/        API client, controls, SVG preview
tests/               geometry / rendering / api  (OSM is mocked — no network)
```

## Stack decisions (important)

- **Backend geo stack is `shapely` + `pyproj` + `requests` — NOT GeoPandas.**
  Chosen to avoid heavy/fragile installs on Windows. The provider returns plain
  `RoadFeature` dataclasses (shapely geometry + road class), not a GeoDataFrame.
  Keep this unless GeoPandas becomes genuinely necessary.
- **OSM access:** Overpass API via `out geom;` (way geometry inline, no node
  resolution). Road classes filtered by a regex in the query.
- **Geocoding:** Nominatim, proxied through the backend (`/api/v1/geocode`) to
  respect the usage policy and set a User-Agent — never call it from the browser.
- **Basemaps:** CARTO raster tiles (`dark_all` / `light_all`) — **no API key**.
- **Projection:** dynamic UTM zone from the bbox centre. Never buffer in degrees.
- **Generation is synchronous** for the MVP. No queue, no DB, no auth.

## Commands

Backend (from `backend/`):
```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (from `frontend/`):
```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api -> :8000
npm run build
```

Tests (from repo root):
```bash
pip install -r backend/requirements.txt pytest
pytest                       # tests/conftest.py puts backend/ on sys.path
```

## Conventions

- Backend: type hints everywhere, `from __future__ import annotations`, small
  pure functions in `geometry/` and `rendering/` that are unit-testable with
  synthetic geometry (no network). Domain failures raise `FabricError`; the API
  layer converts them to `{"error": {"code", "message"}}`.
- Keep the four concerns **independently replaceable**: acquisition (providers/),
  geometry (geometry/), style (rendering/styles.py), output (rendering/svg.py).
- `detail` param is an abstract `0..1` knob → tolerance + class filtering + min
  length. `road_width` is a global multiplier over per-class base widths.
- Frontend: `Selection` is a discriminated union (`type: "bbox"` today).
  `GenerationState` is a tagged union: idle | generating | success | error —
  always reflect it in the UI.
- SVG uses semantic groups (`<g id="background">`, `<g id="roads">`) and carries
  enough metadata to recover the geographic bounds.

## MVP scope / out of scope

In: MapLibre map, search, rectangle select, OSM roads, the pipeline, two styles
(`dark-minimal`, `architectural-monochrome`), SVG preview + download, sync FastAPI.

Out (do not build unless asked): buildings, blocks, land use, freehand/admin
selection, PostGIS, job queues, accounts, persistence, auth, PNG/PDF/DXF export.

## Definition of done

A user can: open the app → navigate → search a place → drag a rectangle →
generate → see the SVG → switch between the two styles → tweak detail & road
width → regenerate without reload → download the SVG. Result must derive from
vector data, not a raster trace.
