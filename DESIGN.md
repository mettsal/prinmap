# Urban Fabric Generator — Technical Design Specification

**Status:** Draft v0.1
**Target:** MVP
**Primary domain:** Geospatial visualization / computational urban morphology
**Frontend:** React + TypeScript + MapLibre GL JS
**Backend:** Python + FastAPI
**Geospatial stack:** Shapely, GeoPandas, pyproj
**Initial data source:** OpenStreetMap
**Primary output:** SVG

---

## 1. Purpose

The Urban Fabric Generator is an interactive web application that allows a user to navigate a geographic map, select a geographic region, retrieve the corresponding urban geographic data, transform that data through a configurable geometry-processing pipeline, and export the resulting urban morphology as a clean vector graphic.

The intended visual language is exemplified by the supplied reference image: dense urban geography represented as high-contrast, abstracted black-and-white geometry.

The MVP focuses exclusively on **road-network morphology**.

Future iterations will support additional urban primitives such as:

* building footprints;
* urban blocks;
* parks and land use;
* waterways;
* railways;
* points of interest;
* combinations of multiple feature classes.

The application must therefore distinguish between:

1. **geographic acquisition**;
2. **geometric processing**;
3. **visual styling**;
4. **output generation**.

These concerns should remain independently replaceable.

---

# 2. Product Concept

The core interaction is:

```text
Navigate map
    ↓
Select geographic region
    ↓
Generate urban fabric
    ↓
Preview vector result
    ↓
Adjust visual parameters
    ↓
Regenerate
    ↓
Export SVG / raster preview
```

The application is not intended to simply screenshot or vectorize a rendered map.

Instead, the application retrieves the underlying geographic vector data and **constructs the final artwork algorithmically**.

This distinction is fundamental.

The map displayed to the user is an interface for geographic navigation and selection; the resulting SVG is an independently generated artifact.

---

# 3. Design Principles

## 3.1 Geographic truth and visual representation are separate

The geographic source should remain as close as practical to the original vector representation.

Visual simplification must occur in a later stage.

This allows:

* different visual styles from the same geographic source;
* regeneration without re-querying geographic data;
* independent control of simplification;
* accurate retention of the geographic coordinate system;
* future support for multiple feature types.

---

## 3.2 SVG is the canonical output

The primary generated artifact should be SVG rather than PNG.

Advantages:

* resolution independent;
* editable in vector software;
* compatible with presentation workflows;
* suitable for subsequent transformation;
* supports semantic grouping;
* permits future recoloring and editing;
* can be rasterized when needed.

PNG should be considered a derived preview/export format.

---

## 3.3 MVP should optimize for morphology, not GIS completeness

The application is not initially intended to be a general-purpose GIS editor.

The primary UX objective is:

> Select an interesting urban region and quickly produce a visually compelling representation of its morphology.

GIS functionality should therefore be introduced only when it supports this objective.

---

# 4. Technology Stack

## Frontend

* React
* TypeScript
* Vite
* MapLibre GL JS
* CSS / CSS modules or equivalent styling system

## Backend

* Python
* FastAPI
* Pydantic
* Uvicorn

## Geospatial processing

* Shapely
* GeoPandas
* pyproj

Potential later additions:

* PostGIS
* GDAL / rasterio where appropriate
* networkx for graph-level road analysis
* svgwrite or direct XML generation for SVG output

---

# 5. High-Level Architecture

```text
┌────────────────────────────────────────────────────────────┐
│                         FRONTEND                           │
│                                                            │
│  React / TypeScript                                        │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ MapLibre Map                                         │  │
│  │                                                      │  │
│  │ pan / zoom / search / selection                     │  │
│  └───────────────────────┬──────────────────────────────┘  │
│                          │                                 │
│                    Selection geometry                       │
│                          │                                 │
│                          ▼                                 │
│                Generation controls                         │
│                          │                                 │
│                          ▼                                 │
│                    SVG preview                             │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTP / JSON
                           ▼
┌────────────────────────────────────────────────────────────┐
│                         BACKEND                            │
│                                                            │
│                         FastAPI                            │
│                           │                                │
│            ┌──────────────┼──────────────┐                 │
│            ▼              ▼              ▼                 │
│       Data Layer     Geometry Layer   Rendering Layer      │
│            │              │              │                 │
│            ▼              ▼              ▼                 │
│          OSM          Shapely/GeoPandas     SVG            │
└────────────────────────────────────────────────────────────┘
```

