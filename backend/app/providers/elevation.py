"""Elevation (DEM) data provider abstraction — mirrors providers/base.py's
GeographicDataProvider pattern so the elevation source is swappable (Terrarium
today; a higher-resolution DEM such as Copernicus GLO-30 later) without
touching geometry/terrain.py or service.py.
"""

from __future__ import annotations

import math
from io import BytesIO
from typing import Protocol

import numpy as np
import requests
from PIL import Image

from ..config import settings
from ..errors import provider_error


class ElevationProvider(Protocol):
    def elevations(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        """Batch WGS84 (lon, lat) arrays -> elevation in metres (same shape).

        Batch-oriented (not one-point-at-a-time) so a tiled raster source can
        fetch/cache/decode each covering tile once per request regardless of
        how many sample points fall inside it.
        """
        ...


# --------------------------------------------------------------------------- #
# Web Mercator XYZ tile math
# --------------------------------------------------------------------------- #
def _lonlat_to_tile(lon: np.ndarray, lat: np.ndarray, zoom: int) -> tuple[np.ndarray, np.ndarray]:
    """WGS84 (lon, lat) -> fractional (tile_x, tile_y) at a given zoom."""
    lat_rad = np.radians(lat)
    n = 2.0**zoom
    tile_x = (lon + 180.0) / 360.0 * n
    tile_y = (1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n
    return tile_x, tile_y


def decode_terrarium(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Terrarium RGB encoding -> elevation in metres (pure, unit-testable).

    elevation = (r * 256 + g + b / 256) - 32768
    """
    return (r.astype(np.float64) * 256.0 + g.astype(np.float64) + b.astype(np.float64) / 256.0) - 32768.0


class TerrariumElevationProvider:
    """AWS Terrarium raster-dem tiles — the same free, no-API-key source used
    by the browser's 3D preview (frontend/src/map/mapStyles.ts::TERRAIN_TILE_URL).
    Keep the URL/encoding in sync between the two — see AGENTS.md.
    """

    TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
    TILE_SIZE = 256

    def __init__(self, zoom: int = 14, session: requests.Session | None = None) -> None:
        self.zoom = zoom
        self.session = session or requests.Session()
        self._tile_cache: dict[tuple[int, int, int], np.ndarray | None] = {}

    def _fetch_tile(self, z: int, x: int, y: int) -> np.ndarray | None:
        """Return a (256, 256, 3) uint8 array, or None if the tile is missing
        (404 — e.g. ocean/coverage gaps). Samples in a missing tile default to
        elevation 0.0 (see `elevations`); other request failures raise.
        """
        key = (z, x, y)
        if key in self._tile_cache:
            return self._tile_cache[key]
        url = self.TILE_URL.format(z=z, x=x, y=y)
        try:
            resp = self.session.get(url, timeout=settings.request_timeout_s)
            if resp.status_code == 404:
                self._tile_cache[key] = None
                return None
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            arr = np.asarray(img, dtype=np.uint8)  # (H, W, 3)
        except requests.RequestException as exc:  # pragma: no cover - network path
            raise provider_error(f"Failed to fetch elevation tile: {exc}") from exc
        self._tile_cache[key] = arr
        return arr

    def elevations(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        lons = np.asarray(lons, dtype=np.float64)
        lats = np.asarray(lats, dtype=np.float64)
        tx, ty = _lonlat_to_tile(lons, lats, self.zoom)

        tile_x = np.floor(tx).astype(np.int64)
        tile_y = np.floor(ty).astype(np.int64)
        px = np.clip(((tx - tile_x) * self.TILE_SIZE).astype(np.int64), 0, self.TILE_SIZE - 1)
        py = np.clip(((ty - tile_y) * self.TILE_SIZE).astype(np.int64), 0, self.TILE_SIZE - 1)

        out = np.zeros(lons.shape, dtype=np.float64)
        for tile_key in {(int(x), int(y)) for x, y in zip(tile_x, tile_y)}:
            x, y = tile_key
            mask = (tile_x == x) & (tile_y == y)
            tile = self._fetch_tile(self.zoom, x, y)
            if tile is None:
                out[mask] = 0.0  # missing tile (coverage gap) -> sea-level default
                continue
            r = tile[py[mask], px[mask], 0]
            g = tile[py[mask], px[mask], 1]
            b = tile[py[mask], px[mask], 2]
            out[mask] = decode_terrarium(r, g, b)
        return out
