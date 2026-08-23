"""Shared helpers for merging independent (vertices, faces) mesh parts.

Used by both the buildings-only extrusion path and the terrain+buildings path
so the index-offsetting logic isn't duplicated.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

MeshPart = tuple[np.ndarray, np.ndarray]  # (vertices Nx3, faces Mx3 uint32)


def merge_meshes(parts: Iterable[MeshPart]) -> MeshPart:
    """Concatenate independent watertight solids into one (vertices, faces)
    buffer, offsetting face indices per part. Empty/degenerate parts are
    silently skipped.
    """
    all_verts: list[np.ndarray] = []
    all_faces: list[np.ndarray] = []
    offset = 0
    for verts, faces in parts:
        if len(verts) == 0 or len(faces) == 0:
            continue
        all_verts.append(verts)
        all_faces.append(faces + offset)
        offset += len(verts)

    if not all_verts:
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.uint32)
    return np.vstack(all_verts), np.vstack(all_faces)


def print_scale_mm_per_m(frame_bounds: tuple[float, float, float, float], print_size_mm: float) -> float:
    """Millimetres-of-printed-model per metre-of-world, so that the model's
    longest horizontal edge ends up exactly `print_size_mm` long.

    This is the single conversion tying the whole STL to a physical print size:
    every treatment depth authored in printed-mm is divided by this to get its
    world-metre magnitude, and the finished mesh is multiplied by it.
    """
    minx, miny, maxx, maxy = frame_bounds
    longest_edge_m = max(maxx - minx, maxy - miny, 1e-6)
    return print_size_mm / longest_edge_m


def scale_mesh_to_print(
    vertices: np.ndarray, mm_per_m: float, origin_x: float, origin_y: float
) -> np.ndarray:
    """Recentre the mesh so (origin_x, origin_y) -> (0, 0) in X/Y, then scale
    all axes uniformly by `mm_per_m` to emit a print-ready model in millimetres.

    X/Y are recentred first because the source coordinates are absolute UTM
    eastings/northings (hundreds of thousands / millions of metres); scaling
    those directly would place the model far from the origin and waste float
    precision. Z is already normalised to relief-from-zero (see
    sample_elevation_grid), so it only needs scaling, not recentring.
    """
    if len(vertices) == 0:
        return vertices
    out = vertices.astype(np.float64, copy=True)
    out[:, 0] -= origin_x
    out[:, 1] -= origin_y
    out *= mm_per_m
    return out
