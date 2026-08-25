import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { MapMouseEvent } from "maplibre-gl";
import { getMapStyle, TERRAIN_SOURCE_ID, TERRAIN_TILE_URL } from "./mapStyles";
import {
  bboxToFeatureCollection,
  squareBboxFromCorners,
} from "../selection/selection";
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
  const presetRef = useRef(preset);
  const dragStartRef = useRef<maplibregl.LngLat | null>(null);

  // Corner resize handles (DOM markers). One per bbox corner, fixed order
  // SW/SE/NE/NW; the diagonally-opposite corner is (i+2)%4.
  const handlesRef = useRef<maplibregl.Marker[]>([]);
  const handlesVisibleRef = useRef(false);
  const draggingHandleRef = useRef(false);
  const dragOppositeRef = useRef<maplibregl.LngLat | null>(null);

  // Moving the whole selection by dragging its interior (translate, keep size).
  const movingRef = useRef(false);
  const moveLastRef = useRef<maplibregl.LngLat | null>(null);
  const movedBboxRef = useRef<BBoxSelection | null>(null);

  selectingRef.current = selecting;
  onChangeRef.current = onSelectionChange;
  selectionRef.current = selection;
  presetRef.current = preset;

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

  // Translate a bbox by (dLng, dLat), preserving its size.
  function shiftBbox(b: BBoxSelection, dLng: number, dLat: number): BBoxSelection {
    return {
      type: "bbox",
      west: b.west + dLng,
      east: b.east + dLng,
      south: b.south + dLat,
      north: b.north + dLat,
    };
  }

  // Corners in a fixed order: SW, SE, NE, NW. Opposite corner is (i+2)%4.
  function cornersOf(b: BBoxSelection): maplibregl.LngLat[] {
    return [
      new maplibregl.LngLat(b.west, b.south),
      new maplibregl.LngLat(b.east, b.south),
      new maplibregl.LngLat(b.east, b.north),
      new maplibregl.LngLat(b.west, b.north),
    ];
  }

  // Lazily create the 4 draggable corner handles (once). Dragging a corner keeps
  // the box square, anchored at the diagonally-opposite (fixed) corner.
  function ensureHandles() {
    if (handlesRef.current.length) return;
    for (let i = 0; i < 4; i++) {
      const el = document.createElement("div");
      el.className = "sel-handle";
      const marker = new maplibregl.Marker({ element: el, draggable: true });
      marker.on("dragstart", () => {
        const sel = selectionRef.current;
        if (!sel) return;
        draggingHandleRef.current = true;
        dragOppositeRef.current = cornersOf(sel)[(i + 2) % 4];
      });
      marker.on("drag", () => {
        const opposite = dragOppositeRef.current;
        if (!opposite) return;
        const box = squareBboxFromCorners(opposite, marker.getLngLat());
        setSelectionData(box);
        // Keep the other three handles glued to the live square; leave the one
        // under the cursor to maplibre so the drag stays smooth.
        const cs = cornersOf(box);
        handlesRef.current.forEach((m, j) => {
          if (j !== i) m.setLngLat(cs[j]);
        });
      });
      marker.on("dragend", () => {
        const opposite = dragOppositeRef.current;
        dragOppositeRef.current = null;
        draggingHandleRef.current = false;
        if (!opposite) return;
        // Commit; the [selection] effect re-syncs every handle to the snapped box.
        onChangeRef.current(squareBboxFromCorners(opposite, marker.getLngLat()));
      });
      handlesRef.current.push(marker);
    }
  }

  // Show handles only for a committed selection outside draw mode and the 3D
  // preset; otherwise hide them. Skipped mid-drag so we never fight the marker.
  function syncHandles() {
    const map = mapRef.current;
    if (!map || draggingHandleRef.current || movingRef.current) return;
    const sel = selectionRef.current;
    const show = !!sel && !selectingRef.current && presetRef.current !== "3d";
    if (!show) {
      if (handlesVisibleRef.current) {
        handlesRef.current.forEach((m) => m.remove());
        handlesVisibleRef.current = false;
      }
      return;
    }
    ensureHandles();
    const cs = cornersOf(sel!);
    handlesRef.current.forEach((m, j) => {
      m.setLngLat(cs[j]);
      if (!handlesVisibleRef.current) m.addTo(map);
    });
    handlesVisibleRef.current = true;
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

    map.on("load", () => {
      ensureSelectionLayers(map);
      syncHandles();
    });
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
      // Moving the whole box (interior drag) wins over drawing/idle.
      if (movingRef.current && moveLastRef.current && movedBboxRef.current) {
        const dLng = e.lngLat.lng - moveLastRef.current.lng;
        const dLat = e.lngLat.lat - moveLastRef.current.lat;
        moveLastRef.current = e.lngLat;
        const box = shiftBbox(movedBboxRef.current, dLng, dLat);
        movedBboxRef.current = box;
        setSelectionData(box);
        const cs = cornersOf(box);
        handlesRef.current.forEach((m, j) => m.setLngLat(cs[j]));
        return;
      }
      if (!dragStartRef.current) return;
      setSelectionData(squareBboxFromCorners(dragStartRef.current, e.lngLat));
    };
    const onUp = () => {
      if (movingRef.current) {
        movingRef.current = false;
        moveLastRef.current = null;
        map.dragPan.enable();
        if (movedBboxRef.current) onChangeRef.current(movedBboxRef.current);
        return;
      }
    };
    const onUpDraw = (e: MapMouseEvent) => {
      if (!dragStartRef.current) return;
      const bbox = squareBboxFromCorners(dragStartRef.current, e.lngLat);
      dragStartRef.current = null;
      map.dragPan.enable();
      onChangeRef.current(bbox);
    };
    // Interior drag = translate the whole selection (like terraprinter). Only
    // outside draw mode / the 3D preset; corner handles keep their own drag.
    const onInteriorDown = (e: MapMouseEvent) => {
      const sel = selectionRef.current;
      if (selectingRef.current || !sel || presetRef.current === "3d") return;
      e.preventDefault();
      map.dragPan.disable();
      movingRef.current = true;
      moveLastRef.current = e.lngLat;
      movedBboxRef.current = sel;
    };
    const setMoveCursor = () => {
      if (!selectingRef.current) map.getCanvas().style.cursor = "move";
    };
    const clearMoveCursor = () => {
      if (!selectingRef.current) map.getCanvas().style.cursor = "";
    };
    map.on("mousedown", onDown);
    map.on("mousedown", "selection-fill", onInteriorDown);
    map.on("mouseenter", "selection-fill", setMoveCursor);
    map.on("mouseleave", "selection-fill", clearMoveCursor);
    map.on("mousemove", onMove);
    map.on("mouseup", onUp);
    map.on("mouseup", onUpDraw);

    return () => {
      handlesRef.current.forEach((m) => m.remove());
      handlesRef.current = [];
      handlesVisibleRef.current = false;
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
    syncHandles(); // hide handles in 3D, restore them in 2D
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  // Reflect externally-driven selection changes (e.g. Clear button, resize commit).
  useEffect(() => {
    setSelectionData(selection);
    syncHandles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  // Crosshair cursor while in selection mode; hide handles while drawing.
  useEffect(() => {
    const canvas = mapRef.current?.getCanvas();
    if (canvas) canvas.style.cursor = selecting ? "crosshair" : "";
    syncHandles();
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
