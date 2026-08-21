"""Geographic data provider abstraction (DESIGN.md §13).

The rest of the application depends only on these types, never on the concrete
acquisition mechanism (Overpass today; PostGIS / local extracts later).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Sequence

from shapely.geometry.base import BaseGeometry


@dataclass
class RoadFeature:
    """A single road centreline in WGS84 (lon/lat) plus its OSM class."""

    geometry: BaseGeometry  # LineString in EPSG:4326
    road_class: str
    name: Optional[str] = None


@dataclass
class GeographicFeatureSet:
    features: List[RoadFeature] = field(default_factory=list)
    crs: str = "EPSG:4326"

    def __len__(self) -> int:  # convenience for emptiness checks
        return len(self.features)


class GeographicDataProvider(Protocol):
    def fetch_roads(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        road_classes: Sequence[str],
    ) -> GeographicFeatureSet:
        ...
