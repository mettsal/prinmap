"""Synthetic geometry fixtures — a tiny grid of roads near São Paulo.

Used so the geometry/rendering/api tests never touch the network (DESIGN.md §37).
"""

from __future__ import annotations

from shapely.geometry import LineString

from app.providers.base import GeographicFeatureSet, RoadFeature

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


class FakeProvider:
    """A GeographicDataProvider that returns the synthetic grid without a network."""

    def fetch_roads(self, west, south, east, north, road_classes):
        return grid_feature_set()
