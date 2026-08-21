from __future__ import annotations

from collections import Counter

from shapely.geometry import Polygon

from app.geometry.extrude import build_scene_mesh, extrude_polygon


def _euler_characteristic(vertices, faces) -> tuple[int, bool]:
    """Return (V - E + F, is_watertight). Watertight iff every edge borders
    exactly two triangles."""
    edge_counts: Counter = Counter()
    for tri in faces:
        for a, b in zip(tri, list(tri[1:]) + [tri[0]]):
            edge_counts[frozenset((int(a), int(b)))] += 1
    watertight = all(c == 2 for c in edge_counts.values())
    euler = len(vertices) - len(edge_counts) + len(faces)
    return euler, watertight


def test_simple_rectangle_is_watertight_genus_zero():
    box = Polygon([(0, 0), (10, 0), (10, 6), (0, 6), (0, 0)])
    vertices, faces = extrude_polygon(box, height=9.0)
    assert vertices.shape[1] == 3
    assert vertices[:, 2].min() == 0.0
    assert vertices[:, 2].max() == 9.0
    euler, watertight = _euler_characteristic(vertices, faces)
    assert watertight
    assert euler == 2  # a prism is topologically a sphere


def test_building_with_courtyard_is_watertight_genus_one():
    outer = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    hole = [(3, 3), (7, 3), (7, 7), (3, 7), (3, 3)]
    poly = Polygon(outer, [hole])
    vertices, faces = extrude_polygon(poly, height=9.0)
    euler, watertight = _euler_characteristic(vertices, faces)
    assert watertight
    assert euler == 0  # a through-hole prism is topologically a torus


def test_extrude_zero_or_negative_height_still_produces_a_solid():
    box = Polygon([(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)])
    vertices, faces = extrude_polygon(box, height=0.0)
    assert vertices[:, 2].max() > 0.0  # clamped to a small positive height


def test_build_scene_mesh_offsets_indices_across_buildings():
    a = Polygon([(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)])
    b = Polygon([(20, 0), (25, 0), (25, 5), (20, 5), (20, 0)])
    vertices, faces = build_scene_mesh([(a, 9.0), (b, 15.0)])
    assert len(vertices) == 16  # 8 verts per simple box prism
    assert faces.max() < len(vertices)  # every face index is in range
    euler, watertight = _euler_characteristic(vertices, faces)
    # Two disjoint spheres: V - E + F = 2 + 2 = 4.
    assert watertight
    assert euler == 4


def test_build_scene_mesh_skips_degenerate_footprints():
    degenerate = Polygon([(0, 0), (0, 0), (0, 0)])  # zero-area, invalid
    good = Polygon([(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)])
    vertices, faces = build_scene_mesh([(degenerate, 9.0), (good, 12.0)])
    assert len(vertices) == 8
    assert len(faces) == 12
