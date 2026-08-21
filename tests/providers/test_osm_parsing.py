from __future__ import annotations

from app.providers.osm import (
    DEFAULT_BUILDING_HEIGHT_M,
    METERS_PER_LEVEL,
    parse_building_height,
)


def test_explicit_height_tag_wins():
    assert parse_building_height({"height": "12"}) == 12.0


def test_height_tag_with_unit_suffix():
    assert parse_building_height({"height": "12.5 m"}) == 12.5


def test_falls_back_to_levels_when_no_height():
    assert parse_building_height({"building:levels": "4"}) == 4 * METERS_PER_LEVEL


def test_height_tag_takes_priority_over_levels():
    assert parse_building_height({"height": "20", "building:levels": "4"}) == 20.0


def test_default_when_no_tags():
    assert parse_building_height({}) == DEFAULT_BUILDING_HEIGHT_M


def test_garbage_values_fall_back_to_default():
    assert parse_building_height({"height": "unknown"}) == DEFAULT_BUILDING_HEIGHT_M
    assert parse_building_height({"height": "-5"}) == DEFAULT_BUILDING_HEIGHT_M
