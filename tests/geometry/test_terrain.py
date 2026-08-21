from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.geometry.projection import projection_for
from app.geometry.terrain import (
    MAX_GRID_POINTS_PER_AXIS,
    PARK_TEXTURE_AMPLITUDE_M,
    STREET_TEXTURE_AMPLITUDE_M,
    WATER_SUBMERSION_M,
    apply_surface_treatments,
    build_terrain_mesh,
    building_base_z,
    sample_elevation_grid,
    terrain_floor_z,
)

from ..fixtures import BBOX, FakeElevationProvider
from .euler import euler_characteristic

PROJ = projection_for((BBOX["west"] + BBOX["east"]) / 2, (BBOX["south"] + BBOX["north"]) / 2)
EMPTY = Polygon()


def _frame_bounds():
    minx, miny = PROJ.forward(BBOX["west"], BBOX["south"])
    maxx, maxy = PROJ.forward(BBOX["east"], BBOX["north"])
    return (min(minx, maxx), min(miny, maxy), max(minx, maxx), max(miny, maxy))


def test_flat_grid_produces_correct_z_range():
    # A perfectly flat real-world elevation (regardless of its absolute value
    # above sea level, e.g. 100m ASL here) normalizes to relief=0 -> z=0 —
    # absolute elevation-above-sea-level is irrelevant to a printed model;
    # only local relief should show up in the mesh's Z coordinates.
    grid = sample_elevation_grid(_frame_bounds(), PROJ, FakeElevationProvider(base_elevation=100.0), resolution_m=50.0)
    assert grid.elevations.min() == grid.elevations.max() == 0.0

    vertices, faces = build_terrain_mesh(grid, base_thickness_m=3.0)
    euler, watertight = euler_characteristic(vertices, faces)
    assert watertight
    assert euler == 2  # single genus-0 solid
    assert vertices[:, 2].max() == 0.0
    assert vertices[:, 2].min() == -3.0


def test_sloped_grid_is_watertight_and_varies():
    grid = sample_elevation_grid(
        _frame_bounds(), PROJ, FakeElevationProvider(base_elevation=10.0, slope_m_per_deg_lon=5000.0), resolution_m=50.0
    )
    assert grid.elevations.max() - grid.elevations.min() > 1.0

    vertices, faces = build_terrain_mesh(grid, base_thickness_m=3.0)
    euler, watertight = euler_characteristic(vertices, faces)
    assert watertight
    assert euler == 2


def test_grid_size_is_clamped():
    grid = sample_elevation_grid(_frame_bounds(), PROJ, FakeElevationProvider(), resolution_m=0.01)
    ny, nx = grid.elevations.shape
    assert nx <= MAX_GRID_POINTS_PER_AXIS
    assert ny <= MAX_GRID_POINTS_PER_AXIS


def test_building_base_z_seats_on_lowest_corner_and_clamps_to_floor():
    grid = sample_elevation_grid(
        _frame_bounds(), PROJ, FakeElevationProvider(base_elevation=50.0, slope_m_per_deg_lon=10000.0), resolution_m=50.0
    )
    minx, miny, maxx, maxy = _frame_bounds()
    footprint = Polygon(
        [
            (minx + 50, miny + 50),
            (minx + 100, miny + 50),
            (minx + 100, miny + 100),
            (minx + 50, miny + 100),
            (minx + 50, miny + 50),
        ]
    )
    base_z = building_base_z(footprint, grid, base_thickness_m=3.0)
    floor_z = terrain_floor_z(grid, base_thickness_m=3.0)

    # Should sit at/below the lowest sampled corner, never below the terrain's own floor.
    lowest_corner = min(grid.sample_bilinear(x, y) for x, y in footprint.exterior.coords)
    assert base_z <= lowest_corner
    assert base_z >= floor_z


def test_building_base_z_never_sinks_below_terrain_floor_on_steep_slope():
    # An extreme slope could push (min_corner - sink) below the terrain's flat
    # floor if unclamped; base_z must never do that.
    grid = sample_elevation_grid(
        _frame_bounds(), PROJ, FakeElevationProvider(base_elevation=0.0, slope_m_per_deg_lon=1_000_000.0), resolution_m=50.0
    )
    minx, miny, maxx, maxy = _frame_bounds()
    footprint = Polygon(
        [
            (minx + 1, miny + 1),
            (minx + 10, miny + 1),
            (minx + 10, miny + 10),
            (minx + 1, miny + 10),
            (minx + 1, miny + 1),
        ]
    )
    base_z = building_base_z(footprint, grid, base_thickness_m=3.0)
    assert base_z >= terrain_floor_z(grid, base_thickness_m=3.0)


def _flat_grid(resolution_m: float = 20.0):
    return sample_elevation_grid(
        _frame_bounds(), PROJ, FakeElevationProvider(base_elevation=50.0), resolution_m=resolution_m
    )


def _mask_of(grid, geom):
    xx, yy = np.meshgrid(grid.xs, grid.ys)
    return shapely.contains_xy(geom, xx.ravel(), yy.ravel()).reshape(grid.elevations.shape)


