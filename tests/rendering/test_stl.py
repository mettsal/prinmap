from __future__ import annotations

import struct

from shapely.geometry import Polygon

from app.geometry.extrude import build_scene_mesh_with_base, extrude_polygon
from app.geometry.mesh_utils import merge_meshes
from app.geometry.projection import projection_for
from app.geometry.terrain import building_base_z, build_terrain_mesh, sample_elevation_grid
from app.rendering.stl import write_stl_binary

from ..fixtures import BBOX, FakeElevationProvider
from ..geometry.euler import euler_characteristic


def test_write_stl_binary_header_and_size():
    box = Polygon([(0, 0), (10, 0), (10, 6), (0, 6), (0, 0)])
    vertices, faces = extrude_polygon(box, height=9.0)
    data = write_stl_binary(vertices, faces, name=b"test")

    assert data[:4] == b"test" + b"\x00" * 0  # header starts with the name
    assert len(data[:80].rstrip(b"\x00")) == 4

    triangle_count = struct.unpack("<I", data[80:84])[0]
    assert triangle_count == len(faces)
    assert len(data) == 84 + triangle_count * 50


def test_write_stl_binary_empty_mesh():
    import numpy as np

    data = write_stl_binary(np.empty((0, 3)), np.empty((0, 3), dtype="uint32"))
    assert len(data) == 84
    assert struct.unpack("<I", data[80:84])[0] == 0


def test_merged_terrain_and_buildings_stl_is_watertight_and_valid():
    proj = projection_for((BBOX["west"] + BBOX["east"]) / 2, (BBOX["south"] + BBOX["north"]) / 2)
    minx, miny = proj.forward(BBOX["west"], BBOX["south"])
    maxx, maxy = proj.forward(BBOX["east"], BBOX["north"])
    frame_bounds = (min(minx, maxx), min(miny, maxy), max(minx, maxx), max(miny, maxy))

    grid = sample_elevation_grid(frame_bounds, proj, FakeElevationProvider(base_elevation=20.0), resolution_m=50.0)
    terrain_mesh = build_terrain_mesh(grid, base_thickness_m=3.0)

    building = Polygon(
        [
            (frame_bounds[0] + 50, frame_bounds[1] + 50),
            (frame_bounds[0] + 80, frame_bounds[1] + 50),
            (frame_bounds[0] + 80, frame_bounds[1] + 80),
            (frame_bounds[0] + 50, frame_bounds[1] + 80),
            (frame_bounds[0] + 50, frame_bounds[1] + 50),
        ]
    )
    base_z = building_base_z(building, grid, base_thickness_m=3.0)
    buildings_mesh = build_scene_mesh_with_base([(building, 12.0, base_z)])

    vertices, faces = merge_meshes([terrain_mesh, buildings_mesh])
    euler, watertight = euler_characteristic(vertices, faces)
    # Two disjoint closed solids (terrain slab + one building prism): 2 + 2 = 4.
    assert watertight
    assert euler == 4

    data = write_stl_binary(vertices, faces)
    triangle_count = struct.unpack("<I", data[80:84])[0]
    assert triangle_count == len(faces)
    assert len(data) == 84 + triangle_count * 50
