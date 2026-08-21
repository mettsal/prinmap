import { useState } from "react";
import { geocode } from "../api";
import type { GeocodeResult } from "../types";

type Props = {
  onPick: (result: GeocodeResult) => void;
};

/** Geographic search (DESIGN.md §9). Picking a result only moves the map — it
 *  does not set the generation boundary; the user still selects a rectangle. */
export default function SearchBar({ onPick }: Props) {
  const [query, setQuery] = useState("São Paulo");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResults(await geocode(query));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="search">
      <form
        className="search-row"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a city or district…"
          aria-label="Search location"
        />
        <button type="submit" disabled={loading}>
          {loading ? "…" : "Search"}
        </button>
      </form>

      {error && <p className="search-error">{error}</p>}

      {results.length > 0 && (
        <ul className="search-results">
          {results.map((r, i) => (
            <li key={i}>
              <button
                onClick={() => {
                  onPick(r);
                  setResults([]);
                }}
              >
                {r.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
