from __future__ import annotations

import xml.etree.ElementTree as ET

from app.geometry.processing import process_fabric
from app.models.schemas import BBoxSelection, Parameters
from app.rendering.styles import get_style
from app.rendering.svg import render_svg

from ..fixtures import BBOX, building_feature_set, grid_feature_set, park_feature_set, water_feature_set


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


def test_full_layer_paint_order_all_five():
    svg = _render(features={"roads", "buildings", "blocks", "water", "parks"})
    root = ET.fromstring(svg)
    top_groups = [g.attrib.get("id") for g in root if g.tag.endswith("g")]
    assert top_groups == ["background", "blocks", "parks", "water", "buildings", "roads"]
