"""Shared watertightness test helper: Euler characteristic (V - E + F) of a
triangle mesh. A closed manifold solid has V - E + F == 2 - 2*genus, and is
watertight iff every edge borders exactly two triangles.
"""

from __future__ import annotations

from collections import Counter


def euler_characteristic(vertices, faces) -> tuple[int, bool]:
    """Return (V - E + F, is_watertight)."""
    edge_counts: Counter = Counter()
    for tri in faces:
        for a, b in zip(tri, list(tri[1:]) + [tri[0]]):
            edge_counts[frozenset((int(a), int(b)))] += 1
    watertight = all(c == 2 for c in edge_counts.values())
    euler = len(vertices) - len(edge_counts) + len(faces)
    return euler, watertight
