"""Generation orchestration — ties provider -> geometry -> renderer together.

Kept separate from the FastAPI layer so it can be driven from tests or a CLI
without HTTP.
"""

from __future__ import annotations

import uuid

from .config import settings
from .errors import empty_geometry, invalid_selection, selection_too_large
from .geometry.processing import process_fabric
from .geometry.projection import projection_for
from .models.schemas import BBoxSelection, GenerateRequest, GenerateResponse
from .providers.base import GeographicDataProvider
from .providers.osm import DEFAULT_ROAD_CLASSES, OSMProvider
from .rendering.styles import get_style
from .rendering.svg import render_svg


def _validate_bbox(bbox: BBoxSelection) -> None:
    if bbox.west >= bbox.east or bbox.south >= bbox.north:
        raise invalid_selection(
            "Selection is degenerate: expected west<east and south<north."
        )
    if not (-180 <= bbox.west <= 180 and -180 <= bbox.east <= 180):
        raise invalid_selection("Longitude out of range.")
    if not (-90 <= bbox.south <= 90 and -90 <= bbox.north <= 90):
        raise invalid_selection("Latitude out of range.")


def _selection_area_km2(bbox: BBoxSelection) -> float:
    """Approximate the selection area using a projected metric frame."""
    proj = projection_for((bbox.west + bbox.east) / 2, (bbox.south + bbox.north) / 2)
    minx, miny = proj.forward(bbox.west, bbox.south)
    maxx, maxy = proj.forward(bbox.east, bbox.north)
    return abs(maxx - minx) * abs(maxy - miny) / 1_000_000.0


def generate_fabric(
    request: GenerateRequest,
    provider: GeographicDataProvider | None = None,
) -> GenerateResponse:
    bbox = request.selection
    _validate_bbox(bbox)

    area = _selection_area_km2(bbox)
    if area < settings.min_selection_area_m2 / 1_000_000.0:
        raise invalid_selection("Selection is too small to generate anything useful.")
    if area > settings.max_selection_area_km2:
        raise selection_too_large(
            f"Selection area is ~{area:.1f} km². "
            f"Maximum supported area is {settings.max_selection_area_km2:.0f} km²."
        )

    provider = provider or OSMProvider()
    feature_set = provider.fetch_roads(
        bbox.west, bbox.south, bbox.east, bbox.north, DEFAULT_ROAD_CLASSES
    )
    if len(feature_set) == 0:
        raise empty_geometry(
            "No supported road features were found in the selected region."
        )

    processed = process_fabric(feature_set, bbox, request.parameters)
    if processed.geometry.is_empty:
        raise empty_geometry(
            "The selected roads produced no drawable area at this detail level."
        )

    style = get_style(request.style.preset)
    svg = render_svg(processed, style, size=settings.svg_size)

    metadata = dict(processed.metadata)
    metadata.update({"style": style.name, "canvas": settings.svg_size, "area_km2": area})

    return GenerateResponse(
        job_id=str(uuid.uuid4()),
        status="completed",
        format="svg",
        svg=svg,
        metadata=metadata,
    )
