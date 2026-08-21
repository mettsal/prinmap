from __future__ import annotations

import app.main as main_module
from app.main import app
from app.service import generate_fabric
from fastapi.testclient import TestClient

from ..fixtures import BBOX, FakeProvider

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
