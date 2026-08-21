"""OpenStreetMap road provider backed by the Overpass API (DESIGN.md §14).

Uses `out geom;` so each way carries its own coordinate list — no separate node
resolution step is required, which keeps the MVP simple.
"""

from __future__ import annotations

from typing import Sequence

import re

import requests
from shapely.geometry import LineString, Polygon

from ..config import settings
from ..errors import provider_error
from .base import BuildingFeature, BuildingFeatureSet, GeographicFeatureSet, RoadFeature

# Fallback height when OSM has neither `height` nor `building:levels` (DESIGN.md
# doesn't specify a value; ~3 storeys is a reasonable dense-urban default).
DEFAULT_BUILDING_HEIGHT_M = 9.0
METERS_PER_LEVEL = 3.0

# Default road classes for the MVP. Footways/tracks are intentionally excluded
# unless explicitly requested (DESIGN.md §14).
DEFAULT_ROAD_CLASSES = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "pedestrian",
    "service",
)


def _build_road_query(
    west: float, south: float, east: float, north: float, road_classes: Sequence[str]
) -> str:
    # Overpass bbox order is (south, west, north, east).
    regex = "|".join(road_classes)
    return (
        "[out:json][timeout:60];"
        f'(way["highway"~"^({regex})$"]({south},{west},{north},{east}););'
        "out geom;"
    )


def _build_building_query(west: float, south: float, east: float, north: float) -> str:
    # Ways only for the MVP; multipolygon relations (buildings with courtyards
    # modelled as an outer+inner relation) are intentionally out of scope.
    return (
        "[out:json][timeout:60];"
        f'(way["building"]({south},{west},{north},{east}););'
        "out geom;"
    )


class OSMProvider:
    """Fetches road centrelines and building footprints from Overpass."""

    def __init__(self, endpoint: str | None = None, session: requests.Session | None = None) -> None:
        self.endpoint = endpoint or settings.overpass_url
        self.session = session or requests.Session()

    def _query_overpass(self, query: str) -> dict:
        try:
            resp = self.session.post(
                self.endpoint,
                data={"data": query},
                headers={"User-Agent": settings.user_agent},
                timeout=settings.request_timeout_s,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout as exc:  # pragma: no cover - network path
            raise provider_error("The OSM query timed out. Try a smaller region.") from exc
        except requests.RequestException as exc:  # pragma: no cover - network path
            raise provider_error(f"Failed to query OpenStreetMap: {exc}") from exc
        except ValueError as exc:  # pragma: no cover - network path
            raise provider_error("OpenStreetMap returned an invalid response.") from exc

    def fetch_roads(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        road_classes: Sequence[str] = DEFAULT_ROAD_CLASSES,
    ) -> GeographicFeatureSet:
        query = _build_road_query(west, south, east, north, road_classes)
        payload = self._query_overpass(query)
        return _parse_roads(payload)

    def fetch_buildings(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> BuildingFeatureSet:
        query = _build_building_query(west, south, east, north)
        payload = self._query_overpass(query)
        return _parse_buildings(payload)


def _parse_roads(payload: dict) -> GeographicFeatureSet:
    features: list[RoadFeature] = []
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        geometry = element.get("geometry")
        if not geometry or len(geometry) < 2:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in geometry]
        tags = element.get("tags", {})
        features.append(
            RoadFeature(
                geometry=LineString(coords),
                road_class=tags.get("highway", "unknown"),
                name=tags.get("name"),
            )
        )
    return GeographicFeatureSet(features=features)


_HEIGHT_RE = re.compile(r"[-+]?\d*\.?\d+")


def parse_building_height(tags: dict) -> float:
    """Derive a building height in metres from OSM tags.

    Priority: explicit `height` tag (accepts "12", "12 m", "12m") > `levels` *
    metres-per-level > a flat dense-urban default. Pure function — no network —
    so it's directly unit-testable.
    """
    height = tags.get("height")
    if height:
        match = _HEIGHT_RE.search(str(height))
        if match:
            try:
                value = float(match.group())
                if value > 0:
                    return value
            except ValueError:
                pass

    levels = tags.get("building:levels")
    if levels:
        match = _HEIGHT_RE.search(str(levels))
        if match:
            try:
                value = float(match.group())
                if value > 0:
                    return value * METERS_PER_LEVEL
            except ValueError:
                pass

    return DEFAULT_BUILDING_HEIGHT_M


def _parse_buildings(payload: dict) -> BuildingFeatureSet:
    features: list[BuildingFeature] = []
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        geometry = element.get("geometry")
        if not geometry or len(geometry) < 4:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in geometry]
        if coords[0] != coords[-1]:
            continue  # not a closed ring -> not a usable footprint
        tags = element.get("tags", {})
        try:
            polygon = Polygon(coords)
        except Exception:  # pragma: no cover - malformed OSM geometry
            continue
        if not polygon.is_valid or polygon.is_empty:
            continue
        features.append(
            BuildingFeature(
                geometry=polygon,
                height_m=parse_building_height(tags),
                name=tags.get("name"),
            )
        )
    return BuildingFeatureSet(features=features)
