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

export type FabricFeature = "roads" | "buildings" | "blocks";

export type GenerationState =
  | { status: "idle" }
  | { status: "generating" }
  | { status: "success"; svg: string; metadata: Record<string, unknown> }
  | { status: "error"; message: string };

export type MeshStatus =
  | { status: "idle" }
  | { status: "exporting" }
  | { status: "error"; message: string };

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

// Terrain relief for the STL export only — never affects the SVG endpoint.
export type TerrainParams = {
  include: boolean;
  resolution_m: number;
  base_thickness_m: number;
  exaggeration: number; // vertical scale on relief only, not building heights
};
