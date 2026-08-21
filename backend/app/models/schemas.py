"""Pydantic request/response schemas for the public API.

Selection is modelled as a discriminated union from the start so that future
selection modes (polygon, circle, admin boundary — DESIGN.md §11) can be added
without reshaping the whole API.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Union

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
class BBoxSelection(BaseModel):
    type: Literal["bbox"] = "bbox"
    west: float
    south: float
    east: float
    north: float


# Only bbox exists in the MVP, but the union keeps the door open (see §11).
Selection = Annotated[Union[BBoxSelection], Field(discriminator="type")]


# --------------------------------------------------------------------------- #
# Request sub-objects
# --------------------------------------------------------------------------- #
class Source(BaseModel):
    provider: Literal["osm"] = "osm"


class Fabric(BaseModel):
    features: List[str] = Field(default_factory=lambda: ["roads"])


class Style(BaseModel):
    preset: str = "dark-minimal"


class Parameters(BaseModel):
    # `detail` is an abstract 0..1 knob (values >1 are treated as 0..100).
    detail: float = 0.75
    # `road_width` is a global multiplier over per-class base widths.
    road_width: float = 2.0


class GenerateRequest(BaseModel):
    selection: BBoxSelection
    source: Source = Field(default_factory=Source)
    fabric: Fabric = Field(default_factory=Fabric)
    style: Style = Field(default_factory=Style)
    parameters: Parameters = Field(default_factory=Parameters)


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class GenerateResponse(BaseModel):
    job_id: str
    status: str = "completed"
    format: str = "svg"
    svg: str
    metadata: dict


class GeocodeResult(BaseModel):
    display_name: str
    lat: float
    lon: float
    # [west, south, east, north]
    bbox: List[float] | None = None


class GeocodeResponse(BaseModel):
    results: List[GeocodeResult]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
