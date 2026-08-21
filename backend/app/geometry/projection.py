"""Coordinate reference system helpers (DESIGN.md §15).

Geometry operations (buffering especially) must happen in a metric CRS, never in
degrees. We pick a UTM zone dynamically from the selection centre.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyproj import CRS, Transformer


def utm_epsg_for(lon: float, lat: float) -> int:
    """Return the EPSG code of the UTM zone containing (lon, lat)."""
    zone = int((lon + 180.0) // 6.0) + 1
    zone = max(1, min(60, zone))
    return (32600 if lat >= 0 else 32700) + zone


@dataclass
class Projection:
    crs: CRS
    epsg: int
    _fwd: Transformer
    _inv: Transformer

    def forward(self, lon: float, lat: float) -> tuple[float, float]:
        """WGS84 (lon, lat) -> projected (x, y) in metres."""
        return self._fwd.transform(lon, lat)

    def inverse(self, x: float, y: float) -> tuple[float, float]:
        """Projected (x, y) -> WGS84 (lon, lat)."""
        return self._inv.transform(x, y)

    @property
    def fwd_xy(self):
        """A `transform`-compatible callable for shapely.ops.transform."""
        return self._fwd.transform


def projection_for(center_lon: float, center_lat: float) -> Projection:
    epsg = utm_epsg_for(center_lon, center_lat)
    crs = CRS.from_epsg(epsg)
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    return Projection(crs=crs, epsg=epsg, _fwd=fwd, _inv=inv)
