import { useCallback, useEffect, useRef, useState } from "react";
import type { GenerationState } from "../types";

type Props = { state: GenerationState };

/** Vector-native SVG preview with wheel-zoom and drag-pan (DESIGN.md §24). */
export default function Preview({ state }: Props) {
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  const svg = state.status === "success" ? state.svg : null;

  const fit = useCallback(() => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  // Reset the view whenever a new result arrives.
  useEffect(() => {
    fit();
  }, [svg, fit]);

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    setScale((s) => Math.min(12, Math.max(0.2, s * factor)));
  }
  function onPointerDown(e: React.PointerEvent) {
    dragRef.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!dragRef.current) return;
    setOffset({ x: e.clientX - dragRef.current.x, y: e.clientY - dragRef.current.y });
  }
  function onPointerUp() {
    dragRef.current = null;
  }

  function download() {
    if (!svg) return;
    const blob = new Blob([svg], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "urban-fabric.svg";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="preview">
      <header className="preview-header">
        <span>Preview</span>
        <div className="preview-actions">
          <button onClick={fit} disabled={!svg}>
            Fit
          </button>
          <button onClick={download} disabled={!svg} className="primary">
            Download SVG
          </button>
        </div>
      </header>

      <div
        className="preview-stage"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {state.status === "idle" && (
          <p className="preview-hint">
            Select a region on the map and press <strong>Generate</strong>.
          </p>
        )}
        {state.status === "generating" && (
          <p className="preview-hint">Generating urban fabric…</p>
        )}
        {state.status === "error" && (
          <p className="preview-hint error">⚠ {state.message}</p>
        )}
        {svg && (
          <div
            className="preview-svg"
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        )}
      </div>
    </section>
  );
}
