# prinmap — Urban Fabric Generator

Select a geographic rectangle, fetch OpenStreetMap road data, and procedurally
generate a black-and-white **SVG** of the urban road morphology. The map is only
a viewport for selection — the artwork is generated algorithmically from vector
data, never screenshotted.

See [`DESIGN.md`](./DESIGN.md) for the full vision and [`AGENTS.md`](./AGENTS.md)
for the operational build/test guide.

## Quick start

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell:  .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend is now at http://localhost:8000 (`GET /health` → `{"status":"ok"}`).

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` → `:8000`.

### 3. Use it

1. Search a place (e.g. *São Paulo*) → the map flies there.
2. Click **Select rectangle**, then drag a box on the map.
3. Press **Generate** → roads are fetched, processed, and rendered.
4. Switch **Output style**, tweak **Detail** / **Road width**, regenerate.
5. **Download SVG**.

> Keep the selection small (a district, not a whole city) — the backend enforces
> a max area of ~25 km² for the MVP.

## Tests

```bash
cd backend && .venv\Scripts\python -m pytest ../tests -q
```

## Architecture

```
Frontend (MapLibre viewport, rectangle select, controls, SVG preview)
        │  POST /api/v1/generate  { selection, style, parameters }
        ▼
Backend  providers/  → geometry/  → rendering/
         (OSM/Overpass) (reproject, simplify, buffer, union, clip) (SVG)
```

Four independently replaceable concerns: **acquisition · geometry · style · output**.
