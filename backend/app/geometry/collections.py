"""Helpers for flattening (Multi)geometry / GeometryCollection results.

Shared by processing, SVG rendering, and mesh extrusion so all three walk
Shapely's multi-part geometries the same way.
"""

from __future__ import annotations

from typing import Iterator

from shapely.geometry.base import BaseGeometry


def iter_lines(geom: BaseGeometry) -> Iterator[BaseGeometry]:
    if geom.is_empty:
        return
    gtype = geom.geom_type
    if gtype == "LineString":
        yield geom
    elif gtype in ("MultiLineString", "GeometryCollection"):
        for part in geom.geoms:
            yield from iter_lines(part)


def iter_polygons(geom: BaseGeometry) -> Iterator[BaseGeometry]:
    if geom.is_empty:
        return
    gtype = geom.geom_type
    if gtype == "Polygon":
        yield geom
    elif gtype in ("MultiPolygon", "GeometryCollection"):
        for part in geom.geoms:
            yield from iter_polygons(part)