The frontend must not contain the core urban-fabric generation algorithm.

The backend is authoritative for geometry generation.

---

# 6. Frontend

## 6.1 Main application layout

The initial interface should contain:

```text
┌──────────────────────────────────────────────────────────────┐
│ Urban Fabric Generator                                      │
├──────────────────────────────────────────────────────────────┤
│ Search [_____________________________] [Search]              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                                                              │
│                        MAP                                   │
│                                                              │
│                                                              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Selection: Rectangle                                         │
│                                                              │
│ [Select] [Clear]                                             │
│                                                              │
│ Style        [Dark Minimal ▼]                                │
│ Detail       ─────────●────────                              │
│ Road width   ───────●──────────                              │
│                                                              │
│                  [ Generate ]                                │
└──────────────────────────────────────────────────────────────┘
```

The exact visual design may change, but the functional hierarchy should remain.

---

# 7. Map Component

MapLibre GL JS will provide:

* map rendering;
* zoom;
* pan;
* geographic navigation;
* vector-tile visualization;
* selection overlays;
* map interaction events.

The map should be treated primarily as a geographic viewport.

The final generated artwork should not depend on the map renderer's pixels.

---

# 8. Map Style Strategy

The MVP should support at least two map appearance presets.

## 8.1 Dark Minimal

Purpose:

Provide an unobtrusive dark map that makes the selected region visually prominent.

Characteristics:

* dark background;
* muted roads;
* low visual noise;
* minimal labels;
* minimal POIs.

## 8.2 Monochrome Architectural

Purpose:

Approximate the graphic sensibility of the supplied reference.

Characteristics:

* monochrome palette;
* strong road hierarchy;
* minimal textual clutter;
* architectural/cartographic appearance.

These styles concern the **interactive map only**.

They must not be conflated with the output styling system.

---

# 9. Geographic Search

A geocoder should allow the user to search for a location before navigating/selecting.

Example:

```text
São Paulo
    ↓
geocoder result
    ↓
map.flyTo(...)
```

The search result should not itself automatically determine the urban-fabric boundary in the MVP.

The user searches for a city/district/place and then explicitly selects the region to generate.

This keeps selection deterministic.

---

# 10. Selection System

## 10.1 MVP Selection: Rectangle

The first selection tool is an axis-aligned geographic rectangle.

The frontend maintains:

```typescript
type BoundingBoxSelection = {
    type: "bbox";
    west: number;
    south: number;
    east: number;
    north: number;
};
```

Example:

```json
{
  "type": "bbox",
  "west": -46.650,
  "south": -23.570,
  "east": -46.630,
  "north": -23.550
}
```

The rectangle should be rendered as an interactive overlay on the map.

---

# 11. Future Selection Abstraction

The frontend should define selection conceptually as a polymorphic type from the beginning.

Future possibilities:

```typescript
type Selection =
    | BoundingBoxSelection
    | PolygonSelection
    | CircleSelection
    | AdministrativeBoundarySelection;
```

Potential future interaction modes:

* rectangle;
* free polygon;
* lasso;
* circle/radius;
* administrative district;
* road corridor;
* arbitrary GeoJSON selection.

The backend API should accept a generic geometry representation where practical rather than hard-coding the rectangle into the entire architecture.

---

# 12. Backend API

The MVP requires only a small number of endpoints.

## 12.1 Health

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

---

## 12.2 Generate

```http
POST /api/v1/generate
```

Request:

```json
{
  "selection": {
    "type": "bbox",
    "west": -46.650,
    "south": -23.570,
    "east": -46.630,
    "north": -23.550
  },
  "source": {
    "provider": "osm"
  },
  "fabric": {
    "features": ["roads"]
  },
  "style": {
    "preset": "dark-minimal"
  },
  "parameters": {
    "detail": 0.75,
    "road_width": 2.0
  }
}
```

Response:

```json
{
  "job_id": "uuid",
  "status": "completed",
  "format": "svg",
  "svg": "<svg>...</svg>"
}
```

For the earliest prototype, synchronous generation is acceptable.