def test_recessed_streets_are_lower_by_exact_depth():
    grid = _flat_grid()
    minx, miny, maxx, maxy = _frame_bounds()
    mid_y = (miny + maxy) / 2
    road = box(minx, mid_y - 15, maxx, mid_y + 15)
    treated = apply_surface_treatments(grid, road, EMPTY, EMPTY, street_style="recessed", street_recess_depth_m=0.6)
    mask = _mask_of(grid, road)
    assert np.allclose(treated.elevations[mask] - grid.elevations[mask], -0.6)
    assert np.allclose(treated.elevations[~mask], grid.elevations[~mask])


def test_textured_streets_stay_within_amplitude_range():
    grid = _flat_grid()
    minx, miny, maxx, maxy = _frame_bounds()
    mid_y = (miny + maxy) / 2
    road = box(minx, mid_y - 15, maxx, mid_y + 15)
    treated = apply_surface_treatments(grid, road, EMPTY, EMPTY, street_style="textured")
    mask = _mask_of(grid, road)
    diff = treated.elevations[mask] - grid.elevations[mask]
    assert diff.min() >= 0.0
    assert diff.max() == STREET_TEXTURE_AMPLITUDE_M
    assert np.allclose(treated.elevations[~mask], grid.elevations[~mask])


def test_park_texture_always_applies_regardless_of_street_style():
    grid = _flat_grid()
    minx, miny, maxx, maxy = _frame_bounds()
    park = box(minx + 20, miny + 20, minx + 120, miny + 120)
    for style in ("recessed", "textured"):
        treated = apply_surface_treatments(grid, EMPTY, EMPTY, park, street_style=style)
        mask = _mask_of(grid, park)
        diff = treated.elevations[mask] - grid.elevations[mask]
        assert diff.min() >= 0.0
        assert diff.max() == PARK_TEXTURE_AMPLITUDE_M


def test_water_is_flattened_to_single_value_below_boundary_min():
    grid = _flat_grid()
    minx, miny, maxx, maxy = _frame_bounds()
    water = box(minx + 20, miny + 20, minx + 120, miny + 120)
    treated = apply_surface_treatments(grid, EMPTY, water, EMPTY, street_style="recessed")
    mask = _mask_of(grid, water)
    values = np.unique(treated.elevations[mask])
    assert len(values) == 1
    boundary_min = min(grid.sample_bilinear(x, y) for x, y in water.exterior.coords)
    assert values[0] == boundary_min - WATER_SUBMERSION_M


def test_water_per_component_flattening_uses_own_component_boundary():
    # Two disjoint water bodies at different local elevations shouldn't
    # cross-contaminate each other's flattened value — proves per-component
    # (not one global min-of-boundary across all water) flattening.
    grid = sample_elevation_grid(
        _frame_bounds(), PROJ, FakeElevationProvider(base_elevation=0.0, slope_m_per_deg_lon=20000.0), resolution_m=20.0
    )
    minx, miny, maxx, maxy = _frame_bounds()
    low_water = box(minx + 10, miny + 10, minx + 60, miny + 60)
    high_water = box(maxx - 60, miny + 10, maxx - 10, miny + 60)
    water = unary_union([low_water, high_water])

    treated = apply_surface_treatments(grid, EMPTY, water, EMPTY, street_style="recessed")
    low_vals = np.unique(treated.elevations[_mask_of(grid, low_water)])
    high_vals = np.unique(treated.elevations[_mask_of(grid, high_water)])
    assert len(low_vals) == 1 and len(high_vals) == 1
    # Terrain slopes with longitude, so the two disjoint water bodies at
    # different x-ranges should flatten to genuinely different elevations.
    assert low_vals[0] != high_vals[0]


def test_overlap_priority_water_wins_over_road():
    grid = _flat_grid()
    minx, miny, maxx, maxy = _frame_bounds()
    water = box(minx + 20, miny + 20, minx + 120, miny + 120)
    road = box(minx + 20, miny + 20, minx + 120, miny + 200)  # fully covers water in x, extends past in y
    treated = apply_surface_treatments(grid, road, water, EMPTY, street_style="recessed", street_recess_depth_m=0.6)
    values = np.unique(treated.elevations[_mask_of(grid, water)])
    assert len(values) == 1
    boundary_min = min(grid.sample_bilinear(x, y) for x, y in water.exterior.coords)
    assert values[0] == boundary_min - WATER_SUBMERSION_M  # water's value, not the road-recessed one


def test_apply_surface_treatments_still_watertight():
    grid = _flat_grid()
    minx, miny, maxx, maxy = _frame_bounds()
    mid_y = (miny + maxy) / 2
    road = box(minx, mid_y - 15, maxx, mid_y + 15)
    water = box(minx + 20, miny + 20, minx + 90, miny + 90)
    park = box(maxx - 150, maxy - 150, maxx - 20, maxy - 20)
    treated = apply_surface_treatments(grid, road, water, park, street_style="textured")
    vertices, faces = build_terrain_mesh(treated, base_thickness_m=3.0)
    euler, watertight = euler_characteristic(vertices, faces)
    assert watertight
    assert euler == 2
