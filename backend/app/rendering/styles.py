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
    block_fill: str  # interior of a city block (frame minus roads)
    building_fill: str  # individual building footprint
    water_fill: str  # water bodies (lakes, rivers, reservoirs)
    park_fill: str  # parks, woods, forests
    # Outlines for water/parks. A crisp stroke keeps these regions legible even
    # when their fill is a near-neighbour of block_fill (which was the "no water
    # or parks visible" bug — fills alone weren't enough, especially in
    # monochrome and in downscaled previews). See rendering/svg.py.
    water_stroke: str
    park_stroke: str
    area_stroke_width: float  # px on the 1600px canvas
    # Pixel margin inside the SVG canvas.
    margin: float


PRESETS: dict[str, FabricStyle] = {
    # Dark background, light roads. Blocks/buildings read as bright mass on
    # near-black ground, roads as slightly brighter cuts through it.
    "dark-minimal": FabricStyle(
        name="dark-minimal",
        background="#0d0d0f",
        road="#f5f5f5",
        block_fill="#3a3d47",
        # Water/parks were near-black (#1e3a4a / #2f4033) and read as empty
        # background — lifted to clearly legible teal/green (well above the grey
        # block fill in luminance) plus a brighter outline.
        building_fill="#e8e9ee",
        water_fill="#2f7a9c",
        park_fill="#3f8a5f",
        water_stroke="#7cc3e0",
        park_stroke="#77c98f",
        area_stroke_width=2.0,
        margin=48.0,
    ),
    # White background, black fill — the classic architectural figure-ground
    # look (Nolli-style): buildings/blocks as solid black mass, streets as the
    # white gaps between them.
    "architectural-monochrome": FabricStyle(
        name="architectural-monochrome",
        background="#ffffff",
        road="#101010",
        block_fill="#c9c9c9",
        building_fill="#101010",
        # Distinctly darker than the light block_fill (#c9c9c9) so the ground
        # cover reads as its own mass, each delimited by a dark outline.
        water_fill="#7f97a8",
        park_fill="#94a888",
        water_stroke="#3a4b57",
        park_stroke="#3f4d38",
        area_stroke_width=2.0,
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
