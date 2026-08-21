import { useState } from "react";
import MapView from "./map/MapView";
import Controls from "./generation/Controls";
import Preview from "./generation/Preview";
import SearchBar from "./components/SearchBar";
import { generateFabric } from "./api";
import type {
  BBoxSelection,
  GenerateParams,
  GenerationState,
  MapPreset,
  StylePreset,
} from "./types";

type FlyTarget =
  | { kind: "bbox"; bbox: [number, number, number, number] }
  | { kind: "center"; center: [number, number]; zoom?: number }
  | null;

export default function App() {
  const [mapPreset, setMapPreset] = useState<MapPreset>("dark");
  const [outputStyle, setOutputStyle] = useState<StylePreset>("dark-minimal");
  const [selecting, setSelecting] = useState(false);
  const [selection, setSelection] = useState<BBoxSelection | null>(null);
  const [params, setParams] = useState<GenerateParams>({
    detail: 0.75,
    road_width: 2.0,
  });
  const [generation, setGeneration] = useState<GenerationState>({
    status: "idle",
  });
  const [flyTarget, setFlyTarget] = useState<FlyTarget>(null);

  async function generate() {
    if (!selection) return;
    setGeneration({ status: "generating" });
    try {
      const res = await generateFabric({
        selection,
        style: outputStyle,
        params,
      });
      setGeneration({
        status: "success",
        svg: res.svg,
        metadata: res.metadata,
      });
    } catch (e) {
      setGeneration({
        status: "error",
        message: e instanceof Error ? e.message : "Generation failed",
      });
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Urban Fabric Generator</h1>
        <span className="tagline">
          procedural urban morphology from OpenStreetMap
        </span>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <SearchBar
            onPick={(r) => {
              if (r.bbox && r.bbox.length === 4) {
                setFlyTarget({
                  kind: "bbox",
                  bbox: r.bbox as [number, number, number, number],
                });
              } else {
                setFlyTarget({ kind: "center", center: [r.lon, r.lat] });
              }
            }}
          />
          <Controls
            selecting={selecting}
            selection={selection}
            mapPreset={mapPreset}
            outputStyle={outputStyle}
            params={params}
            generation={generation}
            onToggleSelect={() => setSelecting((v) => !v)}
            onClear={() => {
              setSelection(null);
              setSelecting(false);
            }}
            onMapPreset={setMapPreset}
            onOutputStyle={setOutputStyle}
            onParams={setParams}
            onGenerate={generate}
          />
        </aside>

        <main className="map-area">
          <MapView
            preset={mapPreset}
            selecting={selecting}
            selection={selection}
            onSelectionChange={(b) => {
              setSelection(b);
              setSelecting(false);
            }}
            flyTarget={flyTarget}
          />
        </main>

        <Preview state={generation} />
      </div>
    </div>
  );
}
