import type { StyleSpecification } from "maplibre-gl";
import type { MapPreset } from "../types";

// Basemap presets for the interactive viewport (DESIGN.md §8). These concern the
// MAP ONLY and are independent of the generated SVG's output styling.
//
// CARTO raster basemaps require no API key, which keeps the MVP zero-config.
function rasterStyle(tileTheme: string, attribution: string): StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: [
          `https://a.basemaps.cartocdn.com/${tileTheme}/{z}/{x}/{y}{r}.png`,
          `https://b.basemaps.cartocdn.com/${tileTheme}/{z}/{x}/{y}{r}.png`,
          `https://c.basemaps.cartocdn.com/${tileTheme}/{z}/{x}/{y}{r}.png`,
        ],
        tileSize: 256,
        attribution,
      },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

const ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/attributions">CARTO</a>';

// OpenFreeMap ("liberty") is a free, no-API-key vector basemap (OpenMapTiles
// schema) whose style already ships a `building-3d` fill-extrusion layer
// (source "openmaptiles", source-layer "building", using render_height /
// render_min_height). We only need to add terrain on top of it.
export const MAP_3D_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

// Free, no-API-key elevation raster-dem (AWS Open Data mirror of the Mapzen
// Terrarium tileset) used to drape terrain relief under the 3D preview.
export const TERRAIN_SOURCE_ID = "prinmap-terrain";
export const TERRAIN_TILE_URL =
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

export function getMapStyle(preset: MapPreset): StyleSpecification | string {
  if (preset === "3d") return MAP_3D_STYLE_URL;
  // "Dark Minimal" -> dark basemap; "Monochrome Architectural" -> light/positron.
  return preset === "mono"
    ? rasterStyle("light_all", ATTRIBUTION)
    : rasterStyle("dark_all", ATTRIBUTION);
}
