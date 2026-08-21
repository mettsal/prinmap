import { useState } from "react";
import MapView from "./map/MapView";
import Controls from "./generation/Controls";
import Preview from "./generation/Preview";
import SearchBar from "./components/SearchBar";
import { generateFabric, generateMesh } from "./api";
import type {
  BBoxSelection,
  FabricFeature,
  GenerateParams,
  GenerationState,
  MapPreset,
  MeshStatus,
  StylePreset,
  TerrainParams,
} from "./types";

type FlyTarget =
  | { kind: "bbox"; bbox: [number, number, number, number] }
  | { kind: "center"; center: [number, number]; zoom?: number }
  | null;

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [mapPreset, setMapPreset] = useState<MapPreset>("dark");
  const [outputStyle, setOutputStyle] = useState<StylePreset>("dark-minimal");
  const [features, setFeatures] = useState<FabricFeature[]>(["roads"]);
  const [selecting, setSelecting] = useState(false);
  const [selection, setSelection] = useState<BBoxSelection | null>(null);
  const [params, setParams] = useState<GenerateParams>({
    detail: 0.75,
    road_width: 2.0,
  });
  const [generation, setGeneration] = useState<GenerationState>({
    status: "idle",
  });
  const [meshStatus, setMeshStatus] = useState<MeshStatus>({ status: "idle" });
  const [terrainParams, setTerrainParams] = useState<TerrainParams>({
    include: true,
    resolution_m: 10,
    base_thickness_m: 3,
    exaggeration: 1,
    street_style: "recessed",
  });
  const [flyTarget, setFlyTarget] = useState<FlyTarget>(null);

  async function generate() {
    if (!selection || features.length === 0) return;
    setGeneration({ status: "generating" });
    try {
      const res = await generateFabric({ selection, features, style: outputStyle, params });
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

  async function exportMesh() {
    if (!selection) return;
    setMeshStatus({ status: "exporting" });
    try {
      const blob = await generateMesh(selection, params, terrainParams);
      downloadBlob(blob, "urban-fabric.stl");
      setMeshStatus({ status: "idle" });
    } catch (e) {
      setMeshStatus({
        status: "error",
        message: e instanceof Error ? e.message : "Mesh export failed",
      });
    }
  }

  function toggleFeature(f: FabricFeature) {
    setFeatures((prev) => {
      const has = prev.includes(f);
      if (has && prev.length === 1) return prev; // keep at least one layer selected
      return has ? prev.filter((x) => x !== f) : [...prev, f];
    });
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
            features={features}
            params={params}
            generation={generation}
            meshStatus={meshStatus}
            terrainParams={terrainParams}
            onToggleSelect={() => setSelecting((v) => !v)}
            onClear={() => {
              setSelection(null);
              setSelecting(false);
            }}
            onMapPreset={setMapPreset}
            onOutputStyle={setOutputStyle}
            onFeaturesToggle={toggleFeature}
            onParams={setParams}
            onGenerate={generate}
            onTerrainParams={setTerrainParams}
            onExportMesh={exportMesh}
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
