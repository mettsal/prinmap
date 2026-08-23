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
    # Any of "roads", "buildings", "blocks" (city-block interiors derived from
    # the street network), "water", "parks" (woods/forests). Layers are
    # independently toggleable and drawn in that painter's order (blocks ->
    # parks -> water -> buildings -> roads).
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


class TerrainParameters(BaseModel):
    """Terrain relief + physical print-scale controls for the STL export only —
    never affects the SVG endpoint.

    The mesh is emitted **pre-scaled to a real printed size in millimetres**
    (`print_size_mm`, the model's longest edge). Every surface-treatment depth
    below is authored in *printed millimetres* and back-converted to world
    metres via the derived scale, so features survive at a real 0.4 mm-nozzle /
    0.2 mm-layer resolution instead of collapsing to microns after slicer
    scaling (which was the original "nothing prints" bug — see AGENTS.md).
    """

    include: bool = True
    resolution_m: float = 10.0  # elevation-grid spacing; may be silently coarsened, see geometry/terrain.py
    exaggeration: float = 1.0  # vertical scale on terrain relief only (not building heights)
    # How streets are differentiated on the (mono-material) printed terrain:
    # "recessed" carves a channel following the local slope; "textured" embosses
    # a surface pattern at the same height. Water/parks always get their own
    # fixed treatment (flattened / textured respectively) whenever present.
    street_style: Literal["recessed", "textured"] = "recessed"

    # --- Physical print scale ------------------------------------------------
    # Target longest edge of the *printed* model, in millimetres. Bambu Lab A1
    # Mini bed is 180×180 mm; default 150 leaves a ~15 mm margin per side for
    # skirt/brim (180 filled the bed edge-to-edge). The UI caps this at 180.
    print_size_mm: float = Field(default=150.0, gt=0)
    # Printer profile — used to clamp treatment depths to a printable minimum
    # (>= 2 layer heights) and to warn when a road, once scaled, is narrower
    # than a single extruded line.
    nozzle_diameter_mm: float = Field(default=0.4, gt=0)
    layer_height_mm: float = Field(default=0.2, gt=0)

    # --- Depths/thicknesses in PRINTED millimetres ---------------------------
    base_thickness_mm: float = Field(default=3.0, gt=0)  # solid plinth below the lowest terrain point
    street_recess_depth_mm: float = Field(default=0.6, ge=0)  # "recessed" mode channel depth
    street_texture_amplitude_mm: float = Field(default=0.4, ge=0)  # "textured" mode bump height
    park_texture_amplitude_mm: float = Field(default=0.4, ge=0)  # park ground-texture bump height
    water_submersion_mm: float = Field(default=0.5, ge=0)  # water sunk below its rim


class GenerateMeshRequest(BaseModel):
    """Input for the 3D building-mesh (STL) export — always buildings-only."""

    selection: BBoxSelection
    source: Source = Field(default_factory=Source)
    parameters: Parameters = Field(default_factory=Parameters)
    terrain: TerrainParameters = Field(default_factory=TerrainParameters)


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
