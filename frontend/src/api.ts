import type {
  BBoxSelection,
  FabricFeature,
  GenerateParams,
  GenerateResponse,
  GeocodeResult,
  MeshPrintInfo,
  StylePreset,
  TerrainParams,
} from "./types";

const BASE = "/api/v1";

/** Translate a backend `{error:{code,message}}` body into a thrown Error. */
async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    if (body?.error?.message) return new Error(body.error.message);
    if (body?.detail) return new Error(JSON.stringify(body.detail));
  } catch {
    /* fall through */
  }
  return new Error(`Request failed (${res.status})`);
}

export async function generateFabric(args: {
  selection: BBoxSelection;
  features: FabricFeature[];
  style: StylePreset;
  params: GenerateParams;
}): Promise<GenerateResponse> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      selection: args.selection,
      source: { provider: "osm" },
      fabric: { features: args.features },
      style: { preset: args.style },
      parameters: args.params,
    }),
  });
  if (!res.ok) throw await toError(res);
  return res.json();
}

/** Buildings-only 3D mesh export (STL) — a separate artifact from the SVG.
 * Returns the STL blob plus the print-scale facts the backend reports via
 * `X-Print-*` headers (derived scale, physical footprint, printability
 * warnings). */
export async function generateMesh(
  selection: BBoxSelection,
  params: GenerateParams,
  terrain: TerrainParams,
): Promise<{ blob: Blob; info: MeshPrintInfo }> {
  const res = await fetch(`${BASE}/generate/mesh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      selection,
      source: { provider: "osm" },
      parameters: params,
      terrain,
    }),
  });
  if (!res.ok) throw await toError(res);
  const info: MeshPrintInfo = {
    scale: res.headers.get("X-Print-Scale") ?? "",
    sizeMm: res.headers.get("X-Print-Size-Mm") ?? "",
    footprintMm: res.headers.get("X-Print-Footprint-Mm") ?? "",
    warnings: res.headers.get("X-Print-Warnings") ?? "",
  };
  return { blob: await res.blob(), info };
}

export async function geocode(query: string): Promise<GeocodeResult[]> {
  const res = await fetch(`${BASE}/geocode?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw await toError(res);
  const body = await res.json();
  return body.results ?? [];
}
