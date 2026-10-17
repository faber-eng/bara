export type Source = "fixture" | "live";

const DEFAULT_SOURCES = {
  rankings: "fixture",
  cases: "fixture",
  caseDetail: "fixture",
  tiles: "live",
  clock: "live",
} as const satisfies Record<string, Source>;

export type SourceArea = keyof typeof DEFAULT_SOURCES;

function isSource(value: unknown): value is Source {
  return value === "fixture" || value === "live";
}

export function sourceFor(area: SourceArea): Source {
  const override: unknown = import.meta.env[`VITE_SOURCE_${area.toUpperCase()}`];
  return isSource(override) ? override : DEFAULT_SOURCES[area];
}
