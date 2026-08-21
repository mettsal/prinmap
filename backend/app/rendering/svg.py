"""SVG renderer (DESIGN.md §19, §20).

Consumes a ProcessedFabric (projected metres, one geometry per requested
layer) + a FabricStyle and emits an SVG string. Normalizes the projected frame
into the canvas, preserving aspect ratio, and flips Y (geographic north is up;
SVG y grows down). Layers are drawn in a fixed painter's order — blocks (base
mass), then parks/water (ground cover), then buildings (finer mass), then
roads (cuts/lines on top) — and a layer is only emitted if it was actually
requested and non-empty.
"""

from __future__ import annotations

from typing import Callable
from xml.sax.saxutils import escape

from ..geometry.collections import iter_polygons
from ..geometry.processing import ProcessedFabric
from .styles import FabricStyle

# (layer key, style attribute name) in paint order, back to front. Parks then
# water: water is drawn after (so it visually wins on the rare OSM overlap),
# both below buildings/roads which should read as foreground regardless of
# what ground cover they sit on.
_LAYER_ORDER = [
    ("blocks", "block_fill"),
    ("parks", "park_fill"),
    ("water", "water_fill"),
    ("buildings", "building_fill"),
    ("roads", "road"),
]


def _ring_to_path(coords, project: Callable[[float, float], tuple[float, float]]) -> str:
    pieces = []
    for i, (x, y) in enumerate(coords):
        px, py = project(x, y)
        cmd = "M" if i == 0 else "L"
        pieces.append(f"{cmd}{px:.2f} {py:.2f}")
    pieces.append("Z")
    return "".join(pieces)


def _geometry_to_path(geom, project: Callable[[float, float], tuple[float, float]]) -> str:
    subpaths = []
    for polygon in iter_polygons(geom):
        subpaths.append(_ring_to_path(polygon.exterior.coords, project))
        for interior in polygon.interiors:
            subpaths.append(_ring_to_path(interior.coords, project))
    return "".join(subpaths)


def render_svg(processed: ProcessedFabric, style: FabricStyle, size: int = 1600) -> str:
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

    bg = escape(style.background)
    groups = [
        "  <g id=\"background\">\n"
        f'    <rect x="0" y="0" width="{size}" height="{size}" fill="{bg}" />\n'
        "  </g>\n"
    ]

    for layer_key, style_attr in _LAYER_ORDER:
        geometry = processed.layers.get(layer_key)
        if geometry is None or geometry.is_empty:
            continue
        path_d = _geometry_to_path(geometry, project)
        if not path_d:
            continue
        fill = escape(getattr(style, style_attr))
        groups.append(
            f'  <g id="{layer_key}">\n'
            f'    <path d="{path_d}" fill="{fill}" fill-rule="evenodd" />\n'
            "  </g>\n"
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">\n' + "".join(groups) + "</svg>\n"
    )
