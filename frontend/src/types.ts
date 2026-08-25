// Selection is a discriminated union from the start (DESIGN.md §11); only bbox
// exists in the MVP.
export type BBoxSelection = {
  type: "bbox";
  west: number;
  south: number;
  east: number;
  north: number;
};

export type Selection = BBoxSelection;

export type StylePreset = "dark-minimal" | "architectural-monochrome";
// "3d" is a preview-only basemap (OpenFreeMap + extruded buildings + terrain)
// — it never affects the generated SVG/STL artifact.
export type MapPreset = "dark" | "mono" | "3d";

export type FabricFeature = "roads" | "buildings" | "blocks" | "water" | "parks";

// How streets are differentiated on the (mono-material) printed terrain.
export type StreetStyle = "recessed" | "raised" | "textured";

export type GenerationState =
  | { status: "idle" }
  | { status: "generating" }
  | { status: "success"; svg: string; metadata: Record<string, unknown> }
  | { status: "error"; message: string };

export type MeshStatus =
  | { status: "idle" }
  | { status: "exporting" }
  | { status: "success"; scale: string; footprintMm: string; warnings: string }
  | { status: "error"; message: string };

// Print-scale facts returned as response headers by the mesh endpoint.
export type MeshPrintInfo = {
  scale: string; // e.g. "1:17006"
  sizeMm: string;
  footprintMm: string; // e.g. "180x162.5"
  warnings: string;
};

export type GenerateResponse = {
  job_id: string;
  status: string;
  format: string;
  svg: string;
  metadata: Record<string, unknown>;
};

export type GeocodeResult = {
  display_name: string;
  lat: number;
  lon: number;
  bbox: number[] | null; // [west, south, east, north]
};

export type GenerateParams = {
  detail: number; // 0..1
  road_width: number;
};

// Terrain relief + physical print-scale for the STL export only — never
// affects the SVG endpoint. Depths are in PRINTED millimetres; the mesh is
// emitted pre-scaled to `print_size_mm` on its longest edge.
export type TerrainParams = {
  include: boolean;
  resolution_m: number;
  max_grid_points_per_axis: number; // grid-density cap; higher = finer streets, more compute
  exaggeration: number; // vertical scale on relief only, not building heights
  street_style: StreetStyle;
  // Physical print scale (millimetres).
  print_size_mm: number; // target longest edge of the printed model
  nozzle_diameter_mm: number;
  layer_height_mm: number;
  base_thickness_mm: number;
  street_recess_depth_mm: number;
  street_texture_amplitude_mm: number;
  park_texture_amplitude_mm: number;
  water_submersion_mm: number;
};
