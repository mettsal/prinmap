from __future__ import annotations

import struct

import pytest

import app.main as main_module
from app.main import app
from app.models.schemas import GenerateMeshRequest
from app.service import generate_fabric, generate_mesh
from fastapi.testclient import TestClient

from ..fixtures import BBOX, FakeElevationProvider, FakeProvider

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def _payload(**overrides):
    body = {
        "selection": {"type": "bbox", **BBOX},
        "style": {"preset": "dark-minimal"},
        "parameters": {"detail": 0.75, "road_width": 2.0},
    }
    body.update(overrides)
    return body


def test_generate_with_mocked_provider(monkeypatch):
    # Patch OSMProvider construction inside the service so no network is hit.
    monkeypatch.setattr(main_module, "generate_fabric", lambda req: generate_fabric(req, provider=FakeProvider()))
    resp = client.post("/api/v1/generate", json=_payload())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["format"] == "svg"
    assert data["status"] == "completed"
    assert data["svg"].startswith("<svg")
    assert data["metadata"]["style"] == "dark-minimal"


def test_generate_rejects_degenerate_selection(monkeypatch):
    monkeypatch.setattr(main_module, "generate_fabric", lambda req: generate_fabric(req, provider=FakeProvider()))
    bad = _payload(selection={"type": "bbox", "west": -46.6, "south": -23.5, "east": -46.7, "north": -23.6})
    resp = client.post("/api/v1/generate", json=bad)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_SELECTION"


def test_generate_rejects_oversized_selection(monkeypatch):
    monkeypatch.setattr(main_module, "generate_fabric", lambda req: generate_fabric(req, provider=FakeProvider()))
    huge = _payload(selection={"type": "bbox", "west": -47.5, "south": -24.5, "east": -46.0, "north": -23.0})
    resp = client.post("/api/v1/generate", json=huge)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SELECTION_TOO_LARGE"


def test_generate_with_buildings_and_blocks_layers(monkeypatch):
    monkeypatch.setattr(main_module, "generate_fabric", lambda req: generate_fabric(req, provider=FakeProvider()))
    payload = _payload(fabric={"features": ["roads", "buildings", "blocks"]})
    resp = client.post("/api/v1/generate", json=payload)
    assert resp.status_code == 200, resp.text
    svg = resp.json()["svg"]
    assert '<g id="blocks">' in svg
    assert '<g id="buildings">' in svg
    assert '<g id="roads">' in svg


def _mesh_stl_triangle_count(body: bytes) -> int:
    return struct.unpack("<I", body[80:84])[0]


def test_generate_mesh_with_terrain_returns_binary_stl(monkeypatch):
    # terrain.include defaults to True — must inject a FakeElevationProvider
    # so this never touches the real network.
    monkeypatch.setattr(
        main_module,
        "generate_mesh",
        lambda req: generate_mesh(req, provider=FakeProvider(), elevation_provider=FakeElevationProvider(base_elevation=15.0)),
    )
    resp = client.post("/api/v1/generate/mesh", json={"selection": {"type": "bbox", **BBOX}})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "model/stl"
    body = resp.content
    assert len(body) > 84
    triangle_count = _mesh_stl_triangle_count(body)
    assert triangle_count > 0
    assert len(body) == 84 + triangle_count * 50


