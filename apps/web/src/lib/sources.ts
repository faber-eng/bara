export type Source = "fixture" | "live";

const DEFAULT_SOURCES = {
  rankings: "live",
  cases: "live",
  caseDetail: "live",
  escalations: "fixture",
  tiles: "live",
  clock: "live",
  inbox: "live",
} as const satisfies Record<string, Source>;

export type SourceArea = keyof typeof DEFAULT_SOURCES;

function isSource(value: unknown): value is Source {
  return value === "fixture" || value === "live";
}

function readOverrides(): Record<SourceArea, unknown> {
  return {
    rankings: import.meta.env.VITE_SOURCE_RANKINGS,
    cases: import.meta.env.VITE_SOURCE_CASES,
    caseDetail: import.meta.env.VITE_SOURCE_CASEDETAIL,
    escalations: import.meta.env.VITE_SOURCE_ESCALATIONS,
    inbox: import.meta.env.VITE_SOURCE_INBOX,
    tiles: import.meta.env.VITE_SOURCE_TILES,
    clock: import.meta.env.VITE_SOURCE_CLOCK,
  };
}

export function sourceFor(area: SourceArea): Source {
  const override = readOverrides()[area];
  return isSource(override) ? override : DEFAULT_SOURCES[area];
}
