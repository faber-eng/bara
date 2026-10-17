export const WEEK_START = "ops-week-start";
export const WEEK_SWAP = "ops-week-swap";
export const LAYER_START = "ops-layer-start";
export const LAYER_SHOWN = "ops-layer-shown";

export function markStart(name: string): void {
  performance.mark(name);
}

export function measureSince(start: string, measure: string): void {
  if (performance.getEntriesByName(start, "mark").length === 0) return;
  performance.measure(measure, start);
  performance.clearMarks(start);
}
