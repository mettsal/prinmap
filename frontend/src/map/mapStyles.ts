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

export function getMapStyle(preset: MapPreset): StyleSpecification {
  // "Dark Minimal" -> dark basemap; "Monochrome Architectural" -> light/positron.
  return preset === "mono"
    ? rasterStyle("light_all", ATTRIBUTION)
    : rasterStyle("dark_all", ATTRIBUTION);
}
