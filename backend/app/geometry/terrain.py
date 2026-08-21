"""Terrain relief: a regular-grid elevation sampler over the projected UTM
frame, and a watertight terrain solid (draped roof + flat floor + skirt
walls) — the grid analogue of extrude.py's roof/floor/wall pattern, so
buildings can be seated on real ground elevation instead of a flat z=0 plane.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon

from ..providers.elevation import ElevationProvider
from .mesh_utils import MeshPart
from .projection import Projection

# Regardless of the requested resolution_m, the sampling grid never exceeds
# this many points per axis — bounds both elevation-provider query volume and
# terrain-mesh triangle count for a max-area (25 km²) selection.
MAX_GRID_POINTS_PER_AXIS = 300

# How far a building's seated floor is sunk below its lowest sampled ground
# corner, to guarantee fusion with the terrain surface (no visible gap).
BUILDING_SINK_M = 0.1


@dataclass
class ElevationGrid:
    xs: np.ndarray  # (nx,) projected x coordinates, metres, ascending
    ys: np.ndarray  # (ny,) projected y coordinates, metres, ascending
    elevations: np.ndarray  # (ny, nx) metres — exaggeration already applied

    def sample_bilinear(self, x: float, y: float) -> float:
        """Sample elevation at an arbitrary projected (x, y), clamped to the
        grid bounds, via bilinear interpolation."""
        xs, ys, z = self.xs, self.ys, self.elevations
        x = min(max(x, xs[0]), xs[-1])
        y = min(max(y, ys[0]), ys[-1])

        i1 = int(np.clip(np.searchsorted(xs, x), 1, len(xs) - 1))
        i0 = i1 - 1
        j1 = int(np.clip(np.searchsorted(ys, y), 1, len(ys) - 1))
        j0 = j1 - 1

        tx = (x - xs[i0]) / (xs[i1] - xs[i0]) if xs[i1] != xs[i0] else 0.0
        ty = (y - ys[j0]) / (ys[j1] - ys[j0]) if ys[j1] != ys[j0] else 0.0

        z00, z10 = z[j0, i0], z[j0, i1]
        z01, z11 = z[j1, i0], z[j1, i1]
        za = z00 * (1 - tx) + z10 * tx
        zb = z01 * (1 - tx) + z11 * tx
        return float(za * (1 - ty) + zb * ty)


def sample_elevation_grid(
    frame_bounds: tuple[float, float, float, float],
    projection: Projection,
    elevation_provider: ElevationProvider,
    resolution_m: float,
    exaggeration: float = 1.0,
) -> ElevationGrid:
    """Build a regular grid of elevation samples over the projected frame.

    Grid nodes are reprojected to WGS84 and batch-queried against
    `elevation_provider`. Silently coarsens (fewer points, larger effective
    spacing) rather than raising if `resolution_m` would exceed
    `MAX_GRID_POINTS_PER_AXIS` on a large selection.

    Elevations are normalized so the selection's lowest sampled point sits at
    z=0 *before* exaggeration is applied — real elevation-above-sea-level is
    an arbitrary, usually-large offset that's irrelevant to a printed model;
    only local relief (deviation from the selection's own lowest point)
    should be visible, and only that relief is stretched by `exaggeration`.
    """
    minx, miny, maxx, maxy = frame_bounds
    width = max(maxx - minx, 1e-6)
    height = max(maxy - miny, 1e-6)

    nx = int(np.clip(np.ceil(width / resolution_m) + 1, 2, MAX_GRID_POINTS_PER_AXIS))
    ny = int(np.clip(np.ceil(height / resolution_m) + 1, 2, MAX_GRID_POINTS_PER_AXIS))

    xs = np.linspace(minx, maxx, nx)
    ys = np.linspace(miny, maxy, ny)
    xx, yy = np.meshgrid(xs, ys)  # each (ny, nx)

    lons, lats = projection.inverse(xx.ravel(), yy.ravel())
    lons = np.asarray(lons, dtype=np.float64)
    lats = np.asarray(lats, dtype=np.float64)

    raw = np.asarray(elevation_provider.elevations(lons, lats), dtype=np.float64).reshape(ny, nx)
    relief = raw - raw.min()
    elevations = relief * exaggeration

    return ElevationGrid(xs=xs, ys=ys, elevations=elevations)


def terrain_floor_z(grid: ElevationGrid, base_thickness_m: float) -> float:
    """The flat z of the terrain solid's bottom face (single source of truth,
    shared by build_terrain_mesh and building_base_z's clamp)."""
    return float(np.min(grid.elevations)) - base_thickness_m


def build_terrain_mesh(grid: ElevationGrid, base_thickness_m: float) -> MeshPart:
    """Build ONE watertight solid: a draped terrain "roof" (heightfield
    surface, two triangles per grid cell), a flat "floor" at
    `terrain_floor_z`, reversed winding, and a perimeter "skirt" of wall
    quads connecting roof-edge to floor-edge — the grid-shaped analogue of
    extrude_polygon's roof/floor/wall pattern. Euler characteristic is 2 (a
    single genus-0 solid).
    """
    ny, nx = grid.elevations.shape
    xx, yy = np.meshgrid(grid.xs, grid.ys)  # (ny, nx)

    def idx(j: int, i: int) -> int:
        return j * nx + i

    n = nx * ny
    floor_z = terrain_floor_z(grid, base_thickness_m)

    roof_verts = np.stack([xx.ravel(), yy.ravel(), grid.elevations.ravel()], axis=1)
    floor_verts = np.stack([xx.ravel(), yy.ravel(), np.full(n, floor_z)], axis=1)
    vertices = np.vstack([floor_verts, roof_verts])  # floor: 0..n-1, roof: n..2n-1

    faces: list[tuple[int, int, int]] = []

    # Roof + floor: two triangles per grid cell. Corner order a,b,c,d is CCW
    # in the XY plane (X right, Y up) so the roof faces +z; floor uses the
    # reversed winding, mirroring extrude_polygon's roof/floor pair.
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, c, d = idx(j, i), idx(j, i + 1), idx(j + 1, i), idx(j + 1, i + 1)
            faces.append((a + n, b + n, d + n))
            faces.append((a + n, d + n, c + n))
            faces.append((a, d, b))
            faces.append((a, c, d))

    # Skirt: walk the grid's outer boundary counter-clockwise (viewed from
    # above) — bottom row left->right, right column bottom->top, top row
    # right->left, left column top->bottom — matching shapely's CCW-exterior
    # convention, so the wall-pair formula below faces outward (same formula
    # extrude_polygon uses for its ring walls).
    perimeter: list[int] = []
    perimeter += [idx(0, i) for i in range(nx)]
    perimeter += [idx(j, nx - 1) for j in range(1, ny)]
    perimeter += [idx(ny - 1, i) for i in range(nx - 2, -1, -1)]
    perimeter += [idx(j, 0) for j in range(ny - 2, 0, -1)]

    m = len(perimeter)
    for k in range(m):
        a = perimeter[k]
        b = perimeter[(k + 1) % m]
        ra, rb = a + n, b + n
        faces.append((a, b, rb))
        faces.append((a, rb, ra))

    return vertices, np.array(faces, dtype=np.uint32)


def building_base_z(footprint: Polygon, grid: ElevationGrid, base_thickness_m: float) -> float:
    """Ground elevation to seat a building's flat floor on, so it never
    floats above sloped terrain: the minimum sampled elevation over the
    footprint's exterior-ring vertices, sunk by BUILDING_SINK_M, clamped to
    never sink below the terrain solid's own flat bottom.
    """
    coords = list(footprint.exterior.coords)
    ground = min(grid.sample_bilinear(x, y) for x, y in coords)
    base_z = ground - BUILDING_SINK_M
    return max(base_z, terrain_floor_z(grid, base_thickness_m))
