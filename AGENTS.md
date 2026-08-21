# AGENTS.md — prinmap (Urban Fabric Generator)

Operational guide for coding agents. The full product vision lives in
[`DESIGN.md`](./DESIGN.md); **this file is the source of truth for how to build,
run, test, and extend the code.** When the two disagree about *implementation*,
this file wins; when they disagree about *intent*, DESIGN.md wins.

## What this is

A web app to select a geographic rectangle, fetch OSM road/building data, and
procedurally generate:

1. a black-and-white **SVG** of the urban morphology (roads, buildings,
   block interiors — independently toggleable layers), and
2. a watertight **STL** mesh of the buildings, extruded by height, for
   Rhino/Blender/slicer workflows.

The interactive map is only a viewport for selection (and, in "3D Preview"
mode, a look-around tool) — the artwork/mesh is generated algorithmically from
vector data on the backend, never screenshotted.

2D pipeline: `select bbox → fetch OSM roads/buildings → reproject to UTM →
simplify → (buffer roads | clip buildings | derive block interiors) → union →
clip → normalize → render SVG`.

3D pipeline: `select bbox → fetch OSM buildings → reproject to UTM → clip →
resolve height (height tag > levels*3m > 9m default) → triangulate footprint
(earcut, handles courtyard holes) → extrude to a closed prism → write binary
STL`. Buildings sit on a flat z=0 ground plane — terrain relief isn't draped
into the STL yet (see "Known gaps / next steps" below); it only exists as a
visual hillshade in the browser's 3D preview.

## Layout

```
backend/app/
  main.py            FastAPI routes: /health, /api/v1/generate (SVG),
                      /api/v1/generate/mesh (STL), /api/v1/geocode
  config.py          Settings (limits, service URLs, canvas size)
  errors.py          FabricError + structured error factories
  models/schemas.py  Pydantic request/response models
  providers/         GeographicDataProvider protocol; OSMProvider (Overpass,
                      roads + buildings); geocode.py (Nominatim proxy)
  geometry/
    projection.py    dynamic UTM zone selection
    collections.py   iter_lines/iter_polygons — shared multi-geometry helpers
    processing.py    layered pipeline: process_roads/process_buildings/
                      process_blocks -> ProcessedFabric (2D layers dict +
                      buildings_3d list of (footprint, height_m))
    extrude.py        earcut triangulation + watertight prism extrusion
  rendering/
    styles.py         FabricStyle presets (background/road/block_fill/building_fill)
    svg.py             multi-layer SVG renderer (blocks -> buildings -> roads)
    stl.py             hand-rolled binary STL writer (no trimesh/numpy-stl)
frontend/src/
  map/               MapLibre viewport, rectangle selection, basemap styles
                      (dark/mono raster + "3d" OpenFreeMap vector preview)
  selection/         selection types/helpers
  generation/        API client, controls (layer toggles, STL export), SVG preview
tests/               geometry / rendering / providers / api (OSM mocked — no network)
```

## Stack decisions (important)

- **Backend geo stack is `shapely` + `pyproj` + `requests` + `numpy` +
  `mapbox-earcut` — NOT GeoPandas.** Chosen to avoid heavy/fragile installs on
  Windows. Providers return plain `RoadFeature`/`BuildingFeature` dataclasses
  (shapely geometry + attrs), not a GeoDataFrame. Keep this unless GeoPandas
  becomes genuinely necessary.
- **OSM access:** Overpass API via `out geom;` (way geometry inline, no node
  resolution). Roads filtered by a `highway` regex; buildings by `way["building"]`
  — **multipolygon-relation buildings are skipped** (ways only) in the MVP.
- **Building height:** `height` tag > `building:levels` * 3m > 9m default
  (`providers/osm.py::parse_building_height`, pure/unit-tested).
- **Mesh triangulation:** `mapbox_earcut` (numpy in/out) — handles polygon
  holes correctly, which matters for buildings with courtyards.
- **STL is hand-written** (`rendering/stl.py`, `struct`-based binary writer) —
  no trimesh/numpy-stl dependency, since the format is simple and fixed-size.
