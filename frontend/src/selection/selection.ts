import type { LngLat } from "maplibre-gl";
import type { BBoxSelection } from "../types";

/** Build a normalized (west<east, south<north) bbox from two corner points. */
export function bboxFromCorners(a: LngLat, b: LngLat): BBoxSelection {
  return {
    type: "bbox",
    west: Math.min(a.lng, b.lng),
    east: Math.max(a.lng, b.lng),
    south: Math.min(a.lat, b.lat),
    north: Math.max(a.lat, b.lat),
  };
}

/** Metres-per-degree at a latitude (equirectangular; same constants as
 * bboxLongestEdgeM and the backend's projection reference). */
function metresPerDegree(lat: number): { mLat: number; mLon: number } {
  const rad = lat * (Math.PI / 180);
  return { mLat: 110574, mLon: 111320 * Math.cos(rad) };
}

/** Build an equilateral-in-ground-metres bbox anchored at `anchor`, extending
 * toward `cursor`. The side is the larger of the two dragged extents (so the
 * square encloses the pointer), and it grows in the drag direction. Because the
 * two sides span equal metres, the projected frame is (near-)square and fills
 * the square SVG/print canvas edge-to-edge — matching examples/…/ibirapuera_full.svg. */
export function squareBboxFromCorners(anchor: LngLat, cursor: LngLat): BBoxSelection {
  const { mLat, mLon } = metresPerDegree(anchor.lat);
  const dLon = cursor.lng - anchor.lng;
  const dLat = cursor.lat - anchor.lat;
  const widthM = Math.abs(dLon) * mLon;
  const heightM = Math.abs(dLat) * mLat;
  const side = Math.max(widthM, heightM);
  const signLon = dLon >= 0 ? 1 : -1;
  const signLat = dLat >= 0 ? 1 : -1;
  const oppLon = anchor.lng + (signLon * side) / mLon;
  const oppLat = anchor.lat + (signLat * side) / mLat;
  return {
    type: "bbox",
    west: Math.min(anchor.lng, oppLon),
    east: Math.max(anchor.lng, oppLon),
    south: Math.min(anchor.lat, oppLat),
    north: Math.max(anchor.lat, oppLat),
  };
}

/** GeoJSON polygon for rendering the selection overlay on the map. */
export function bboxToFeatureCollection(
  bbox: BBoxSelection | null,
): GeoJSON.FeatureCollection {
  if (!bbox) return { type: "FeatureCollection", features: [] };
  const { west, south, east, north } = bbox;
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [west, south],
              [east, south],
              [east, north],
              [west, north],
              [west, south],
            ],
          ],
        },
      },
    ],
  };
}

/** Rough area of a bbox in km² (equirectangular approximation, good enough for UI). */
export function bboxAreaKm2(bbox: BBoxSelection): number {
  const midLat = ((bbox.south + bbox.north) / 2) * (Math.PI / 180);
  const kmPerDegLat = 110.574;
  const kmPerDegLon = 111.32 * Math.cos(midLat);
  const h = (bbox.north - bbox.south) * kmPerDegLat;
  const w = (bbox.east - bbox.west) * kmPerDegLon;
  return Math.abs(w * h);
}

/** Longest bbox edge in metres (equirectangular approximation) — the dimension
 * the STL export scales to `print_size_mm`, so the UI can preview the print
 * scale and street detail before exporting. Mirrors the backend's
 * geometry/mesh_utils.py::print_scale_mm_per_m reference (frame longest edge). */
export function bboxLongestEdgeM(bbox: BBoxSelection): number {
  const midLat = ((bbox.south + bbox.north) / 2) * (Math.PI / 180);
  const w = Math.abs(bbox.east - bbox.west) * 111320 * Math.cos(midLat);
  const h = Math.abs(bbox.north - bbox.south) * 110574;
  return Math.max(w, h);
}
