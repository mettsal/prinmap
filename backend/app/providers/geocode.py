"""Nominatim geocoding proxy (DESIGN.md §9).

Proxied through the backend so we control the User-Agent and honour Nominatim's
usage policy, rather than calling it from the browser.
"""

from __future__ import annotations

import requests

from ..config import settings
from ..errors import provider_error
from ..models.schemas import GeocodeResult


def geocode(query: str, limit: int = 5) -> list[GeocodeResult]:
    try:
        resp = requests.get(
            settings.nominatim_url,
            params={"q": query, "format": "jsonv2", "limit": limit},
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout_s,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:  # pragma: no cover - network path
        raise provider_error(f"Geocoding failed: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - network path
        raise provider_error("Geocoder returned an invalid response.") from exc

    results: list[GeocodeResult] = []
    for item in payload:
        bbox = None
        raw = item.get("boundingbox")
        if raw and len(raw) == 4:
            # Nominatim order: [south, north, west, east] -> [west, south, east, north]
            south, north, west, east = (float(v) for v in raw)
            bbox = [west, south, east, north]
        results.append(
            GeocodeResult(
                display_name=item.get("display_name", query),
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                bbox=bbox,
            )
        )
    return results
