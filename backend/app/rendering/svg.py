"""SVG renderer (DESIGN.md §19, §20).

Consumes a ProcessedGeometry (projected metres) + a FabricStyle and emits an SVG
string. Normalizes the projected frame into the canvas, preserving aspect ratio,
and flips Y (geographic north is up; SVG y grows down).
"""

from __future__ import annotations

from typing import Callable
from xml.sax.saxutils import escape

from shapely.geometry.base import BaseGeometry

from ..geometry.processing import ProcessedGeometry
from .styles import FabricStyle


def _iter_polygons(geom: BaseGeometry):
    if geom.is_empty:
        return
    gtype = geom.geom_type
    if gtype == "Polygon":
        yield geom
    elif gtype in ("MultiPolygon", "GeometryCollection"):
        for part in geom.geoms:
            yield from _iter_polygons(part)


def _ring_to_path(coords, project: Callable[[float, float], tuple[float, float]]) -> str:
    pieces = []
    for i, (x, y) in enumerate(coords):
        px, py = project(x, y)
        cmd = "M" if i == 0 else "L"
        pieces.append(f"{cmd}{px:.2f} {py:.2f}")
    pieces.append("Z")
    return "".join(pieces)


def _geometry_to_path(
    geom: BaseGeometry, project: Callable[[float, float], tuple[float, float]]
) -> str:
    subpaths = []
    for polygon in _iter_polygons(geom):
        subpaths.append(_ring_to_path(polygon.exterior.coords, project))
        for interior in polygon.interiors:
            subpaths.append(_ring_to_path(interior.coords, project))
    return "".join(subpaths)


def render_svg(processed: ProcessedGeometry, style: FabricStyle, size: int = 1600) -> str:
    minx, miny, maxx, maxy = processed.frame.bounds
    frame_w = max(maxx - minx, 1e-9)
    frame_h = max(maxy - miny, 1e-9)

    inner = max(size - 2.0 * style.margin, 1.0)
    scale = min(inner / frame_w, inner / frame_h)
    # Centre the scaled frame within the canvas.
    offset_x = style.margin + (inner - frame_w * scale) / 2.0
    offset_y = style.margin + (inner - frame_h * scale) / 2.0

    def project(x: float, y: float) -> tuple[float, float]:
        px = offset_x + (x - minx) * scale
        py = size - (offset_y + (y - miny) * scale)  # flip Y
        return px, py

    path_d = _geometry_to_path(processed.geometry, project)

    bg = escape(style.background)
    road = escape(style.road)
    roads_group = (
        f'    <path d="{path_d}" fill="{road}" fill-rule="evenodd" />\n'
        if path_d
        else ""
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">\n'
        f'  <g id="background">\n'
        f'    <rect x="0" y="0" width="{size}" height="{size}" fill="{bg}" />\n'
        f'  </g>\n'
        f'  <g id="roads">\n'
        f"{roads_group}"
        f'  </g>\n'
        f"</svg>\n"
    )