A job queue should only be introduced when generation becomes slow enough to justify it.

---

# 13. Data Source Layer

The application should use an abstraction such as:

```python
class GeographicDataProvider(Protocol):
    def fetch_features(
        self,
        geometry,
        feature_types
    ) -> GeoDataFrame:
        ...
```

The MVP implementation:

```text
OSMProvider
```

Future implementations:

```text
PostGISProvider
CachedOSMProvider
LocalExtractProvider
```

This prevents the rest of the application from becoming coupled to the data-acquisition mechanism.

---

# 14. OpenStreetMap Query Strategy

The first feature class is:

```text
highway
```

The provider should retrieve road geometries intersecting the requested selection.

Relevant OSM road classes may include:

* motorway;
* trunk;
* primary;
* secondary;
* tertiary;
* residential;
* living_street;
* unclassified;
* service;
* pedestrian;
* track.

The MVP should probably exclude specialized features such as footpaths and tracks unless explicitly enabled.

---

# 15. Geographic Processing

Raw OSM geometries will generally be geographic coordinates.

Before geometry operations, transform them into an appropriate projected coordinate reference system.

For São Paulo and comparable areas, a suitable local projected CRS should be selected dynamically or via configuration.

The pipeline is:

```text
WGS84 / geographic coordinates
            ↓
Projected CRS
            ↓
geometry processing
            ↓
SVG coordinate normalization
```

Operations such as buffering must not be performed directly in latitude/longitude degrees.

---

# 16. Urban Fabric Pipeline

The MVP road-only pipeline is:

```text
OSM road centerlines
        ↓
filter relevant features
        ↓
clip to selection
        ↓
reproject to metric CRS
        ↓
normalize / clean geometries
        ↓
optionally simplify
        ↓
buffer road geometries
        ↓
union overlapping road areas
        ↓
clip final road mask
        ↓
normalize to SVG canvas
        ↓
render
```

The simplest artistic interpretation is:

```text
background = black
roads      = white
```

This should already produce the basic visual vocabulary visible in the supplied reference.

---

# 17. Road Width Model

A fixed width is acceptable for the first test.

However, the architecture should allow width to depend on road hierarchy.

For example:

```text
motorway   → large
trunk      → large
primary    → medium-large
secondary  → medium
tertiary   → medium-small
residential → small
service    → very small
```

Conceptually:

```python
ROAD_WIDTHS = {
    "motorway": 8.0,
    "trunk": 7.0,
    "primary": 6.0,
    "secondary": 5.0,
    "tertiary": 4.0,
    "residential": 2.5,
    "service": 1.5,
}
```

Exact values should be determined empirically after generating real examples.

---

# 18. Urban Fabric Simplification

Raw OSM data will generally be too detailed for a clean graphic.

The pipeline therefore requires a configurable simplification stage.

Possible operations:

* Douglas-Peucker simplification;
* topology-preserving simplification;
* removal of extremely short segments;
* removal of tiny disconnected features;
* road-class filtering;
* merging of overlapping buffered geometries.

The parameter exposed to the user should ultimately be abstract:

```text
Detail
0 ───────────────● 100
```

rather than exposing raw tolerances.

Internally:

```text
detail → geometry tolerance
       → feature filtering
       → minimum area
       → road classes
```

---

# 19. SVG Coordinate System

The generated SVG should not necessarily use geographic coordinates directly.

Instead:

```text
geographic geometry
       ↓
bounding box
       ↓
normalize
       ↓
scale to canvas
```

For example:

```text
SVG width  = 1600
SVG height = 1600
```

with the selected geography fitted while preserving aspect ratio.

A margin may be added according to style configuration.

The system should retain enough metadata to recover the original geographic bounds.

---

# 20. SVG Structure

A generated file should use semantic groups.

Example:

```xml
<svg
    width="1600"
    height="1600"
    viewBox="0 0 1600 1600"
>

    <g id="background">
        ...
    </g>

    <g id="roads">
        ...
    </g>

</svg>
```

Future versions:

```xml
<g id="major-roads">
    ...
</g>

<g id="minor-roads">
    ...
</g>

<g id="buildings">
    ...
</g>

<g id="water">
    ...
</g>
```

This is important for later editing and presentation workflows.

---

