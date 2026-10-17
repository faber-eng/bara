import { describe, expect, it, vi } from "vitest";
import type { CellPoint } from "../contracts";
import { fitToRanked, rankedBounds, rankedCells } from "./rankedView";

function point(id: string, lat: number, lon: number, rank: number): CellPoint {
  return { cell_id: id, centroid: { lat, lon }, drying_score: 50, rank };
}

describe("rankedView", () => {
  it("keeps the top 200 ranks only", () => {
    const cells = [point("a", 0, 0, 1), point("b", 0, 0, 200), point("c", 0, 0, 201)];

    expect(rankedCells(cells).map((cell) => cell.cell_id)).toEqual(["a", "b"]);
  });

  it("bounds the ranked cells and ignores the rest", () => {
    const cells = [
      point("a", 0.4, 101.5, 1),
      point("b", 0.9, 102.5, 150),
      point("far", 5, 110, 900),
    ];

    expect(rankedBounds(cells)).toEqual({ south: 0.4, north: 0.9, west: 101.5, east: 102.5 });
  });

  it("has no bounds when nothing is ranked", () => {
    expect(rankedBounds([point("far", 5, 110, 900)])).toBeUndefined();
    expect(rankedBounds([])).toBeUndefined();
  });

  it("fits the ranked bounds with a zoom cap that is lifted once the map is idle", () => {
    const listeners = new Map<string, () => void>();
    const map = {
      setOptions: vi.fn(),
      fitBounds: vi.fn(),
      addListener: (name: string, handler: () => void) => {
        listeners.set(name, handler);
        return { remove: () => listeners.delete(name) };
      },
    };
    const bounds = { south: 0.4, north: 0.9, west: 101.5, east: 102.5 };

    fitToRanked(map as never, bounds);

    expect(map.setOptions).toHaveBeenLastCalledWith({ maxZoom: 11 });
    expect(map.fitBounds).toHaveBeenCalledWith(bounds, 48);
    listeners.get("idle")?.();
    expect(map.setOptions).toHaveBeenLastCalledWith({ maxZoom: null });
    expect(listeners.size).toBe(0);
  });
});
