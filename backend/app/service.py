"""Generation orchestration — ties provider -> geometry -> renderer together.

Kept separate from the FastAPI layer so it can be driven from tests or a CLI
without HTTP.
"""

from __future__ import annotations

import uuid

from .config import settings
from .errors import empty_geometry, invalid_selection, selection_too_large
from .geometry.extrude import build_scene_mesh, build_scene_mesh_with_base
from .geometry.mesh_utils import merge_meshes
from .geometry.processing import process_fabric
from .geometry.projection import projection_for
from .geometry.terrain import building_base_z, build_terrain_mesh, sample_elevation_grid
from .models.schemas import (
    BBoxSelection,
    GenerateMeshRequest,
    GenerateRequest,
    GenerateResponse,
)
from .providers.base import GeographicDataProvider
from .providers.elevation import ElevationProvider, TerrariumElevationProvider
from .providers.osm import DEFAULT_ROAD_CLASSES, OSMProvider
from .rendering.stl import write_stl_binary
from .rendering.styles import get_style
from .rendering.svg import render_svg

KNOWN_FEATURES = {"roads", "buildings", "blocks"}


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


def _check_area(bbox: BBoxSelection) -> float:
    area = _selection_area_km2(bbox)
    if area < settings.min_selection_area_m2 / 1_000_000.0:
        raise invalid_selection("Selection is too small to generate anything useful.")
    if area > settings.max_selection_area_km2:
        raise selection_too_large(
            f"Selection area is ~{area:.1f} km². "
            f"Maximum supported area is {settings.max_selection_area_km2:.0f} km²."
        )
    return area


def generate_fabric(
    request: GenerateRequest,
    provider: GeographicDataProvider | None = None,
) -> GenerateResponse:
    bbox = request.selection
    _validate_bbox(bbox)
    area = _check_area(bbox)

    features = set(request.fabric.features) & KNOWN_FEATURES
    if not features:
        raise invalid_selection(
            f"fabric.features must include at least one of {sorted(KNOWN_FEATURES)}."
        )

    provider = provider or OSMProvider()

    road_feature_set = None
    if "roads" in features or "blocks" in features:
        road_feature_set = provider.fetch_roads(
            bbox.west, bbox.south, bbox.east, bbox.north, DEFAULT_ROAD_CLASSES
        )

    building_feature_set = None
    if "buildings" in features:
        building_feature_set = provider.fetch_buildings(
            bbox.west, bbox.south, bbox.east, bbox.north
        )

    fetched_anything = (road_feature_set is not None and len(road_feature_set) > 0) or (
        building_feature_set is not None and len(building_feature_set) > 0
    )
    if not fetched_anything:
        raise empty_geometry(
            "No supported features were found in the selected region."
        )

    processed = process_fabric(
        bbox,
        features,
        request.parameters,
        road_feature_set=road_feature_set,
        building_feature_set=building_feature_set,
    )
    if not any(not g.is_empty for g in processed.layers.values()):
        raise empty_geometry(
            "The selected features produced no drawable area at this detail level."
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


def generate_mesh(
    request: GenerateMeshRequest,
    provider: GeographicDataProvider | None = None,
    elevation_provider: ElevationProvider | None = None,
) -> bytes:
    """Fetch building footprints and extrude them into a watertight STL mesh.

    When `terrain.include` (default True), buildings are seated on real
    ground elevation and fused onto a solid terrain slab with a flat bottom
    (printable as one piece). When False, buildings sit on a flat z=0 plane
    with no terrain fetch (faster, network-lighter iteration path).
    """
    bbox = request.selection
    _validate_bbox(bbox)
    _check_area(bbox)

    provider = provider or OSMProvider()
    building_feature_set = provider.fetch_buildings(
        bbox.west, bbox.south, bbox.east, bbox.north
    )
    if len(building_feature_set) == 0:
        raise empty_geometry(
            "No building footprints were found in the selected region."
        )

    processed = process_fabric(
        bbox, {"buildings"}, request.parameters, building_feature_set=building_feature_set
    )
    if not processed.buildings_3d:
        raise empty_geometry(
            "The selected buildings produced no extrudable mesh at this detail level."
        )

    if not request.terrain.include:
        vertices, faces = build_scene_mesh(processed.buildings_3d)
        if len(faces) == 0:
            raise empty_geometry("Mesh extrusion produced no triangles.")
        return write_stl_binary(vertices, faces)

    elevation_provider = elevation_provider or TerrariumElevationProvider()
    grid = sample_elevation_grid(
        processed.frame.bounds,
        processed.projection,
        elevation_provider,
        request.terrain.resolution_m,
        request.terrain.exaggeration,
    )
    terrain_mesh = build_terrain_mesh(grid, request.terrain.base_thickness_m)

    seated_buildings = [
        (footprint, height, building_base_z(footprint, grid, request.terrain.base_thickness_m))
        for footprint, height in processed.buildings_3d
    ]
    buildings_mesh = build_scene_mesh_with_base(seated_buildings)

    vertices, faces = merge_meshes([terrain_mesh, buildings_mesh])
    if len(faces) == 0:
        raise empty_geometry("Mesh extrusion produced no triangles.")

    return write_stl_binary(vertices, faces)
