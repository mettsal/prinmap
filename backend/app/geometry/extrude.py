"""3D mesh extrusion of building footprints (glTF/OBJ/STL export — see AGENTS.md).

Each building footprint becomes a closed, watertight triangular prism: a
triangulated roof at z=height, a triangulated floor at z=0 (reversed winding),
and wall quads connecting every ring (exterior + holes/courtyards) between the
two. Footprints are triangulated with `mapbox_earcut`, which handles holes
directly — important for buildings with internal courtyards.

Terrain relief (draping onto a DEM) is not implemented yet — buildings sit on a
flat z=0 ground plane. See AGENTS.md for the plan to add it via a DEM source.
"""

from __future__ import annotations

from typing import Iterable

import mapbox_earcut as earcut
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient


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


def build_scene_mesh(
    buildings: Iterable[tuple[Polygon, float]],
) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate every building's mesh into one (vertices, faces) pair.

    Buildings are independent watertight solids sharing one vertex/face buffer
    — valid for STL (which has no shared-solid concept) and fine for slicing/
    printing a whole block as one file.
    """
    all_verts: list[np.ndarray] = []
    all_faces: list[np.ndarray] = []
    offset = 0
    for polygon, height in buildings:
        try:
            verts, faces = extrude_polygon(polygon, height)
        except Exception:
            continue  # skip a degenerate footprint rather than fail the whole export
        if len(verts) == 0 or len(faces) == 0:
            continue
        all_verts.append(verts)
        all_faces.append(faces + offset)
        offset += len(verts)

    if not all_verts:
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.uint32)
    return np.vstack(all_verts), np.vstack(all_faces)
