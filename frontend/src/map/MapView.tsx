import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { MapMouseEvent } from "maplibre-gl";
import { getMapStyle, TERRAIN_SOURCE_ID, TERRAIN_TILE_URL } from "./mapStyles";
import { bboxFromCorners, bboxToFeatureCollection } from "../selection/selection";
import type { BBoxSelection, MapPreset } from "../types";

type FlyTarget =
  | { kind: "bbox"; bbox: [number, number, number, number] }
  | { kind: "center"; center: [number, number]; zoom?: number }
  | null;

type Props = {
  preset: MapPreset;
  selecting: boolean;
  selection: BBoxSelection | null;
  onSelectionChange: (bbox: BBoxSelection) => void;
  flyTarget: FlyTarget;
};

const SOURCE_ID = "selection";

export default function MapView({
  preset,
  selecting,
  selection,
  onSelectionChange,
  flyTarget,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  // Live refs so the persistent map event handlers always read current state.
  const selectingRef = useRef(selecting);
  const onChangeRef = useRef(onSelectionChange);
  const selectionRef = useRef(selection);
  const dragStartRef = useRef<maplibregl.LngLat | null>(null);

  selectingRef.current = selecting;
  onChangeRef.current = onSelectionChange;
  selectionRef.current = selection;

  // Add the selection source/layers; safe to call repeatedly (e.g. after setStyle).
  function ensureSelectionLayers(map: maplibregl.Map) {
    if (map.getSource(SOURCE_ID)) return;
    map.addSource(SOURCE_ID, {
      type: "geojson",
      data: bboxToFeatureCollection(selectionRef.current),
    });
    map.addLayer({
      id: "selection-fill",
      type: "fill",
      source: SOURCE_ID,
      paint: { "fill-color": "#4f9cff", "fill-opacity": 0.15 },
    });
    map.addLayer({
      id: "selection-line",
      type: "line",
      source: SOURCE_ID,
      paint: { "line-color": "#4f9cff", "line-width": 2 },
    });
  }

  function setSelectionData(bbox: BBoxSelection | null) {
    const map = mapRef.current;
    const src = map?.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData(bboxToFeatureCollection(bbox) as never);
  }

  // Drape terrain relief under the 3D preview (the "liberty" style already
  // ships its own building-3d fill-extrusion layer, so we only add terrain).
  function ensureTerrain(map: maplibregl.Map) {
    if (!map.getSource(TERRAIN_SOURCE_ID)) {
      map.addSource(TERRAIN_SOURCE_ID, {
        type: "raster-dem",
        tiles: [TERRAIN_TILE_URL],
        tileSize: 256,
        encoding: "terrarium",
        maxzoom: 15,
      });
    }
    map.setTerrain({ source: TERRAIN_SOURCE_ID, exaggeration: 1.5 });
  }

  // Mount / unmount the map once.
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: getMapStyle(preset),
      center: [-46.64, -23.55], // São Paulo
      zoom: 12,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => ensureSelectionLayers(map));
    // setStyle() wipes custom layers — re-add them whenever the style reloads.
    map.on("styledata", () => {
      ensureSelectionLayers(map);
      setSelectionData(selectionRef.current);
    });

    const onDown = (e: MapMouseEvent) => {
      if (!selectingRef.current) return;
      e.preventDefault();
      map.dragPan.disable();
      dragStartRef.current = e.lngLat;
    };
    const onMove = (e: MapMouseEvent) => {
      if (!dragStartRef.current) return;
      setSelectionData(bboxFromCorners(dragStartRef.current, e.lngLat));
    };
    const onUp = (e: MapMouseEvent) => {
      if (!dragStartRef.current) return;
      const bbox = bboxFromCorners(dragStartRef.current, e.lngLat);
      dragStartRef.current = null;
      map.dragPan.enable();
      onChangeRef.current(bbox);
    };
    map.on("mousedown", onDown);
    map.on("mousemove", onMove);
    map.on("mouseup", onUp);

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Switch basemap when the preset changes; terrain/pitch follow the "3d" mode.
  // Calling setTerrain()/setStyle() before the map's style has finished its
  // first load throws ("Style is not done loading") and crashes the render —
  // so gate on isStyleLoaded()/the `load` event rather than "is this the
  // first effect run", which breaks under React.StrictMode's mount/remount.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const apply = () => {
      map.setTerrain(null);
      map.setStyle(getMapStyle(preset));
      map.once("styledata", () => {
        if (preset === "3d") {
          ensureTerrain(map);
          map.easeTo({ pitch: 60, duration: 600 });
        } else {
          map.easeTo({ pitch: 0, bearing: 0, duration: 600 });
        }
      });
    };

    if (map.isStyleLoaded()) {
      apply();
    } else {
      map.once("load", apply);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  // Reflect externally-driven selection changes (e.g. Clear button).
  useEffect(() => {
    setSelectionData(selection);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  // Crosshair cursor while in selection mode.
  useEffect(() => {
    const canvas = mapRef.current?.getCanvas();
    if (canvas) canvas.style.cursor = selecting ? "crosshair" : "";
  }, [selecting]);

  // Fly to a geocoded location or fit a bbox.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyTarget) return;
    if (flyTarget.kind === "bbox") {
      const [w, s, e, n] = flyTarget.bbox;
      map.fitBounds(
        [
          [w, s],
          [e, n],
        ],
        { padding: 60, duration: 800 },
      );
    } else {
      map.flyTo({ center: flyTarget.center, zoom: flyTarget.zoom ?? 13, duration: 800 });
    }
  }, [flyTarget]);

  return <div ref={containerRef} className="map-canvas" />;
}
