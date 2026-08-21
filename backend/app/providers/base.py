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


@dataclass
class BuildingFeature:
    """A single building footprint in WGS84 (lon/lat) plus its derived height."""

    geometry: BaseGeometry  # Polygon in EPSG:4326
    height_m: float
    name: Optional[str] = None


@dataclass
class BuildingFeatureSet:
    features: List[BuildingFeature] = field(default_factory=list)
    crs: str = "EPSG:4326"

    def __len__(self) -> int:
        return len(self.features)


@dataclass
class AreaFeature:
    """A single water/park/wood polygon in WGS84 (lon/lat) plus its category.

    Water and parks are structurally identical (a polygon + category, no
    height) so they share this one type rather than duplicating
    BuildingFeature's shape for no behavioral gain.
    """

    geometry: BaseGeometry  # Polygon in EPSG:4326
    category: str  # "water" | "park"
    name: Optional[str] = None


@dataclass
class AreaFeatureSet:
    features: List[AreaFeature] = field(default_factory=list)
    crs: str = "EPSG:4326"

    def __len__(self) -> int:
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

    def fetch_buildings(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> BuildingFeatureSet:
        ...

    def fetch_water(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> AreaFeatureSet:
        ...

    def fetch_parks(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> AreaFeatureSet:
        ...