- **Geocoding:** Nominatim, proxied through the backend (`/api/v1/geocode`) to
  respect the usage policy and set a User-Agent — never call it from the browser.
- **2D basemaps:** CARTO raster tiles (`dark_all` / `light_all`) — no API key.
- **3D preview basemap:** OpenFreeMap `liberty` style
  (`https://tiles.openfreemap.org/styles/liberty`) — free, no API key, vector,
  OpenMapTiles schema. It already ships a `building-3d` fill-extrusion layer
  (source `openmaptiles`, source-layer `building`, `render_height`/
  `render_min_height`) — **do not add a duplicate custom extrusion layer**.
  Terrain relief is added separately via the AWS Terrarium DEM mirror
  (`s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`,
  `encoding: "terrarium"`, no API key) — see `map/mapStyles.ts`.
- **Projection:** dynamic UTM zone from the bbox centre. Never buffer/extrude
  in degrees.
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
  geometry (geometry/), style (rendering/styles.py), output (rendering/svg.py,
  rendering/stl.py).
- `fabric.features` (SVG endpoint) is a set of `"roads" | "buildings" | "blocks"`;
  layers are independently toggleable and drawn in that painter's order
  (`geometry/processing.py::process_fabric`, `rendering/svg.py::_LAYER_ORDER`).
  "blocks" (city-block interiors) are derived as `frame.difference(roads)`, so
  the road network is fetched even if the "roads" layer itself isn't rendered.
- `detail` param is an abstract `0..1` knob → tolerance + class filtering + min
  length (roads) / light simplification (buildings). `road_width` is a global
  multiplier over per-class base widths; doesn't affect buildings/blocks.
- The 3D mesh endpoint (`/api/v1/generate/mesh`) is buildings-only and has its
  own lightweight request schema (`GenerateMeshRequest` — no `fabric`/`style`).
- Frontend: `Selection` is a discriminated union (`type: "bbox"` today).
  `GenerationState`/`MeshStatus` are tagged unions: idle | generating/exporting
  | success | error — always reflect them in the UI.
- SVG uses semantic groups (`<g id="background">`, `<g id="blocks">`,
  `<g id="buildings">`, `<g id="roads">` — only the requested/non-empty ones)
  and carries enough metadata to recover the geographic bounds.
- STL is a flat triangle list (no shared-solid concept) — multiple buildings in
  one file are fine as long as each building's own mesh is watertight
  (verified in tests via Euler characteristic: V - E + F == 2 - 2·genus).

## MVP scope / out of scope

In: MapLibre map, search, rectangle select, OSM roads + buildings, the layered
2D pipeline, two SVG styles (`dark-minimal`, `architectural-monochrome`), SVG
preview + download, STL export of extruded buildings, a MapLibre 3D preview
(extruded buildings + terrain hillshade, browser-only), sync FastAPI.

Out (do not build unless asked): land-use classification, freehand/admin
selection, PostGIS, job queues, accounts, persistence, auth, PNG/PDF/DXF export,
multipolygon-relation buildings, terrain-draped STL (see below).

## Known gaps / next steps (don't silently "fix" — ask first, these are scoped)

- **STL buildings sit on flat ground (z=0)** — no DEM drape yet. Next step
  would reuse the AWS Terrarium tiles (already used for the browser preview)
  server-side, or a proper DEM (SRTM/Copernicus), to offset each building's
  base by ground elevation before extrusion.
- **Building `relation` (multipolygon) footprints are skipped** — only OSM
  `way["building"]` is queried; complex/relation-based footprints are missing.
- **Rectangle selection is awkward in 3D preview mode** (pitch distorts the
  screen-space drag) — Controls disables "Select rectangle" while
  `mapPreset === "3d"`; users draw in 2D, then switch to 3D to look around.

## Definition of done

A user can: open the app → navigate → search a place → drag a rectangle →
toggle roads/buildings/block-interior layers → generate → see the SVG →
switch between the two styles → tweak detail & road width → regenerate
without reload → download the SVG → export the buildings as an STL → look
around a 3D preview (extruded buildings + terrain) in the browser. Results
must derive from vector data, not a raster trace.
