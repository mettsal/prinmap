"""The urban-fabric geometry pipeline (DESIGN.md §16, §18, and Phase 2A/2B).

Input:  road centrelines and/or building footprints (WGS84) + a bbox + params.
Output: a ProcessedFabric holding one merged 2D polygon layer per requested
        feature (roads / buildings / blocks) in projected metres, plus the
        per-building (footprint, height) list used by the 3D extrusion path.

Everything here is pure and unit-testable with synthetic geometry — no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

from ..models.schemas import BBoxSelection, Parameters
from ..providers.base import AreaFeatureSet, BuildingFeatureSet, GeographicFeatureSet
from ..rendering.styles import base_width
from .collections import iter_lines, iter_polygons
from .projection import Projection, projection_for

EMPTY_POLYGON: BaseGeometry = Polygon()

# Road-class tiers used to drop minor roads at low detail levels.
_MAJOR = {"motorway", "trunk", "primary", "secondary"}
_MID = {"tertiary", "unclassified", "living_street", "pedestrian"}
# everything else counts as minor (residential, service, track, ...)

# City-block interior slivers smaller than this (m²) are discarded as noise.
MIN_BLOCK_AREA_M2 = 15.0
# Building footprint fragments smaller than this (m²) are discarded as noise.
MIN_BUILDING_AREA_M2 = 4.0


@dataclass
class ProcessedFabric:
    layers: dict[str, BaseGeometry] = field(default_factory=dict)  # 2D fill layers for SVG
    buildings_3d: list[tuple[BaseGeometry, float]] = field(default_factory=list)  # (footprint, height_m)
    frame: BaseGeometry = EMPTY_POLYGON  # projected bbox rectangle
    projection: Optional[Projection] = None
    bbox: Optional[BBoxSelection] = None
    metadata: dict = field(default_factory=dict)
    # Always populated when their feature_set is given, independent of the
    # `features` toggle — the 3D pipeline (apply_surface_treatments) needs
    # these masks even when the corresponding 2D layer isn't rendered.
    road_area: BaseGeometry = EMPTY_POLYGON
    water_area: BaseGeometry = EMPTY_POLYGON
    park_area: BaseGeometry = EMPTY_POLYGON


def normalize_detail(detail: float) -> float:
    """Accept either 0..1 or 0..100 and clamp to 0..1."""
    d = detail / 100.0 if detail > 1.0 else detail
    return max(0.0, min(1.0, d))


def _allowed_classes(detail: float) -> set[str] | None:
    """Return the set of allowed road classes, or None meaning 'all classes'."""
    if detail < 0.34:
        return set(_MAJOR)
    if detail < 0.67:
        return set(_MAJOR) | set(_MID)
    return None  # keep everything


def _build_frame(bbox: BBoxSelection, proj: Projection) -> BaseGeometry:
    # Projected frame (may be slightly non-axis-aligned after projection; using
    # the corner extremes gives a safe rectangular clip window).
    minx, miny = proj.forward(bbox.west, bbox.south)
    maxx, maxy = proj.forward(bbox.east, bbox.north)
    minx, maxx = sorted((minx, maxx))
    miny, maxy = sorted((miny, maxy))
    return box(minx, miny, maxx, maxy)


def process_roads(
    feature_set: GeographicFeatureSet,
    frame: BaseGeometry,
    proj: Projection,
    parameters: Parameters,
) -> tuple[BaseGeometry, dict]:
    """Clip -> simplify -> buffer -> union road centrelines into a road-area mask."""
    detail = normalize_detail(parameters.detail)
    width_mult = max(0.1, parameters.road_width)
    tolerance = (1.0 - detail) * 15.0  # metres of Douglas-Peucker simplification
    min_length = (1.0 - detail) * 40.0  # drop segments shorter than this
    allowed = _allowed_classes(detail)

    buffered: list[BaseGeometry] = []
    kept = 0
    for feature in feature_set.features:
        if allowed is not None and feature.road_class not in allowed:
            continue
        projected = transform(proj.fwd_xy, feature.geometry)
        clipped = projected.intersection(frame)
        if clipped.is_empty:
            continue
        radius = base_width(feature.road_class) * width_mult / 2.0
        for segment in iter_lines(clipped):
            if segment.length < min_length:
                continue
            if tolerance > 0:
                segment = segment.simplify(tolerance)
            buffered.append(segment.buffer(radius, quad_segs=6))
            kept += 1

    geometry = EMPTY_POLYGON if not buffered else unary_union(buffered).intersection(frame)
    stats = {"input_road_features": len(feature_set), "kept_road_segments": kept}
    return geometry, stats


def process_buildings(
    feature_set: BuildingFeatureSet,
    frame: BaseGeometry,
    proj: Projection,
    parameters: Parameters,
) -> tuple[list[tuple[BaseGeometry, float]], dict]:
    """Reproject -> clip -> lightly simplify building footprints.

    Returns the per-building (footprint polygon, height_m) list. Footprints are
    clipped to the selection frame, so a building straddling the boundary gets a
    flat cut face — an accepted MVP limitation for both the 2D fill and 3D mesh.
    """
    detail = normalize_detail(parameters.detail)
    tolerance = (1.0 - detail) * 1.0  # buildings are small; simplify gently

    footprints: list[tuple[BaseGeometry, float]] = []
    for feature in feature_set.features:
        projected = transform(proj.fwd_xy, feature.geometry)
        clipped = projected.intersection(frame)
        if clipped.is_empty:
            continue
        for poly in iter_polygons(clipped):
            if tolerance > 0:
                poly = poly.simplify(tolerance, preserve_topology=True)
            if poly.is_empty or not poly.is_valid or poly.area < MIN_BUILDING_AREA_M2:
                continue
            footprints.append((poly, feature.height_m))

    stats = {"input_building_features": len(feature_set), "kept_buildings": len(footprints)}
    return footprints, stats


def process_landuse(
    feature_set: AreaFeatureSet,
    frame: BaseGeometry,
    proj: Projection,
    tolerance_m: float = 2.0,
) -> tuple[BaseGeometry, dict]:
    """Reproject -> clip -> union -> light simplify water/park polygons.

    Unlike roads, water/park boundaries aren't hierarchy-filtered by `detail`,
    so this uses a small fixed tolerance rather than a detail-scaled one.
    """
    polys: list[BaseGeometry] = []
    for feature in feature_set.features:
        projected = transform(proj.fwd_xy, feature.geometry)
        clipped = projected.intersection(frame)
        if clipped.is_empty:
            continue
        polys.extend(iter_polygons(clipped))

    if not polys:
        return EMPTY_POLYGON, {"input_area_features": len(feature_set), "kept_area_polygons": 0}

    merged = unary_union(polys)
    if tolerance_m > 0:
        merged = merged.simplify(tolerance_m, preserve_topology=True)
    stats = {
        "input_area_features": len(feature_set),
        "kept_area_polygons": len(list(iter_polygons(merged))),
    }
    return merged, stats


def process_blocks(road_geometry: BaseGeometry, frame: BaseGeometry) -> BaseGeometry:
    """The interior of city blocks — whatever is inside the frame but outside roads."""
    blocks = frame if road_geometry.is_empty else frame.difference(road_geometry)
    if blocks.is_empty:
        return EMPTY_POLYGON
    kept = [p for p in iter_polygons(blocks) if p.area >= MIN_BLOCK_AREA_M2]
    if not kept:
        return EMPTY_POLYGON
    return kept[0] if len(kept) == 1 else MultiPolygon(kept)


def process_fabric(
    bbox: BBoxSelection,
    features: set[str],
    parameters: Parameters,
    road_feature_set: GeographicFeatureSet | None = None,
    building_feature_set: BuildingFeatureSet | None = None,
    water_feature_set: AreaFeatureSet | None = None,
    park_feature_set: AreaFeatureSet | None = None,
) -> ProcessedFabric:
    """Orchestrate the layered pipeline for whichever feature layers were requested.

    `road_feature_set` should be provided whenever "roads" or "blocks" is in
    `features` (blocks are derived from the street network even if roads
    themselves aren't rendered); `building_feature_set` whenever "buildings" is
    requested. `water_feature_set`/`park_feature_set`, when given, are always
    processed into `ProcessedFabric.water_area`/`park_area` regardless of
    whether "water"/"parks" is in `features` — the 3D surface-treatment pass
    needs these masks even when the 2D layer itself isn't rendered.
    """
    center_lon = (bbox.west + bbox.east) / 2.0
    center_lat = (bbox.south + bbox.north) / 2.0
    proj = projection_for(center_lon, center_lat)
    frame = _build_frame(bbox, proj)

    layers: dict[str, BaseGeometry] = {}
    buildings_3d: list[tuple[BaseGeometry, float]] = []
    stats: dict = {}

    road_geometry = EMPTY_POLYGON
    if road_feature_set is not None:
        road_geometry, road_stats = process_roads(road_feature_set, frame, proj, parameters)
        stats.update(road_stats)
        if "roads" in features:
            layers["roads"] = road_geometry

    if building_feature_set is not None and "buildings" in features:
        buildings_3d, building_stats = process_buildings(building_feature_set, frame, proj, parameters)
        stats.update(building_stats)
        if buildings_3d:
            layers["buildings"] = unary_union([poly for poly, _ in buildings_3d])

    water_geometry = EMPTY_POLYGON
    if water_feature_set is not None:
        water_geometry, water_stats = process_landuse(water_feature_set, frame, proj)
        stats.update({f"water_{k}": v for k, v in water_stats.items()})
        if "water" in features:
            layers["water"] = water_geometry

    park_geometry = EMPTY_POLYGON
    if park_feature_set is not None:
        park_geometry, park_stats = process_landuse(park_feature_set, frame, proj)
        stats.update({f"park_{k}": v for k, v in park_stats.items()})
        if "parks" in features:
            layers["parks"] = park_geometry

    if "blocks" in features:
        layers["blocks"] = process_blocks(road_geometry, frame)

    metadata = {
        "crs_epsg": proj.epsg,
        "detail": normalize_detail(parameters.detail),
        "road_width": max(0.1, parameters.road_width),
        "features": sorted(features),
        "frame_bounds_m": list(frame.bounds),
        "bbox": {
            "west": bbox.west,
            "south": bbox.south,
            "east": bbox.east,
            "north": bbox.north,
        },
        **stats,
    }

    return ProcessedFabric(
        layers=layers,
        buildings_3d=buildings_3d,
        frame=frame,
        projection=proj,
        bbox=bbox,
        metadata=metadata,
        road_area=road_geometry,
        water_area=water_geometry,
        park_area=park_geometry,
    )
