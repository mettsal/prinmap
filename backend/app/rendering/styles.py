"""Visual style system (DESIGN.md §17, §21).

Style answers "how should the roads look?" and is deliberately decoupled from
geometry ("where are the roads?") and output ("how do we encode SVG?").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FabricStyle:
    name: str
    background: str
    road: str
    # Pixel margin inside the SVG canvas.
    margin: float


PRESETS: dict[str, FabricStyle] = {
    # Dark background, light roads.
    "dark-minimal": FabricStyle(
        name="dark-minimal",
        background="#0d0d0f",
        road="#f5f5f5",
        margin=48.0,
    ),
    # White background, black roads — the architectural reference look.
    "architectural-monochrome": FabricStyle(
        name="architectural-monochrome",
        background="#ffffff",
        road="#101010",
        margin=48.0,
    ),
}

DEFAULT_PRESET = "dark-minimal"


def get_style(preset: str) -> FabricStyle:
    return PRESETS.get(preset, PRESETS[DEFAULT_PRESET])


# Per-class base widths in metres (full stroke width, not radius). These give
# the road hierarchy; the user's `road_width` parameter multiplies them.
ROAD_WIDTHS: dict[str, float] = {
    "motorway": 8.0,
    "trunk": 7.0,
    "primary": 6.0,
    "secondary": 5.0,
    "tertiary": 4.0,
    "unclassified": 3.0,
    "residential": 2.5,
    "living_street": 2.2,
    "pedestrian": 2.0,
    "service": 1.5,
    "track": 1.2,
}
DEFAULT_WIDTH = 2.5


def base_width(road_class: str) -> float:
    return ROAD_WIDTHS.get(road_class, DEFAULT_WIDTH)
