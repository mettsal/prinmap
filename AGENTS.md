# AGENTS.md — prinmap (Urban Fabric Generator)

Operational guide for coding agents. The full product vision lives in
[`DESIGN.md`](./DESIGN.md); **this file is the source of truth for how to build,
run, test, and extend the code.** When the two disagree about *implementation*,
this file wins; when they disagree about *intent*, DESIGN.md wins.

## What this is

A web app to select a geographic rectangle, fetch OSM road/building/water/park
data, and procedurally generate:

1. a black-and-white **SVG** of the urban morphology (roads, buildings,
   block interiors, water, parks/woods — independently toggleable layers), and
2. a watertight **STL** mesh of the buildings fused onto DEM-draped terrain
   with a solid flat base, for Rhino/Blender/slicer workflows — with streets,
   water, and parks/woods differentiated on the (mono-material) print surface
   via shape/texture rather than color.

The interactive map is only a viewport for selection (and, in "3D Preview"
mode, a look-around tool) — the artwork/mesh is generated algorithmically from
vector data on the backend, never screenshotted.

2D pipeline: `select bbox → fetch OSM roads/buildings/water/parks → reproject
to UTM → simplify → (buffer roads | clip buildings | derive block interiors |
clip+union water/parks) → union → clip → normalize → render SVG`.

3D pipeline: `select bbox → fetch OSM buildings → reproject to UTM → clip →
resolve height (height tag > levels*3m > 9m default) → [if terrain.include]
also fetch roads/water/parks → sample a DEM elevation grid over the frame →
apply_surface_treatments (recess or texture streets, texture parks, flatten
water per-component — all as Z-value edits to the grid, never touching mesh
topology) → build a watertight terrain solid from that treated grid (draped
surface + flat base plinth) → seat each building's base_z on that
POST-treatment surface (min sampled corner, sunk slightly to guarantee
fusion) → triangulate footprint (earcut, handles courtyard holes) → extrude
each building to a closed prism → merge terrain + all buildings into one mesh
→ write binary STL`. With `terrain.include=false`, buildings extrude straight
onto a flat z=0 plane (no DEM/road/water/park fetch — faster, network-lighter).

## Layout

