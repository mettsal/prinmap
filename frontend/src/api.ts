import type {
  BBoxSelection,
  GenerateParams,
  GenerateResponse,
  GeocodeResult,
  StylePreset,
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
  style: StylePreset;
  params: GenerateParams;
}): Promise<GenerateResponse> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      selection: args.selection,
      source: { provider: "osm" },
      fabric: { features: ["roads"] },
      style: { preset: args.style },
      parameters: args.params,
    }),
  });
  if (!res.ok) throw await toError(res);
  return res.json();
}

export async function geocode(query: string): Promise<GeocodeResult[]> {
  const res = await fetch(`${BASE}/geocode?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw await toError(res);
  const body = await res.json();
  return body.results ?? [];
}
