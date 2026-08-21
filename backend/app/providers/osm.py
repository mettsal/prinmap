"""OpenStreetMap road provider backed by the Overpass API (DESIGN.md §14).

Uses `out geom;` so each way carries its own coordinate list — no separate node
resolution step is required, which keeps the MVP simple.
"""

from __future__ import annotations

from typing import Sequence

import requests
from shapely.geometry import LineString

from ..config import settings
from ..errors import provider_error
from .base import GeographicFeatureSet, RoadFeature

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


def _build_query(
    west: float, south: float, east: float, north: float, road_classes: Sequence[str]
) -> str:
    # Overpass bbox order is (south, west, north, east).
    regex = "|".join(road_classes)
    return (
        "[out:json][timeout:60];"
        f'(way["highway"~"^({regex})$"]({south},{west},{north},{east}););'
        "out geom;"
    )


class OSMProvider:
    """Fetches road centrelines intersecting a bounding box from Overpass."""

    def __init__(self, endpoint: str | None = None, session: requests.Session | None = None) -> None:
        self.endpoint = endpoint or settings.overpass_url
        self.session = session or requests.Session()

    def fetch_roads(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        road_classes: Sequence[str] = DEFAULT_ROAD_CLASSES,
    ) -> GeographicFeatureSet:
        query = _build_query(west, south, east, north, road_classes)
        try:
            resp = self.session.post(
                self.endpoint,
                data={"data": query},
                headers={"User-Agent": settings.user_agent},
                timeout=settings.request_timeout_s,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.Timeout as exc:  # pragma: no cover - network path
            raise provider_error("The OSM query timed out. Try a smaller region.") from exc
        except requests.RequestException as exc:  # pragma: no cover - network path
            raise provider_error(f"Failed to query OpenStreetMap: {exc}") from exc
        except ValueError as exc:  # pragma: no cover - network path
            raise provider_error("OpenStreetMap returned an invalid response.") from exc

        return _parse_overpass(payload)


def _parse_overpass(payload: dict) -> GeographicFeatureSet:
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
