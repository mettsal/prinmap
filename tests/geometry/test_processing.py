from __future__ import annotations

from app.geometry.processing import _build_frame, normalize_detail, process_fabric, process_landuse
from app.geometry.projection import projection_for
from app.models.schemas import BBoxSelection, Parameters

from ..fixtures import BBOX, building_feature_set, grid_feature_set, park_feature_set, water_feature_set


def _bbox() -> BBoxSelection:
    return BBoxSelection(**BBOX)


def test_normalize_detail_accepts_both_scales():
    assert normalize_detail(0.5) == 0.5
    assert normalize_detail(75) == 0.75
    assert normalize_detail(-3) == 0.0
    assert normalize_detail(200) == 1.0


def test_process_roads_layer_is_non_empty_within_frame():
    processed = process_fabric(
        _bbox(),
        {"roads"},
        Parameters(detail=0.75, road_width=2.0),
        road_feature_set=grid_feature_set(),
    )
    roads = processed.layers["roads"]
    assert not roads.is_empty
    assert roads.area > 0
    assert processed.frame.buffer(1.0).contains(roads)
    assert processed.metadata["kept_road_segments"] > 0


def test_low_detail_drops_minor_roads():
    low = process_fabric(
        _bbox(), {"roads"}, Parameters(detail=0.1, road_width=2.0), road_feature_set=grid_feature_set()
    )
    high = process_fabric(
        _bbox(), {"roads"}, Parameters(detail=0.9, road_width=2.0), road_feature_set=grid_feature_set()
    )
    assert low.metadata["kept_road_segments"] < high.metadata["kept_road_segments"]


def test_wider_roads_produce_more_area():
    thin = process_fabric(
        _bbox(), {"roads"}, Parameters(detail=0.8, road_width=1.0), road_feature_set=grid_feature_set()
    )
    thick = process_fabric(
        _bbox(), {"roads"}, Parameters(detail=0.8, road_width=4.0), road_feature_set=grid_feature_set()
    )
    assert thick.layers["roads"].area > thin.layers["roads"].area


def test_uses_utm_zone_23_south_for_sao_paulo():
    processed = process_fabric(
        _bbox(), {"roads"}, Parameters(), road_feature_set=grid_feature_set()
    )
    assert processed.metadata["crs_epsg"] == 32723


def test_process_buildings_layer_and_3d_list():
    processed = process_fabric(
        _bbox(),
        {"buildings"},
        Parameters(),
        building_feature_set=building_feature_set(),
    )
    assert "buildings" in processed.layers
    assert not processed.layers["buildings"].is_empty
    assert len(processed.buildings_3d) == 4
    heights = sorted(h for _, h in processed.buildings_3d)
    assert heights == [6.0, 9.0, 15.0, 30.0]
    for footprint, _ in processed.buildings_3d:
        assert processed.frame.buffer(1.0).contains(footprint)


def test_process_blocks_fills_gaps_between_roads():
    processed = process_fabric(
        _bbox(), {"blocks"}, Parameters(detail=0.8), road_feature_set=grid_feature_set()
    )
    blocks = processed.layers["blocks"]
    assert not blocks.is_empty
    # Blocks must not overlap the road mask they were carved from.
    roads_only = process_fabric(
        _bbox(), {"roads"}, Parameters(detail=0.8), road_feature_set=grid_feature_set()
    ).layers["roads"]
    assert blocks.intersection(roads_only).area < 1.0


def test_all_three_layers_can_coexist():
    processed = process_fabric(
        _bbox(),
        {"roads", "buildings", "blocks"},
        Parameters(),
        road_feature_set=grid_feature_set(),
        building_feature_set=building_feature_set(),
    )
    assert set(processed.layers.keys()) == {"roads", "buildings", "blocks"}


def test_process_landuse_clips_unions_and_simplifies():
    bbox = _bbox()
    proj = projection_for((bbox.west + bbox.east) / 2, (bbox.south + bbox.north) / 2)
    frame = _build_frame(bbox, proj)
    geometry, stats = process_landuse(water_feature_set(), frame, proj)
    assert not geometry.is_empty
    assert geometry.area > 0
    assert frame.buffer(1.0).contains(geometry)
    assert stats["kept_area_polygons"] == 1


def test_water_and_parks_layers_populate_when_requested():
    processed = process_fabric(
        _bbox(),
        {"water", "parks"},
        Parameters(),
        water_feature_set=water_feature_set(),
        park_feature_set=park_feature_set(),
    )
    assert "water" in processed.layers and not processed.layers["water"].is_empty
    assert "parks" in processed.layers and not processed.layers["parks"].is_empty


def test_water_and_park_areas_populate_on_dataclass_even_when_not_in_features():
    # generate_mesh needs road_area/water_area/park_area for the 3D surface
    # treatment even when the 2D "water"/"parks" layers aren't requested.
    processed = process_fabric(
        _bbox(),
        {"buildings"},
        Parameters(),
        building_feature_set=building_feature_set(),
        water_feature_set=water_feature_set(),
        park_feature_set=park_feature_set(),
    )
    assert "water" not in processed.layers
    assert "parks" not in processed.layers
    assert not processed.water_area.is_empty
    assert not processed.park_area.is_empty
