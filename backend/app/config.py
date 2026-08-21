"""Application configuration.

Values are intentionally conservative for the MVP and can later be moved to
environment variables or a settings file without touching call sites.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Selection guardrails (see DESIGN.md §29).
    max_selection_area_km2: float = 25.0
    min_selection_area_m2: float = 100.0

    # External services.
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    request_timeout_s: float = 60.0
    user_agent: str = "prinmap-urban-fabric/0.1 (https://github.com/prinmap)"

    # Output canvas.
    svg_size: int = 1600


settings = Settings()
