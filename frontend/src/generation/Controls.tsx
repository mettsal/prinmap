import { bboxAreaKm2 } from "../selection/selection";
import type {
  BBoxSelection,
  FabricFeature,
  GenerateParams,
  GenerationState,
  MapPreset,
  MeshStatus,
  StylePreset,
} from "../types";

type Props = {
  selecting: boolean;
  selection: BBoxSelection | null;
  mapPreset: MapPreset;
  outputStyle: StylePreset;
  features: FabricFeature[];
  params: GenerateParams;
  generation: GenerationState;
  meshStatus: MeshStatus;
  onToggleSelect: () => void;
  onClear: () => void;
  onMapPreset: (p: MapPreset) => void;
  onOutputStyle: (s: StylePreset) => void;
  onFeaturesToggle: (f: FabricFeature) => void;
  onParams: (p: GenerateParams) => void;
  onGenerate: () => void;
  onExportMesh: () => void;
};

const FEATURE_LABELS: Record<FabricFeature, string> = {
  roads: "Roads",
  buildings: "Buildings (footprints)",
  blocks: "Block interiors",
};

export default function Controls(props: Props) {
  const {
    selecting,
    selection,
    mapPreset,
    outputStyle,
    features,
    params,
    generation,
    meshStatus,
    onToggleSelect,
    onClear,
    onMapPreset,
    onOutputStyle,
    onFeaturesToggle,
    onParams,
    onGenerate,
    onExportMesh,
  } = props;

  const busy = generation.status === "generating";
  const meshBusy = meshStatus.status === "exporting";
  const area = selection ? bboxAreaKm2(selection) : null;

  return (
    <div className="controls">
      <section className="control-block">
        <h2>Selection</h2>
        <div className="button-row">
          <button
            className={selecting ? "active" : ""}
            onClick={onToggleSelect}
            disabled={mapPreset === "3d"}
            title={mapPreset === "3d" ? "Switch to a 2D basemap to draw a selection" : undefined}
          >
            {selecting ? "Drawing… (drag on map)" : "Select rectangle"}
          </button>
          <button onClick={onClear} disabled={!selection}>
            Clear
          </button>
        </div>
        {selection ? (
          <p className="readout">
            {selection.west.toFixed(4)}, {selection.south.toFixed(4)} →{" "}
            {selection.east.toFixed(4)}, {selection.north.toFixed(4)}
            <br />
            <span className="muted">≈ {area!.toFixed(2)} km²</span>
          </p>
        ) : (
          <p className="readout muted">No region selected.</p>
        )}
      </section>

      <section className="control-block">
        <h2>Map basemap</h2>
        <select
          value={mapPreset}
          onChange={(e) => onMapPreset(e.target.value as MapPreset)}
        >
          <option value="dark">Dark Minimal</option>
          <option value="mono">Monochrome Architectural</option>
          <option value="3d">3D Preview (buildings + terrain)</option>
        </select>
      </section>

      <section className="control-block">
        <h2>Fabric layers</h2>
        {(Object.keys(FEATURE_LABELS) as FabricFeature[]).map((f) => (
          <label key={f} className="checkbox-row">
            <input
              type="checkbox"
              checked={features.includes(f)}
              onChange={() => onFeaturesToggle(f)}
            />
            {FEATURE_LABELS[f]}
          </label>
        ))}
      </section>

      <section className="control-block">
        <h2>Output style</h2>
        <select
          value={outputStyle}
          onChange={(e) => onOutputStyle(e.target.value as StylePreset)}
        >
          <option value="dark-minimal">Dark Minimal</option>
          <option value="architectural-monochrome">
            Architectural Monochrome
          </option>
        </select>

        <label className="slider">
          Detail <span className="muted">{Math.round(params.detail * 100)}</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={params.detail}
            onChange={(e) =>
              onParams({ ...params, detail: Number(e.target.value) })
            }
          />
        </label>

        <label className="slider">
          Road width <span className="muted">{params.road_width.toFixed(1)}×</span>
          <input
            type="range"
            min={0.5}
            max={5}
            step={0.1}
            value={params.road_width}
            onChange={(e) =>
              onParams({ ...params, road_width: Number(e.target.value) })
            }
          />
        </label>
      </section>

      <button
        className="generate primary"
        disabled={!selection || busy || features.length === 0}
        onClick={onGenerate}
      >
        {busy ? "Generating…" : "Generate"}
      </button>

      <p className={`status status-${generation.status}`}>
        {generation.status === "idle" && "Idle"}
        {generation.status === "generating" && "Querying OSM & building geometry…"}
        {generation.status === "success" && "Done — preview updated."}
        {generation.status === "error" && `Error: ${generation.message}`}
      </p>

      <section className="control-block">
        <h2>3D export</h2>
        <button onClick={onExportMesh} disabled={!selection || meshBusy}>
          {meshBusy ? "Extruding buildings…" : "Export 3D model (STL)"}
        </button>
        <p className="readout muted">
          Extrudes OSM building footprints by height (default ~9 m when
          unknown) onto a flat ground plane — ready for Rhino/Blender/slicing.
        </p>
        {meshStatus.status === "error" && (
          <p className="status status-error">Error: {meshStatus.message}</p>
        )}
      </section>
    </div>
  );
}
