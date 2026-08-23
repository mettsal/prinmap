"""FastAPI application entry point (DESIGN.md §12).

Endpoints:
    GET  /health
    POST /api/v1/generate
    GET  /api/v1/geocode?q=...
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .errors import FabricError, invalid_selection
from .models.schemas import (
    GenerateMeshRequest,
    GenerateRequest,
    GenerateResponse,
    GeocodeResponse,
)
from .providers.geocode import geocode
from .service import generate_fabric, generate_mesh

app = FastAPI(title="Urban Fabric Generator", version="0.1.0")

# Permissive CORS for local development (frontend runs on a different port).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FabricError)
async def _fabric_error_handler(_request, exc: FabricError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    return generate_fabric(request)


@app.post("/api/v1/generate/mesh")
def generate_mesh_endpoint(request: GenerateMeshRequest) -> Response:
    stl_bytes, print_info = generate_mesh(request)
    headers = {
        "Content-Disposition": 'attachment; filename="urban-fabric.stl"',
        "X-Print-Scale": f"1:{print_info['scale_denominator']}",
        "X-Print-Size-Mm": str(print_info["print_size_mm"]),
        "X-Print-Footprint-Mm": "x".join(str(v) for v in print_info["model_footprint_mm"]),
        "X-Print-Warnings": " | ".join(print_info["warnings"]),
        # Let the browser (a cross-origin fetch during dev) read the X-* headers.
        "Access-Control-Expose-Headers": (
            "X-Print-Scale, X-Print-Size-Mm, X-Print-Footprint-Mm, X-Print-Warnings"
        ),
    }
    return Response(content=stl_bytes, media_type="model/stl", headers=headers)


@app.get("/api/v1/geocode", response_model=GeocodeResponse)
def geocode_endpoint(q: str = Query(..., min_length=1)) -> GeocodeResponse:
    if not q.strip():
        raise invalid_selection("Empty geocoding query.")
    return GeocodeResponse(results=geocode(q))