def test_generate_mesh_without_terrain_still_works(monkeypatch):
    # terrain.include=False must never call the elevation provider — passing
    # None here proves it, since a None.elevations() call would crash.
    monkeypatch.setattr(
        main_module,
        "generate_mesh",
        lambda req: generate_mesh(req, provider=FakeProvider(), elevation_provider=None),
    )
    resp = client.post(
        "/api/v1/generate/mesh",
        json={"selection": {"type": "bbox", **BBOX}, "terrain": {"include": False}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.content
    assert _mesh_stl_triangle_count(body) > 0


def test_generate_mesh_terrain_adds_triangles_over_flat_baseline(monkeypatch):
    def _generate(req):
        return generate_mesh(req, provider=FakeProvider(), elevation_provider=FakeElevationProvider(base_elevation=15.0))

    monkeypatch.setattr(main_module, "generate_mesh", _generate)

    flat_resp = client.post(
        "/api/v1/generate/mesh",
        json={"selection": {"type": "bbox", **BBOX}, "terrain": {"include": False}},
    )
    terrain_resp = client.post(
        "/api/v1/generate/mesh",
        json={"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True}},
    )
    assert _mesh_stl_triangle_count(terrain_resp.content) > _mesh_stl_triangle_count(flat_resp.content)


def test_generate_mesh_textured_street_style(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "generate_mesh",
        lambda req: generate_mesh(req, provider=FakeProvider(), elevation_provider=FakeElevationProvider(base_elevation=15.0)),
    )
    resp = client.post(
        "/api/v1/generate/mesh",
        json={"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True, "street_style": "textured"}},
    )
    assert resp.status_code == 200, resp.text
    assert _mesh_stl_triangle_count(resp.content) > 0


def test_generate_mesh_street_style_changes_geometry_not_triangle_count(monkeypatch):
    def _generate(req):
        return generate_mesh(req, provider=FakeProvider(), elevation_provider=FakeElevationProvider(base_elevation=15.0))

    monkeypatch.setattr(main_module, "generate_mesh", _generate)

    recessed = client.post(
        "/api/v1/generate/mesh",
        json={"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True, "street_style": "recessed"}},
    )
    textured = client.post(
        "/api/v1/generate/mesh",
        json={"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True, "street_style": "textured"}},
    )
    # apply_surface_treatments only mutates Z values, never topology, so both
    # modes must produce the exact same triangle count for the same grid.
    assert _mesh_stl_triangle_count(recessed.content) == _mesh_stl_triangle_count(textured.content)
    assert recessed.content != textured.content  # but the actual geometry (Z values) differs


def _stl_xy_extent(body: bytes) -> tuple[float, float]:
    """Longest X and Y span of all triangle vertices in a binary STL."""
    count = _mesh_stl_triangle_count(body)
    xs: list[float] = []
    ys: list[float] = []
    for t in range(count):
        base = 84 + t * 50 + 12  # skip header + normal
        floats = struct.unpack_from("<9f", body, base)
        xs += [floats[0], floats[3], floats[6]]
        ys += [floats[1], floats[4], floats[7]]
    return max(xs) - min(xs), max(ys) - min(ys)


def test_mesh_is_exported_at_requested_print_size():
    # The model's longest horizontal edge should equal print_size_mm.
    stl, info = generate_mesh(
        GenerateMeshRequest.model_validate(
            {"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True, "print_size_mm": 120.0}}
        ),
        provider=FakeProvider(),
        elevation_provider=FakeElevationProvider(base_elevation=15.0),
    )
    dx, dy = _stl_xy_extent(stl)
    assert max(dx, dy) == pytest.approx(120.0, rel=1e-3)
    assert info["print_size_mm"] == 120.0
    assert info["scale_denominator"] > 0


def test_larger_print_size_scales_the_mesh_up():
    def _extent(size: float) -> float:
        stl, _ = generate_mesh(
            GenerateMeshRequest.model_validate(
                {"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True, "print_size_mm": size}}
            ),
            provider=FakeProvider(),
            elevation_provider=FakeElevationProvider(base_elevation=15.0),
        )
        return max(_stl_xy_extent(stl))

    assert _extent(200.0) == pytest.approx(2.0 * _extent(100.0), rel=1e-3)


def test_flat_path_is_scaled_consistently_without_touching_elevation():
    # The flat path has no terrain slab spanning the frame, so its extent is
    # just the (scattered) buildings — smaller than print_size_mm. What must
    # hold is scale *consistency* (the frame's longest edge defines the factor,
    # so doubling print_size doubles the model) and that the buildings never
    # exceed the requested print size. elevation_provider=None proves the flat
    # path never calls it.
    def _extent(size: float) -> float:
        stl, _ = generate_mesh(
            GenerateMeshRequest.model_validate(
                {"selection": {"type": "bbox", **BBOX}, "terrain": {"include": False, "print_size_mm": size}}
            ),
            provider=FakeProvider(),
            elevation_provider=None,
        )
        return max(_stl_xy_extent(stl))

    e90, e180 = _extent(90.0), _extent(180.0)
    assert e180 == pytest.approx(2.0 * e90, rel=1e-3)
    assert e180 <= 180.0


def test_default_print_size_fits_a1_mini_bed_with_margin():
    # The A1 Mini bed is 180x180 mm. The default export must leave margin for
    # skirt/brim — not fill the bed edge-to-edge (the "muito largo" regression).
    stl, info = generate_mesh(
        GenerateMeshRequest.model_validate({"selection": {"type": "bbox", **BBOX}}),
        provider=FakeProvider(),
        elevation_provider=FakeElevationProvider(base_elevation=15.0),
    )
    assert info["print_size_mm"] == 150.0  # calibrated default, not 180
    assert max(_stl_xy_extent(stl)) <= 170.0  # >= ~10mm total margin on a 180 bed


def test_tiny_print_size_warns_about_unprintable_streets():
    _, info = generate_mesh(
        GenerateMeshRequest.model_validate(
            {"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True, "print_size_mm": 40.0}}
        ),
        provider=FakeProvider(),
        elevation_provider=FakeElevationProvider(base_elevation=15.0),
    )
    assert any("nozzle" in w for w in info["warnings"])


def test_mesh_endpoint_exposes_print_scale_headers(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "generate_mesh",
        lambda req: generate_mesh(req, provider=FakeProvider(), elevation_provider=FakeElevationProvider(base_elevation=15.0)),
    )
    resp = client.post(
        "/api/v1/generate/mesh",
        json={"selection": {"type": "bbox", **BBOX}, "terrain": {"include": True, "print_size_mm": 150.0}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["X-Print-Size-Mm"] == "150.0"
    assert resp.headers["X-Print-Scale"].startswith("1:")


def test_generate_svg_with_water_and_parks(monkeypatch):
    monkeypatch.setattr(main_module, "generate_fabric", lambda req: generate_fabric(req, provider=FakeProvider()))
    payload = _payload(fabric={"features": ["water", "parks"]})
    resp = client.post("/api/v1/generate", json=payload)
    assert resp.status_code == 200, resp.text
    svg = resp.json()["svg"]
    assert '<g id="water">' in svg
    assert '<g id="parks">' in svg