```
backend/app/
  main.py            FastAPI routes: /health, /api/v1/generate (SVG),
                      /api/v1/generate/mesh (STL), /api/v1/geocode
  config.py          Settings (limits, service URLs, canvas size)
  errors.py          FabricError + structured error factories
  models/schemas.py  Pydantic request/response models
  providers/         GeographicDataProvider protocol; OSMProvider (Overpass,
                      roads + buildings + water + parks); geocode.py
                      (Nominatim proxy); elevation.py (ElevationProvider
                      protocol + TerrariumElevationProvider — DEM tile
                      fetch/decode); base.py also has AreaFeature/
                      AreaFeatureSet (shared water/park data model)
  geometry/
    projection.py    dynamic UTM zone selection
    collections.py   iter_lines/iter_polygons — shared multi-geometry helpers
    processing.py    layered pipeline: process_roads/process_buildings/
                      process_blocks/process_landuse (water+parks, shared fn)
                      -> ProcessedFabric (2D layers dict + buildings_3d list
                      of (footprint, height_m) + always-populated road_area/
                      water_area/park_area masks for the 3D pass)
    extrude.py        earcut triangulation + watertight prism extrusion
                      (extrude_polygon takes base_z; build_scene_mesh /
                      build_scene_mesh_with_base concatenate buildings)
    mesh_utils.py     merge_meshes — shared index-offsetting for combining
                      independent watertight solids into one buffer
    terrain.py        ElevationGrid + sample_elevation_grid + build_terrain_mesh
                      (draped surface + flat base plinth) + building_base_z +
                      apply_surface_treatments (roads/water/parks Z-edits)
  rendering/
    styles.py         FabricStyle presets (background/road/block_fill/
                      building_fill/water_fill/park_fill)
    svg.py             multi-layer SVG renderer (blocks -> parks -> water ->
                      buildings -> roads)
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
- **Elevation (DEM) is a swappable abstraction** (`providers/elevation.py::
  ElevationProvider`, mirrors `GeographicDataProvider`): `.elevations(lons,
  lats) -> metres`, batch-oriented so a tiled source only fetches/decodes
  each covering tile once per request. `TerrariumElevationProvider` (the only
  implementation today) reuses the exact free, no-API-key AWS Terrarium
  raster-dem tiles already used for the browser's 3D preview
  (`s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`,
  `elevation_m = r*256 + g + b/256 - 32768`) — **this URL/encoding is
  duplicated** in `frontend/src/map/mapStyles.ts` (TypeScript, browser
  preview) and `backend/app/providers/elevation.py` (Python, server-side STL
  export); there's no shared config between the two languages, so if either
  changes, update both. Swap in a higher-res DEM later (Copernicus GLO-30,
  SRTM, municipal data) by implementing the same protocol — nothing else in
  `geometry/terrain.py` or `service.py` needs to change.
- **Pillow is a new dependency** (PNG decode for Terrarium tiles). Unlike
  GeoPandas/GDAL-class packages, it ships plain precompiled wheels — doesn't
  conflict with the project's "avoid heavy/fragile Windows installs" stance.
- **Terrain tile sampling is nearest-pixel, not bilinear-within-tile** (v1
  simplification, `elevation.py::TerrariumElevationProvider.elevations`) —
  the *grid* itself is bilinearly interpolated (`terrain.py::ElevationGrid.
  sample_bilinear`), so this only matters at the sub-tile-pixel level
  (~9.5m at the default zoom 14); revisit if terrain looks blocky up close.
- **Roads/water/parks are "carved" into the terrain by mutating
  `ElevationGrid.elevations` Z-values BEFORE `build_terrain_mesh` runs
  (`terrain.py::apply_surface_treatments`) — never by touching
  `build_terrain_mesh`'s topology-building code.** Since that function is a
  pure function of whatever Z values are already in the grid, watertightness
  (verified via Euler characteristic) stays guaranteed "for free": only Z
  values change, never triangle connectivity. Any future surface treatment
  should follow this same pattern.
- **Street/park texture pitch is tied to `resolution_m`** (grid-index-parity
  checkerboard/stripe patterns, one bump per grid cell) — at the default 10m
  spacing this reads as coarse bumps, not fine ridges. No independent
  physical-scale control exists yet; finer texture currently requires a
  finer `resolution_m` (more compute). Revisit after physical print feedback.
- **Water is flattened per connected polygon component**, not by one global
  min-of-boundary across all water in the selection — each lake/river segment
  gets its own flat elevation (min of that component's own boundary vertices
  minus `WATER_SUBMERSION_M`), so one low-lying water body elsewhere in the
  selection can't trench an unrelated one. A single elongated/sloped water
  body (e.g. a river crossing a hilly selection) can still show a stepped
  edge at its own boundary — accepted v1 simplification, no centerline/flow-
  direction handling.
- **Overlap priority when road/water/park masks intersect: water > road >
  park** — each grid node gets exactly one treatment (masks are made
  mutually exclusive before applying in `apply_surface_treatments`), never a
  stack of overlapping edits.
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
- `fabric.features` (SVG endpoint) is a set of `"roads" | "buildings" |
  "blocks" | "water" | "parks"`; layers are independently toggleable and
  drawn in that painter's order (`geometry/processing.py::process_fabric`,
  `rendering/svg.py::_LAYER_ORDER` = blocks -> parks -> water -> buildings ->
  roads). "blocks" (city-block interiors) are derived as
  `frame.difference(roads)`, so the road network is fetched even if the
  "roads" layer itself isn't rendered. `ProcessedFabric.road_area`/
  `water_area`/`park_area` are always populated whenever their feature_set is
  given, *independent* of whether that layer is in `features` — the 3D mesh
  endpoint needs these masks even when no 2D layer is requested at all.
- `detail` param is an abstract `0..1` knob → tolerance + class filtering + min
  length (roads) / light simplification (buildings). `road_width` is a global
  multiplier over per-class base widths; doesn't affect buildings/blocks.
- The 3D mesh endpoint (`/api/v1/generate/mesh`) is buildings-only and has its
  own lightweight request schema (`GenerateMeshRequest` — no `fabric`/`style`,
  plus a `terrain: TerrainParameters` block: `include` (default `true`),
  `resolution_m`, `base_thickness_m`, `exaggeration`, `street_style`
  (`"recessed"|"textured"`, default `"recessed"`), `street_recess_depth_m`).
  There's no separate include-toggle for water/parks — whenever
  `terrain.include=True` they're fetched and treated if present in the
  selection (empty masks are just a no-op); `terrain.include=False` skips
  fetching roads/water/parks entirely, keeping that path exactly as fast as
  the plain buildings-only export.
- `service.py` functions take an optional provider/`elevation_provider` param
  (defaulting to the real `OSMProvider`/`TerrariumElevationProvider`) purely
  for dependency injection in tests — always wire new external data sources
  the same way, never construct them unconditionally inside a function body.
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

In: MapLibre map, search, rectangle select, OSM roads + buildings + water +
parks/woods, the layered 2D pipeline, two SVG styles (`dark-minimal`,
`architectural-monochrome`), SVG preview + download, STL export of buildings
fused onto DEM-draped terrain with a solid flat base and mono-material-safe
street/water/park differentiation (printable as one watertight piece), a
MapLibre 3D preview (extruded buildings + terrain hillshade, browser-only),
sync FastAPI.

Out (do not build unless asked): land-use classification beyond
water/parks/woods (e.g. no `landuse=grass`/`meadow`, no individual tree
geometry — ground texture only), freehand/admin selection, PostGIS, job
queues, accounts, persistence, auth, PNG/PDF/DXF export, multipolygon-relation
buildings/water/parks (ways only, everywhere).

## Known gaps / next steps (don't silently "fix" — ask first, these are scoped)

- **Terrain grid resolution is clamped** (`geometry/terrain.py::
  MAX_GRID_POINTS_PER_AXIS = 300` per axis) regardless of the requested
  `terrain.resolution_m` — silently coarsens rather than erroring on a large
  selection. Not currently surfaced in the API response metadata.
- **Vertical exaggeration only scales terrain relief, not building heights**
  (`terrain.exaggeration` applied once at grid-sampling time,
  `terrain.py::sample_elevation_grid`) — a high exaggeration can look
  architecturally odd (short real-scale buildings on dramatically stretched
  hills). Exposed as a UI slider; no warning shown yet.
- **Building `relation` (multipolygon) footprints are skipped** — only OSM
  `way["building"]` is queried; complex/relation-based footprints are missing.
  **Water/park `relation` features are skipped too** (ways only, same
  convention) — this likely matters *more* here than for buildings, since
  large water bodies and forests are commonly mapped as multipolygon
  relations in real OSM data more often than buildings are.
- **Building seating depends on the POST-surface-treatment grid** — a
  building near a recessed street or a flattened water edge seats on
  whatever the final treated terrain looks like there, not the raw sampled
  relief. This is intentional (buildings should fuse with the actual printed
  surface) but is a real interaction worth remembering when debugging
  building placement near roads/water.
- **Rectangle selection is awkward in 3D preview mode** (pitch distorts the
  screen-space drag) — Controls disables "Select rectangle" while
  `mapPreset === "3d"`; users draw in 2D, then switch to 3D to look around.
- **No caching across requests for elevation tiles** — `TerrariumElevationProvider`
  caches per-instance (i.e. per-request) only; repeated exports of the same
  area re-fetch the same DEM tiles. Fine for MVP ("Generation is synchronous,
  no queue"), worth revisiting if usage grows.

## Definition of done

A user can: open the app → navigate → search a place → drag a rectangle →
toggle roads/buildings/block-interior/water/park layers → generate → see the
SVG → switch between the two styles → tweak detail & road width → regenerate
without reload → download the SVG → export a printable STL (buildings fused
onto real terrain relief with a solid flat base; base thickness, vertical
exaggeration, and street treatment — recessed channel or embossed texture —
all adjustable; water flattened and parks/woods textured automatically
whenever present; or a flat/no-terrain fast path) → look around a 3D preview
(extruded buildings + terrain) in the browser. Results must derive from
vector data, not a raster trace.
