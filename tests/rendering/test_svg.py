from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.geometry.processing import process_fabric
from app.models.schemas import BBoxSelection, Parameters
from app.rendering.styles import PRESETS, get_style
from app.rendering.svg import render_svg

from ..fixtures import BBOX, building_feature_set, grid_feature_set, park_feature_set, water_feature_set


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


# Minimum perceptual gap (0..255 luminance) between a ground-cover fill and the
# block fill it sits on. Below this, water/parks read as empty block/background
# — the "no water or parks visible" regression this guards against.
_MIN_FILL_GAP = 35.0


def _render(preset: str = "dark-minimal", size: int = 800, features=None):
    features = features or {"roads"}
    processed = process_fabric(
        BBoxSelection(**BBOX),
        features,
        Parameters(),
        road_feature_set=grid_feature_set() if features & {"roads", "blocks"} else None,
        building_feature_set=building_feature_set() if "buildings" in features else None,
        water_feature_set=water_feature_set() if "water" in features else None,
        park_feature_set=park_feature_set() if "parks" in features else None,
    )
    return render_svg(processed, get_style(preset), size=size)


def test_svg_is_well_formed_and_structured():
    svg = _render(size=800)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.attrib["width"] == "800"
    assert root.attrib["viewBox"] == "0 0 800 800"
    group_ids = {g.attrib.get("id") for g in root.iter() if g.tag.endswith("g")}
    assert {"background", "roads"} <= group_ids


def test_svg_contains_road_path():
    svg = _render()
    assert "<path" in svg
    assert 'fill-rule="evenodd"' in svg


def test_style_changes_colors_only():
    dark = _render("dark-minimal")
    mono = _render("architectural-monochrome")
    assert "#0d0d0f" in dark
    assert "#ffffff" in mono
    assert "#101010" in mono


def test_layer_paint_order_blocks_buildings_roads():
    svg = _render(features={"roads", "buildings", "blocks"})
    root = ET.fromstring(svg)
    top_groups = [g.attrib.get("id") for g in root if g.tag.endswith("g")]
    assert top_groups == ["background", "blocks", "buildings", "roads"]


def test_buildings_only_svg_has_no_road_group():
    svg = _render(features={"buildings"})
    root = ET.fromstring(svg)
    group_ids = {g.attrib.get("id") for g in root if g.tag.endswith("g")}
    assert group_ids == {"background", "buildings"}


def test_water_and_parks_groups_present_when_requested():
    svg = _render(features={"water", "parks"})
    root = ET.fromstring(svg)
    group_ids = {g.attrib.get("id") for g in root if g.tag.endswith("g")}
    assert group_ids == {"background", "parks", "water"}


def test_water_and_parks_absent_when_not_requested():
    svg = _render(features={"roads"})
    root = ET.fromstring(svg)
    group_ids = {g.attrib.get("id") for g in root if g.tag.endswith("g")}
    assert "water" not in group_ids and "parks" not in group_ids


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_water_and_park_fills_are_distinct_from_blocks(preset):
    # Presence of a <g id="water"> group is not enough — the fill must actually
    # be distinguishable from the block fill it's painted over, in EVERY preset.
    style = PRESETS[preset]
    block = _luminance(style.block_fill)
    assert abs(_luminance(style.water_fill) - block) >= _MIN_FILL_GAP, preset
    assert abs(_luminance(style.park_fill) - block) >= _MIN_FILL_GAP, preset


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_water_and_park_paths_have_an_outline(preset):
    # Water/parks carry a stroke so the region stays legible even when the fill
    # is a near-neighbour of block_fill (belt-and-suspenders on top of the gap).
    svg = _render(preset, features={"water", "parks"})
    root = ET.fromstring(svg)
    for group_id in ("water", "parks"):
        group = next(g for g in root if g.tag.endswith("g") and g.attrib.get("id") == group_id)
        path = next(p for p in group if p.tag.endswith("path"))
        assert path.attrib.get("stroke"), f"{preset}/{group_id} has no stroke"
        assert float(path.attrib.get("stroke-width", 0)) > 0


def test_full_layer_paint_order_all_five():
    svg = _render(features={"roads", "buildings", "blocks", "water", "parks"})
    root = ET.fromstring(svg)
    top_groups = [g.attrib.get("id") for g in root if g.tag.endswith("g")]
    assert top_groups == ["background", "blocks", "parks", "water", "buildings", "roads"]
