"""The urban-fabric geometry pipeline (DESIGN.md §16, §18).

Input:  a GeographicFeatureSet of road centrelines (WGS84) + a bbox + parameters.
Output: a ProcessedGeometry holding a merged road-area polygon in projected
        metres, plus the projected frame used for SVG normalization.

Everything here is pure and unit-testable with synthetic geometry — no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

from ..models.schemas import BBoxSelection, Parameters
from ..providers.base import GeographicFeatureSet
from ..rendering.styles import base_width
from .projection import Projection, projection_for

# Road-class tiers used to drop minor roads at low detail levels.
_MAJOR = {"motorway", "trunk", "primary", "secondary"}
_MID = {"tertiary", "unclassified", "living_street", "pedestrian"}
# everything else counts as minor (residential, service, track, ...)


@dataclass
class ProcessedGeometry:
    geometry: BaseGeometry  # (Multi)Polygon of road area, projected metres
    frame: BaseGeometry  # projected bbox rectangle used as the SVG frame
    projection: Projection
    bbox: BBoxSelection
    metadata: dict


def normalize_detail(detail: float) -> float:
    """Accept either 0..1 or 0..100 and clamp to 0..1."""
    d = detail / 100.0 if detail > 1.0 else detail
    return max(0.0, min(1.0, d))


def _allowed_classes(detail: float) -> set[str] | None:
    """Return the set of allowed classes, or None meaning 'all classes'."""
    if detail < 0.34:
        return set(_MAJOR)
    if detail < 0.67:
        return set(_MAJOR) | set(_MID)
    return None  # keep everything


def _iter_lines(geom: BaseGeometry) -> Iterator[BaseGeometry]:
    """Yield individual LineStrings from a possibly-multi/collection geometry."""
    if geom.is_empty:
        return
    gtype = geom.geom_type
    if gtype == "LineString":
        yield geom
    elif gtype in ("MultiLineString", "GeometryCollection"):
        for part in geom.geoms:
            yield from _iter_lines(part)


def process_fabric(
    feature_set: GeographicFeatureSet,
    bbox: BBoxSelection,
    parameters: Parameters,
) -> ProcessedGeometry:
    detail = normalize_detail(parameters.detail)
    width_mult = max(0.1, parameters.road_width)

    center_lon = (bbox.west + bbox.east) / 2.0
    center_lat = (bbox.south + bbox.north) / 2.0
    proj = projection_for(center_lon, center_lat)

    # Projected frame (may be slightly non-axis-aligned after projection; using
    # the corner extremes gives a safe rectangular clip window).
    minx, miny = proj.forward(bbox.west, bbox.south)
    maxx, maxy = proj.forward(bbox.east, bbox.north)
    minx, maxx = sorted((minx, maxx))
    miny, maxy = sorted((miny, maxy))
    frame = box(minx, miny, maxx, maxy)

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
        for segment in _iter_lines(clipped):
            if segment.length < min_length:
                continue
            if tolerance > 0:
                segment = segment.simplify(tolerance)
            buffered.append(segment.buffer(radius, quad_segs=6))
            kept += 1

    if not buffered:
        merged: BaseGeometry = box(0, 0, 0, 0).difference(box(0, 0, 0, 0))  # empty
    else:
        merged = unary_union(buffered).intersection(frame)

    metadata = {
        "crs_epsg": proj.epsg,
        "detail": detail,
        "road_width": width_mult,
        "input_features": len(feature_set),
        "kept_segments": kept,
        "frame_bounds_m": [minx, miny, maxx, maxy],
        "bbox": {
            "west": bbox.west,
            "south": bbox.south,
            "east": bbox.east,
            "north": bbox.north,
        },
    }
    return ProcessedGeometry(
        geometry=merged,
        frame=frame,
        projection=proj,
        bbox=bbox,
        metadata=metadata,
    )
