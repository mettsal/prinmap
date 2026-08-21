from __future__ import annotations

import struct

from shapely.geometry import Polygon

from app.geometry.extrude import extrude_polygon
from app.rendering.stl import write_stl_binary


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