# 21. Style System

The rendering engine should consume a style object rather than hard-coded colors.

Conceptually:

```python
@dataclass
class FabricStyle:
    background: str
    road: str
    major_road_width: float
    minor_road_width: float
    margin: float
```

Initial presets:

```text
dark-minimal
architectural-monochrome
```

The actual parameter space should remain open for later styles.

Potential future styles:

```text
blueprint
paper
night
inverted
pastel
neon
topographic
minimal
```

---

# 22. Rendering vs. Geometry

A strict separation should be maintained:

```text
GEOMETRY

"Where are the roads?"
```

versus:

```text
STYLE

"How should the roads look?"
```

and:

```text
OUTPUT

"How do we encode that as SVG?"
```

This gives us:

```text
Same São Paulo geometry
        ↓
 ┌──────┼─────────┬─────────┐
 ↓      ↓         ↓         ↓
dark  blueprint  mono     future style
```

without repeating geographic computation.

---

# 23. Frontend State Model

The frontend will likely need approximately:

```typescript
type AppState = {
    map: MapState;
    selection: Selection | null;
    generation: GenerationState;
    style: StyleState;
};
```

Generation state:

```typescript
type GenerationState =
    | { status: "idle" }
    | { status: "generating" }
    | { status: "success"; svg: string }
    | { status: "error"; message: string };
```

The UI should visibly distinguish:

```text
idle
generating
success
failure
```

rather than leaving the user uncertain whether generation is running.

---

# 24. Preview

After generation, the application should display the resulting SVG directly in the browser.

The preview should support:

* fit-to-window;
* zoom;
* pan;
* transparent/background preview where useful;
* regeneration after parameter changes.

The SVG should remain vector-native rather than being immediately rasterized.

---

# 25. Export

MVP export:

```text
Download SVG
```

Secondary:

```text
Download PNG
```

PNG can be generated either client-side or backend-side depending on implementation.

Future:

```text
PDF
GeoJSON
DXF
```

should not be implemented until there is a concrete use case.

---

# 26. Caching

Generation requests should eventually be cacheable.

A request can be identified approximately by:

```text
selection
+
source
+
feature set
+
processing parameters
+
style parameters
```

This allows:

```text
same district
+
same roads
+
same geometry settings
=
reuse previous geometry
```

Style-only changes should ideally not require refetching OSM data.

---

# 27. Recommended Internal Pipeline Objects

The backend should conceptually separate:

```python
Selection
GeographicFeatureSet
ProcessedGeometry
FabricStyle
FabricResult
```

For example:

```python
@dataclass
class FabricResult:
    geometry: GeoDataFrame
    metadata: dict
```

The renderer then consumes this object.

---

# 28. Error Handling

Expected failures include:

* invalid selection;
* selection outside provider coverage;
* OSM query timeout;
* excessive selection size;
* empty road network;
* invalid geometry;
* geometry operation failure;
* SVG serialization failure.

The API should return structured errors.

Example:

```json
{
  "error": {
    "code": "EMPTY_GEOMETRY",
    "message": "No supported road features were found in the selected region."
  }
}
```

The frontend should translate technical failures into readable UI messages.

---

# 29. Selection Constraints

To protect the MVP from pathological requests, the backend should enforce a maximum area.

For example:

```text
maximum selection area = configurable
```

This should initially be conservative.

The actual threshold should be determined experimentally based on:

* OSM query time;
* geometry complexity;
* SVG size;
* browser rendering time.

The UI can eventually display:

```text
Selection too large.
Maximum supported area: X km²
```

---

# 30. Performance Targets

Initial target:

```text
map interaction:
    smooth at normal desktop usage

generation:
    ideally < 5 seconds for a typical district-sized selection

SVG:
    render interactively in browser
```

These are engineering targets rather than hard requirements for the first prototype.

The architecture should prioritize correctness before aggressive optimization.

---

# 31. MVP Scope

The first implementation should contain only:

### Map

* MapLibre map;
* zoom/pan;
* geographic search;
* rectangle selection.

### Data

* OpenStreetMap;
* roads only.

### Generation

* clip roads;
* reproject;
* simplify;
* buffer;
* union;
* normalize.

### Styles

* dark minimal;
* monochrome architectural.

### Output

