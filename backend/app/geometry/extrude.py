"""3D mesh extrusion of building footprints (STL export — see AGENTS.md).

Each building footprint becomes a closed, watertight triangular prism: a
triangulated roof at z=base_z+height, a triangulated floor at z=base_z
(reversed winding), and wall quads connecting every ring (exterior +
holes/courtyards) between the two. Footprints are triangulated with
`mapbox_earcut`, which handles holes directly — important for buildings with
internal courtyards.

`base_z` lets a building be seated on terrain relief (see geometry/terrain.py)
instead of a flat z=0 ground plane.
"""

from __future__ import annotations

from typing import Iterable

import mapbox_earcut as earcut
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from .mesh_utils import MeshPart, merge_meshes


def _triangulate_footprint(polygon: Polygon) -> tuple[np.ndarray, np.ndarray]:
    """Return (points Nx2, triangles Mx3) for the polygon's rings via earcut."""
    rings = [list(polygon.exterior.coords)[:-1]]
    rings += [list(interior.coords)[:-1] for interior in polygon.interiors]

    points: list[tuple[float, float]] = []
    ring_ends: list[int] = []
    for ring in rings:
        points.extend(ring)
        ring_ends.append(len(points))

    verts = np.array(points, dtype=np.float64).reshape(-1, 2)
    ring_ends_arr = np.array(ring_ends, dtype=np.uint32)
    indices = earcut.triangulate_float64(verts, ring_ends_arr)
    return verts, indices.reshape(-1, 3)


def extrude_polygon(
    polygon: Polygon, height: float, base_z: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Build a watertight triangle mesh for one building.

    Returns (vertices Nx3 float64, faces Mx3 uint32), locally indexed from 0 —
    callers must offset indices when merging multiple buildings into one mesh.
    """
    if height <= 0:
        height = 0.1
    polygon = orient(polygon, sign=1.0)  # exterior CCW, holes CW

    verts2d, roof_tris = _triangulate_footprint(polygon)
    n = len(verts2d)
    if n == 0 or len(roof_tris) == 0:
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.uint32)

    floor = np.hstack([verts2d, np.full((n, 1), base_z)])
    roof = np.hstack([verts2d, np.full((n, 1), base_z + height)])
    vertices = np.vstack([floor, roof])  # floor: 0..n-1, roof: n..2n-1

    faces: list[tuple[int, int, int]] = []
    for a, b, c in roof_tris:
        faces.append((a + n, b + n, c + n))  # roof, facing +z
    for a, b, c in roof_tris:
        faces.append((a, c, b))  # floor, reversed winding -> facing -z

    rings = [list(polygon.exterior.coords)[:-1]] + [
        list(i.coords)[:-1] for i in polygon.interiors
    ]
    start = 0
    for ring in rings:
        m = len(ring)
        for i in range(m):
            a = start + i
            b = start + (i + 1) % m
            ra, rb = a + n, b + n
            faces.append((a, b, rb))
            faces.append((a, rb, ra))
        start += m

    return vertices, np.array(faces, dtype=np.uint32)


def build_scene_mesh(buildings: Iterable[tuple[Polygon, float]]) -> MeshPart:
    """Concatenate every building's mesh into one (vertices, faces) pair, each
    seated on a flat z=0 ground plane. See `build_scene_mesh_with_base` for
    buildings seated on terrain relief.
    """
    return build_scene_mesh_with_base((polygon, height, 0.0) for polygon, height in buildings)


def build_scene_mesh_with_base(
    buildings: Iterable[tuple[Polygon, float, float]],
) -> MeshPart:
    """Concatenate every building's mesh into one (vertices, faces) pair, each
    seated at its own `base_z` (e.g. terrain elevation sampled under its
    footprint — see geometry/terrain.py::building_base_z).

    Buildings are independent watertight solids sharing one vertex/face buffer
    — valid for STL (which has no shared-solid concept) and fine for slicing/
    printing a whole block as one file.
    """
    parts: list[MeshPart] = []
    for polygon, height, base_z in buildings:
        try:
            parts.append(extrude_polygon(polygon, height, base_z=base_z))
        except Exception:
            continue  # skip a degenerate footprint rather than fail the whole export
    return merge_meshes(parts)
