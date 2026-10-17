import type { CellPoint } from "../contracts";
import { RANKED_CELL_LIMIT, RANKED_FIT_PADDING_PX, RANKED_MAX_ZOOM } from "./region";

export type CellBounds = { south: number; west: number; north: number; east: number };

export function rankedCells(cells: readonly CellPoint[]): CellPoint[] {
  return cells.filter((cell) => cell.rank <= RANKED_CELL_LIMIT);
}

export function rankedBounds(cells: readonly CellPoint[]): CellBounds | undefined {
  const ranked = rankedCells(cells);
  const [first] = ranked;
  if (first === undefined) return undefined;
  const bounds = {
    south: first.centroid.lat,
    north: first.centroid.lat,
    west: first.centroid.lon,
    east: first.centroid.lon,
  };
  for (const { centroid } of ranked) {
    bounds.south = Math.min(bounds.south, centroid.lat);
    bounds.north = Math.max(bounds.north, centroid.lat);
    bounds.west = Math.min(bounds.west, centroid.lon);
    bounds.east = Math.max(bounds.east, centroid.lon);
  }
  return bounds;
}

export function fitToRanked(map: google.maps.Map, bounds: CellBounds): void {
  map.setOptions({ maxZoom: RANKED_MAX_ZOOM });
  map.fitBounds(bounds, RANKED_FIT_PADDING_PX);
  const idle = map.addListener("idle", () => {
    idle.remove();
    map.setOptions({ maxZoom: null });
  });
}
