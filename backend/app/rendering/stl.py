"""Binary STL writer for the 3D building-mesh export.

Hand-rolled instead of pulling in trimesh/numpy-stl: binary STL is a simple,
fixed-size record format (80-byte header, uint32 triangle count, then per
triangle a 12-byte normal + three 12-byte vertices + a 2-byte attribute count),
and we already depend on numpy for the extrusion math.
"""

from __future__ import annotations

import struct

import numpy as np


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths == 0] = 1.0
    return normals / lengths[:, None]


def write_stl_binary(vertices: np.ndarray, faces: np.ndarray, name: bytes = b"prinmap") -> bytes:
    """Serialize an indexed triangle mesh (Nx3 vertices, Mx3 face indices)."""
    triangle_count = len(faces)
    body = bytearray()
    body += name[:80].ljust(80, b"\0")
    body += struct.pack("<I", triangle_count)

    if triangle_count:
        normals = _face_normals(vertices, faces)
        tri_verts = vertices[faces]  # (M, 3, 3)
        for normal, tri in zip(normals, tri_verts):
            body += struct.pack(
                "<12fH",
                *normal,
                *tri[0],
                *tri[1],
                *tri[2],
                0,
            )
    return bytes(body)
