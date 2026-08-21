import { bboxAreaKm2 } from "../selection/selection";
import type {
  BBoxSelection,
  GenerateParams,
  GenerationState,
  MapPreset,
  StylePreset,
} from "../types";

type Props = {
  selecting: boolean;
  selection: BBoxSelection | null;
  mapPreset: MapPreset;
  outputStyle: StylePreset;
  params: GenerateParams;
  generation: GenerationState;
  onToggleSelect: () => void;
  onClear: () => void;
  onMapPreset: (p: MapPreset) => void;
  onOutputStyle: (s: StylePreset) => void;
  onParams: (p: GenerateParams) => void;
  onGenerate: () => void;
};

export default function Controls(props: Props) {
  const {
    selecting,
    selection,
    mapPreset,
    outputStyle,
    params,
    generation,
    onToggleSelect,
    onClear,
    onMapPreset,
    onOutputStyle,
    onParams,
    onGenerate,
  } = props;

  const busy = generation.status === "generating";
  const area = selection ? bboxAreaKm2(selection) : null;

  return (
    <div className="controls">
      <section className="control-block">
        <h2>Selection</h2>
        <div className="button-row">
          <button
            className={selecting ? "active" : ""}
            onClick={onToggleSelect}
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
        </select>
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
        disabled={!selection || busy}
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
    </div>
  );
}
