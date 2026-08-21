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
