"""Synthetic geometry fixtures — a tiny grid of roads + buildings near São Paulo.

Used so the geometry/rendering/api tests never touch the network (DESIGN.md §37).
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import LineString, Polygon

from app.providers.base import (
    AreaFeature,
    AreaFeatureSet,
    BuildingFeature,
    BuildingFeatureSet,
    GeographicFeatureSet,
    RoadFeature,
)

# A small bbox in central São Paulo.
BBOX = {"west": -46.650, "south": -23.570, "east": -46.630, "north": -23.550}


def grid_feature_set() -> GeographicFeatureSet:
    """A 3x3 grid of roads spanning the fixture bbox."""
    w, s, e, n = BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]
    features: list[RoadFeature] = []

    lats = [s + (n - s) * f for f in (0.2, 0.5, 0.8)]
    lons = [w + (e - w) * f for f in (0.2, 0.5, 0.8)]

    for i, lat in enumerate(lats):
        road_class = "primary" if i == 1 else "residential"
        features.append(
            RoadFeature(LineString([(w, lat), (e, lat)]), road_class, name=f"h{i}")
        )
    for j, lon in enumerate(lons):
        road_class = "secondary" if j == 1 else "residential"
        features.append(
            RoadFeature(LineString([(lon, s), (lon, n)]), road_class, name=f"v{j}")
        )
    return GeographicFeatureSet(features=features)


def building_feature_set() -> BuildingFeatureSet:
    """Four small buildings, one per quadrant of the road grid, distinct heights."""
    w, s, e, n = BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]
    dx, dy = (e - w), (n - s)
    fracs = (0.35, 0.65)  # midpoints between the 0.2/0.5/0.8 road lines
    heights = {(0, 0): 9.0, (0, 1): 15.0, (1, 0): 30.0, (1, 1): 6.0}
    half_w, half_h = dx * 0.08, dy * 0.08

    buildings: list[BuildingFeature] = []
    for i, fy in enumerate(fracs):
        for j, fx in enumerate(fracs):
            cx, cy = w + dx * fx, s + dy * fy
            ring = [
                (cx - half_w, cy - half_h),
                (cx + half_w, cy - half_h),
                (cx + half_w, cy + half_h),
                (cx - half_w, cy + half_h),
                (cx - half_w, cy - half_h),
            ]
            buildings.append(
                BuildingFeature(Polygon(ring), height_m=heights[(i, j)], name=f"b{i}{j}")
            )
    return BuildingFeatureSet(features=buildings)


def _small_area(frac_x: float, frac_y: float, category: str) -> AreaFeatureSet:
    """One small rectangular polygon inside BBOX, centered at the given
    fractional position — used for both water and park fixtures, kept away
    from the road grid (0.2/0.5/0.8) and building fixtures (0.35/0.65)."""
    w, s, e, n = BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]
    dx, dy = (e - w), (n - s)
    cx, cy = w + dx * frac_x, s + dy * frac_y
    half_w, half_h = dx * 0.06, dy * 0.06
    ring = [
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
        (cx - half_w, cy - half_h),
    ]
    return AreaFeatureSet(features=[AreaFeature(Polygon(ring), category=category, name=category)])


def water_feature_set() -> AreaFeatureSet:
    """One rectangular "lake" polygon inside BBOX."""
    return _small_area(0.1, 0.1, "water")


def park_feature_set() -> AreaFeatureSet:
    """One rectangular "park" polygon inside BBOX, non-overlapping with water."""
    return _small_area(0.9, 0.9, "park")


class FakeProvider:
    """A GeographicDataProvider that returns synthetic fixtures without a network."""

    def fetch_roads(self, west, south, east, north, road_classes):
        return grid_feature_set()

    def fetch_buildings(self, west, south, east, north):
        return building_feature_set()

    def fetch_water(self, west, south, east, north):
        return water_feature_set()

    def fetch_parks(self, west, south, east, north):
        return park_feature_set()


class FakeElevationProvider:
    """An ElevationProvider with a flat or east-west-sloped synthetic surface,
    no network. `slope_m_per_deg_lon` is metres of rise per degree of
    longitude, applied relative to the fixture bbox's west edge — small but
    nonzero over BBOX's ~0.02 degree span so tests can see real variation.
    """

    def __init__(self, base_elevation: float = 0.0, slope_m_per_deg_lon: float = 0.0):
        self.base_elevation = base_elevation
        self.slope_m_per_deg_lon = slope_m_per_deg_lon

    def elevations(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        lons = np.asarray(lons, dtype=np.float64)
        return self.base_elevation + self.slope_m_per_deg_lon * (lons - BBOX["west"])
