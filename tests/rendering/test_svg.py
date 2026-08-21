from __future__ import annotations

import xml.etree.ElementTree as ET

from app.geometry.processing import process_fabric
from app.models.schemas import BBoxSelection, Parameters
from app.rendering.styles import get_style
from app.rendering.svg import render_svg

from ..fixtures import BBOX, grid_feature_set


def _render(preset: str = "dark-minimal", size: int = 800) -> str:
    processed = process_fabric(grid_feature_set(), BBoxSelection(**BBOX), Parameters())
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
