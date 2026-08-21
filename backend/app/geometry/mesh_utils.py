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
