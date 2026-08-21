from __future__ import annotations

import numpy as np
import pytest

from app.providers.elevation import TerrariumElevationProvider, _lonlat_to_tile, decode_terrarium


def test_decode_terrarium_sea_level_reference_pixel():
    # Mapzen's documented Terrarium "0m" reference pixel is r=128, g=0, b=0:
    # 128*256 + 0 + 0/256 - 32768 == 0.
    r = np.array([128])
    g = np.array([0])
    b = np.array([0])
    assert decode_terrarium(r, g, b)[0] == pytest.approx(0.0)


def test_decode_terrarium_known_values():
    # elevation = r*256 + g + b/256 - 32768
    r, g, b = np.array([128]), np.array([10]), np.array([64])
    expected = 128 * 256 + 10 + 64 / 256 - 32768
    assert decode_terrarium(r, g, b)[0] == pytest.approx(expected)


def test_decode_terrarium_negative_elevation():
    r, g, b = np.array([127]), np.array([255]), np.array([0])
    expected = 127 * 256 + 255 + 0 - 32768
    assert expected < 0
    assert decode_terrarium(r, g, b)[0] == pytest.approx(expected)


def test_lonlat_to_tile_origin_at_zoom_zero():
    # (0, 0) sits at the centre of the single zoom-0 tile.
    tx, ty = _lonlat_to_tile(np.array([0.0]), np.array([0.0]), zoom=0)
    assert tx[0] == pytest.approx(0.5, abs=1e-6)
    assert ty[0] == pytest.approx(0.5, abs=1e-6)


class _FakeResponse:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 404:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    """Counts .get() calls per URL so tests can assert tile-fetch caching."""

    def __init__(self, tile_png_bytes: bytes):
        self.tile_png_bytes = tile_png_bytes
        self.calls: list[str] = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        if "404" in url:
            return _FakeResponse(404)
        return _FakeResponse(200, self.tile_png_bytes)


def _solid_color_png_bytes(r: int, g: int, b: int) -> bytes:
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (256, 256), (r, g, b))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_elevations_decodes_solid_tile_correctly():
    png = _solid_color_png_bytes(128, 0, 0)  # encodes to 0.0m everywhere
    session = _FakeSession(png)
    provider = TerrariumElevationProvider(zoom=10, session=session)

    lons = np.array([-46.64, -46.64, -46.6])
    lats = np.array([-23.55, -23.551, -23.55])
    result = provider.elevations(lons, lats)

    assert result.shape == lons.shape
    assert np.allclose(result, 0.0)


def test_elevations_caches_tiles_across_nearby_points():
    png = _solid_color_png_bytes(128, 0, 0)
    session = _FakeSession(png)
    provider = TerrariumElevationProvider(zoom=10, session=session)

    # Many points clustered close together should stay within one tile.
    lons = np.full(20, -46.64) + np.linspace(0, 0.0005, 20)
    lats = np.full(20, -23.55)
    provider.elevations(lons, lats)

    assert len(session.calls) == 1  # only one distinct tile fetched


def test_elevations_missing_tile_defaults_to_zero():
    session = _FakeSession(b"")

    class Missing404Session(_FakeSession):
        def get(self, url, timeout=None):
            self.calls.append(url)
            return _FakeResponse(404)

    provider = TerrariumElevationProvider(zoom=10, session=Missing404Session(b""))
    result = provider.elevations(np.array([-46.64]), np.array([-23.55]))
    assert result[0] == 0.0