* SVG;
* browser preview;
* download.

### Backend

* FastAPI;
* synchronous generation.

That is enough to validate the entire concept end-to-end.

---

# 32. Explicitly Out of MVP

The following should be deliberately postponed:

* building footprints;
* block generation;
* land-use classification;
* satellite imagery;
* automatic district recognition;
* freehand selection;
* administrative-boundary selection;
* PostGIS;
* distributed job queues;
* user accounts;
* persistence/database;
* collaborative editing;
* advanced SVG editing;
* authentication;
* deployment infrastructure optimization.

The objective is to prove:

> geographic selection → OSM retrieval → procedural urban morphology → useful SVG.

---

# 33. Phase 2

Once the MVP works, introduce additional feature layers.

Potential ordering:

```text
MVP
roads
  ↓
Phase 2A
building footprints
  ↓
Phase 2B
urban blocks
  ↓
Phase 2C
water + parks
  ↓
Phase 2D
multi-layer compositing
```

This should allow the artwork to move progressively from:

```text
ROAD NETWORK
```

toward:

```text
FULL URBAN FABRIC
```

without changing the user-facing interaction model.

---

# 34. Phase 3 — Morphological Analysis

The project can eventually go beyond representation and calculate urban morphology metrics.

Possible derived quantities:

* road density;
* intersection density;
* average block area;
* street orientation;
* network centrality;
* block compactness;
* intersection type distribution;
* street hierarchy distribution.

That opens the door to a second product layer:

```text
Generate an urban fabric
```

and:

```text
Analyze an urban fabric
```

using the same geographic substrate.

This is intentionally outside the MVP but should inform the data model.

---

# 35. Suggested Repository Structure

```text
prinmap/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── map/
│   │   ├── selection/
│   │   ├── generation/
│   │   └── styles/
│   ├── package.json
│   └── vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── providers/
│   │   │   └── osm.py
│   │   ├── geometry/
│   │   │   ├── processing.py
│   │   │   └── projection.py
│   │   ├── rendering/
│   │   │   ├── svg.py
│   │   │   └── styles.py
│   │   └── main.py
│   └── pyproject.toml
│
├── tests/
│   ├── geometry/
│   ├── rendering/
│   └── api/
│
├── examples/
│   └── sao_paulo/
│
├── docs/
│
└── README.md
```

---

# 36. First Development Milestone

The first milestone should deliberately avoid building the entire polished UI.

The target is:

```text
1. Launch frontend.
2. Display interactive map.
3. Search São Paulo.
4. Draw rectangle.
5. Send rectangle to FastAPI.
6. Query OSM roads.
7. Generate black/white SVG.
8. Display SVG.
9. Download SVG.
```

A successful implementation of those nine steps proves the core architecture.

Everything else becomes refinement.

---

# 37. First Technical Prototype

The initial prototype should therefore have four independently testable pieces:

```text
A. Map + selection
B. OSM acquisition
C. Geometry processor
D. SVG renderer
```

Test them independently before coupling everything together.

For example, the geometry processor should be capable of accepting a local GeoJSON fixture:

```text
fixture.geojson
       ↓
geometry processor
       ↓
fabric.svg
```

without requiring the frontend or a live OSM request.

Likewise, the renderer should be testable with synthetic geometries.

---

# 38. Definition of Done — MVP

The MVP is considered functionally complete when a user can:

1. open the web application;
2. navigate the map;
3. search for a location such as São Paulo;
4. select an arbitrary rectangular region;
5. request generation;
6. retrieve road geometry for the selected region;
7. generate a vector urban-fabric representation;
8. view that representation in the application;
9. switch between at least two output styles;
10. adjust at least detail and road-width parameters;
11. regenerate without reloading the application;
12. download the resulting SVG.

The generated result must be based on geographic vector data rather than a screenshot or raster tracing.

---

# 39. Guiding Principle for Future Development

The application should ultimately behave less like:

```text
"map screenshot generator"
```

and more like:

```text
"procedural urban morphology synthesizer"
```

The map is the interface.

The OSM data is the geographic substrate.

The geometry engine is the core intellectual component.

The SVG renderer is the final expression layer.

That separation is what gives the project room to evolve from a simple road visualizer into a general-purpose urban-fabric generation system.
