import type {
  DamState,
  GeoPoint,
  RankExplanation,
  RankedCell,
  RankedDam,
  RankingComponents,
  Rankings,
  Scalar,
} from "../contracts";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import {
  type JsonRecord,
  ResponseShapeError,
  readArray,
  readBoolean,
  readNullable,
  readNumber,
  readOneOf,
  readRecord,
  readString,
} from "./parse";

export const DAM_STATES: readonly DamState[] = [
  "intact",
  "damaged",
  "broken",
  "overtopped",
  "not_applicable",
  "unknown",
];

export function parsePoint(value: unknown, label: string): GeoPoint {
  const record = readRecord(value, label);
  return { lat: readNumber(record, "lat", label), lon: readNumber(record, "lon", label) };
}

function parsePeatClass(record: JsonRecord): 1 | 2 {
  const value = readNumber(record, "peat_class", "components");
  if (value === 1 || value === 2) return value;
  throw new ResponseShapeError("components.peat_class is not 1 or 2");
}

export function parseComponents(value: unknown): RankingComponents {
  const record = readRecord(value, "components");
  return {
    s1_anom_db: readNullable(record, "s1_anom_db", "components", readNumber),
    rain_30d_mm: readNumber(record, "rain_30d_mm", "components"),
    rain_deficit_pct: readNumber(record, "rain_deficit_pct", "components"),
    canal_dist_m: readNumber(record, "canal_dist_m", "components"),
    peat_class: parsePeatClass(record),
  };
}

function parseCited(value: unknown): { [field: string]: Scalar } {
  const record = readRecord(value, "explanation.cited");
  const cited: { [field: string]: Scalar } = {};
  for (const [key, entry] of Object.entries(record)) {
    if (typeof entry !== "number" && typeof entry !== "string") {
      throw new ResponseShapeError(`explanation.cited.${key} is not a number or string`);
    }
    cited[key] = entry;
  }
  return cited;
}

export function parseExplanation(value: unknown): RankExplanation | null {
  if (value === null) return null;
  const record = readRecord(value, "explanation");
  return { text: readString(record, "text", "explanation"), cited: parseCited(record.cited) };
}

function parseCell(value: unknown): RankedCell {
  const record = readRecord(value, "cell");
  return {
    cell_id: readString(record, "cell_id", "cell"),
    region: readString(record, "region", "cell"),
    week_start: readString(record, "week_start", "cell"),
    centroid: parsePoint(record.centroid, "cell.centroid"),
    components: parseComponents(record.components),
    drying_score: readNumber(record, "drying_score", "cell"),
    rank: readNumber(record, "rank", "cell"),
    rank_change: readNullable(record, "rank_change", "cell", readNumber),
    stale_s1: readBoolean(record, "stale_s1", "cell"),
    explanation: parseExplanation(record.explanation),
  };
}

function parseDam(value: unknown): RankedDam {
  const record = readRecord(value, "dam");
  return {
    dam_id: readString(record, "dam_id", "dam"),
    region: readString(record, "region", "dam"),
    cell_id: readString(record, "cell_id", "dam"),
    point: parsePoint(record.point, "dam.point"),
    last_state: readOneOf(record, "last_state", "dam", DAM_STATES),
    last_checked_at: readNullable(record, "last_checked_at", "dam", readString),
    drying_score: readNumber(record, "drying_score", "dam"),
    rank: readNumber(record, "rank", "dam"),
    example: readBoolean(record, "example", "dam"),
  };
}

export function parseRankings(body: unknown): Rankings {
  const record = readRecord(body, "rankings");
  return {
    region: readString(record, "region", "rankings"),
    week: readString(record, "week", "rankings"),
    cells: readArray(record.cells, "rankings.cells").map(parseCell),
    dams: readArray(record.dams, "rankings.dams").map(parseDam),
  };
}

export async function fetchRankings(region: string, signal?: AbortSignal): Promise<Rankings> {
  if (sourceFor("rankings") === "fixture") {
    return parseRankings((await import("@fixtures/rankings_riau_200.json")).default);
  }
  return parseRankings(await apiRequest(`/api/rankings/${encodeURIComponent(region)}`, { signal }));
}
