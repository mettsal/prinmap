"""Generation orchestration — ties provider -> geometry -> renderer together.

Kept separate from the FastAPI layer so it can be driven from tests or a CLI
without HTTP.
"""

from __future__ import annotations

import uuid

from .config import settings
from .errors import empty_geometry, invalid_selection, selection_too_large
from .geometry.extrude import build_scene_mesh, build_scene_mesh_with_base
from .geometry.mesh_utils import merge_meshes, print_scale_mm_per_m, scale_mesh_to_print
from .geometry.processing import process_fabric
from .geometry.projection import projection_for
from .geometry.terrain import (
    apply_surface_treatments,
    building_base_z,
    build_terrain_mesh,
    sample_elevation_grid,
)
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

KNOWN_FEATURES = {"roads", "buildings", "blocks", "water", "parks"}


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

    water_feature_set = None
    if "water" in features:
        water_feature_set = provider.fetch_water(bbox.west, bbox.south, bbox.east, bbox.north)

    park_feature_set = None
    if "parks" in features:
        park_feature_set = provider.fetch_parks(bbox.west, bbox.south, bbox.east, bbox.north)

    fetched_anything = (
        (road_feature_set is not None and len(road_feature_set) > 0)
        or (building_feature_set is not None and len(building_feature_set) > 0)
        or (water_feature_set is not None and len(water_feature_set) > 0)
        or (park_feature_set is not None and len(park_feature_set) > 0)
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
        water_feature_set=water_feature_set,
        park_feature_set=park_feature_set,
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


# Smallest common surface road width (metres) — a residential street — used
# only to warn when the chosen print scale makes fine streets thinner than one
# extruded line (see rendering/styles.py::ROAD_WIDTHS).
_TYPICAL_MINOR_ROAD_WIDTH_M = 2.5


def generate_mesh(
    request: GenerateMeshRequest,
    provider: GeographicDataProvider | None = None,
    elevation_provider: ElevationProvider | None = None,
) -> tuple[bytes, dict]:
    """Fetch building footprints and extrude them into a watertight STL mesh,
    emitted **pre-scaled to a real printed size** (`terrain.print_size_mm`).

    When `terrain.include` (default True), buildings are seated on real
    ground elevation and fused onto a solid terrain slab with a flat bottom
    (printable as one piece). When False, buildings sit on a flat z=0 plane
    with no terrain fetch (faster, network-lighter iteration path).

    Returns `(stl_bytes, print_info)` — `print_info` carries the derived scale
    and any printability warnings (surfaced to the client as response headers).
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

    # Roads/water/parks only matter for the terrain-treatment pass, so only
    # fetch them when terrain is actually requested — keeps the flat/no-DEM
    # path exactly as fast/network-light as before this feature existed.
    road_feature_set = None
    water_feature_set = None
    park_feature_set = None
    if request.terrain.include:
        road_feature_set = provider.fetch_roads(
            bbox.west, bbox.south, bbox.east, bbox.north, DEFAULT_ROAD_CLASSES
        )
        water_feature_set = provider.fetch_water(bbox.west, bbox.south, bbox.east, bbox.north)
        park_feature_set = provider.fetch_parks(bbox.west, bbox.south, bbox.east, bbox.north)

    processed = process_fabric(
        bbox,
        {"buildings"},
        request.parameters,
        road_feature_set=road_feature_set,
        building_feature_set=building_feature_set,
        water_feature_set=water_feature_set,
        park_feature_set=park_feature_set,
    )
    if not processed.buildings_3d:
        raise empty_geometry(
            "The selected buildings produced no extrudable mesh at this detail level."
        )

    terrain = request.terrain
    minx, miny, _, _ = processed.frame.bounds
    mm_per_m = print_scale_mm_per_m(processed.frame.bounds, terrain.print_size_mm)
    print_info = _print_info(processed.frame.bounds, mm_per_m, terrain, request.parameters)

    if not terrain.include:
        vertices, faces = build_scene_mesh(processed.buildings_3d)
        if len(faces) == 0:
            raise empty_geometry("Mesh extrusion produced no triangles.")
        vertices = scale_mesh_to_print(vertices, mm_per_m, minx, miny)
        return write_stl_binary(vertices, faces), print_info

    # Author every treatment in printed-millimetres, clamp to a printable floor
    # (>= 2 layer heights so it never lands below the printer's resolution),
    # then convert to the world metres apply_surface_treatments/build_terrain_mesh
    # operate in. After the whole mesh is scaled by mm_per_m these come back out
    # at their intended printed depth.
    min_relief_mm = 2.0 * terrain.layer_height_mm

    def _world_m(printed_mm: float) -> float:
        return max(printed_mm, min_relief_mm) / mm_per_m

    base_thickness_m = terrain.base_thickness_mm / mm_per_m  # plinth: no relief floor needed

    elevation_provider = elevation_provider or TerrariumElevationProvider()
    grid = sample_elevation_grid(
        processed.frame.bounds,
        processed.projection,
        elevation_provider,
        terrain.resolution_m,
        terrain.exaggeration,
        max_grid_points_per_axis=terrain.max_grid_points_per_axis,
    )
    grid = apply_surface_treatments(
        grid,
        road_area=processed.road_area,
        water_area=processed.water_area,
        park_area=processed.park_area,
        street_style=terrain.street_style,
        street_recess_depth_m=_world_m(terrain.street_recess_depth_mm),
        street_texture_amplitude_m=_world_m(terrain.street_texture_amplitude_mm),
        park_texture_amplitude_m=_world_m(terrain.park_texture_amplitude_mm),
        water_submersion_m=_world_m(terrain.water_submersion_mm),
    )
    terrain_mesh = build_terrain_mesh(grid, base_thickness_m)

    # Buildings seat on the POST-treatment grid, so they correctly fuse with
    # whatever the final surface looks like (e.g. a building at a recessed
    # street edge or a flattened water shore) — see AGENTS.md.
    seated_buildings = [
        (footprint, height, building_base_z(footprint, grid, base_thickness_m))
        for footprint, height in processed.buildings_3d
    ]
    buildings_mesh = build_scene_mesh_with_base(seated_buildings)

    vertices, faces = merge_meshes([terrain_mesh, buildings_mesh])
    if len(faces) == 0:
        raise empty_geometry("Mesh extrusion produced no triangles.")

    vertices = scale_mesh_to_print(vertices, mm_per_m, minx, miny)
    return write_stl_binary(vertices, faces), print_info


def _print_info(frame_bounds, mm_per_m, terrain, parameters) -> dict:
    """Derive human-facing print-scale facts + printability warnings.

    Warnings cover the one thing the print-scale fix *can't* rescue: horizontal
    features (fine streets) that, once scaled, are thinner than a single nozzle
    line — the user must pick a smaller selection or a larger print size.
    """
    minx, miny, maxx, maxy = frame_bounds
    scale_denominator = 1000.0 / mm_per_m if mm_per_m else 0.0  # world_mm : print_mm
    width_mm = (maxx - minx) * mm_per_m
    height_mm = (maxy - miny) * mm_per_m

    warnings: list[str] = []
    minor_road_mm = _TYPICAL_MINOR_ROAD_WIDTH_M * max(0.1, parameters.road_width) * mm_per_m
    if terrain.include and minor_road_mm < terrain.nozzle_diameter_mm:
        # Kept ASCII-only: this string is emitted as an HTTP header (latin-1).
        warnings.append(
            f"At 1:{round(scale_denominator):,}, minor streets are ~{minor_road_mm:.2f} mm wide, "
            f"below the {terrain.nozzle_diameter_mm} mm nozzle. Fine streets may not print; "
            f"pick a smaller area or a larger print size."
        )

    return {
        "print_size_mm": terrain.print_size_mm,
        "scale_denominator": round(scale_denominator),
        "model_footprint_mm": [round(width_mm, 1), round(height_mm, 1)],
        "warnings": warnings,
    }
