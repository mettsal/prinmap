from __future__ import annotations

from shapely.geometry import Polygon

from app.geometry.projection import projection_for
from app.geometry.terrain import (
    MAX_GRID_POINTS_PER_AXIS,
    build_terrain_mesh,
    building_base_z,
    sample_elevation_grid,
    terrain_floor_z,
)

from ..fixtures import BBOX, FakeElevationProvider
from .euler import euler_characteristic

PROJ = projection_for((BBOX["west"] + BBOX["east"]) / 2, (BBOX["south"] + BBOX["north"]) / 2)


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
