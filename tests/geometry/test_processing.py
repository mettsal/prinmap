from __future__ import annotations

from app.geometry.processing import normalize_detail, process_fabric
from app.models.schemas import BBoxSelection, Parameters

from ..fixtures import BBOX, grid_feature_set


def _bbox() -> BBoxSelection:
    return BBoxSelection(**BBOX)


def test_normalize_detail_accepts_both_scales():
    assert normalize_detail(0.5) == 0.5
    assert normalize_detail(75) == 0.75
    assert normalize_detail(-3) == 0.0
    assert normalize_detail(200) == 1.0


def test_process_produces_non_empty_area_within_frame():
    processed = process_fabric(grid_feature_set(), _bbox(), Parameters(detail=0.75, road_width=2.0))
    assert not processed.geometry.is_empty
    assert processed.geometry.area > 0
    # Road area must stay within the projected selection frame.
    assert processed.frame.buffer(1.0).contains(processed.geometry)
    assert processed.metadata["kept_segments"] > 0


def test_low_detail_drops_minor_roads():
    low = process_fabric(grid_feature_set(), _bbox(), Parameters(detail=0.1, road_width=2.0))
    high = process_fabric(grid_feature_set(), _bbox(), Parameters(detail=0.9, road_width=2.0))
    # Low detail keeps only major classes -> fewer kept segments.
    assert low.metadata["kept_segments"] < high.metadata["kept_segments"]


def test_wider_roads_produce_more_area():
    thin = process_fabric(grid_feature_set(), _bbox(), Parameters(detail=0.8, road_width=1.0))
    thick = process_fabric(grid_feature_set(), _bbox(), Parameters(detail=0.8, road_width=4.0))
    assert thick.geometry.area > thin.geometry.area


def test_uses_utm_zone_23_south_for_sao_paulo():
    processed = process_fabric(grid_feature_set(), _bbox(), Parameters())
    assert processed.metadata["crs_epsg"] == 32723
