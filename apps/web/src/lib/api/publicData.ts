import type {
  CitedValue,
  PublicBulletin,
  PublicCell,
  PublicCells,
  PublicDam,
  PublicSummary,
  RecordKind,
  RecordLine,
  TileLayer,
  TileLayerKind,
} from "../contracts";
import { apiRequest } from "./client";
import {
  type JsonRecord,
  ResponseShapeError,
  readArray,
  readNullable,
  readNumber,
  readOneOf,
  readRecord,
  readString,
} from "./parse";
import { DAM_STATES, parseComponents, parsePoint } from "./rankings";
import { parseTileLayer } from "./tiles";

const RECORD_KINDS: readonly RecordKind[] = ["opened", "task", "overdue", "escalated", "closed"];
const BULLETIN_SOURCES = ["gemini", "template"] as const;
const MAP_CELL_LIMIT = 200;
const RECORD_LIMIT = 50;
const TILES_TIMEOUT_MS = 30_000;

export type PublicQuery = { region: string; week: string | undefined };

function weekQuery(week: string | undefined, extra = ""): string {
  const params = new URLSearchParams(extra);
  if (week !== undefined) params.set("week", week);
  const text = params.toString();
  return text === "" ? "" : `?${text}`;
}

export function publicPath(region: string, route: string, week?: string, extra = ""): string {
  return `/api/public/${encodeURIComponent(region)}/${route}${weekQuery(week, extra)}`;
}

export function parseSummary(body: unknown): PublicSummary {
  const record = readRecord(body, "summary");
  const asOf = readRecord(record.data_as_of, "summary.data_as_of");
  return {
    region: readString(record, "region", "summary"),
    week: readString(record, "week", "summary"),
    high_risk_cells: readNumber(record, "high_risk_cells", "summary"),
    dams_broken: readNumber(record, "dams_broken", "summary"),
    cases_open: readNumber(record, "cases_open", "summary"),
    cases_escalated: readNumber(record, "cases_escalated", "summary"),
    cases_closed: readNumber(record, "cases_closed", "summary"),
    median_days_to_repair: readNullable(record, "median_days_to_repair", "summary", readNumber),
    tasks_on_time_pct: readNullable(record, "tasks_on_time_pct", "summary", readNumber),
    data_as_of: {
      s1_pass_date: readString(asOf, "s1_pass_date", "summary.data_as_of"),
      ranking_run_at: readString(asOf, "ranking_run_at", "summary.data_as_of"),
    },
  };
}

function parseCell(value: unknown): PublicCell {
  const record = readRecord(value, "public cell");
  return {
    cell_id: readString(record, "cell_id", "public cell"),
    centroid: parsePoint(record.centroid, "public cell.centroid"),
    drying_score: readNumber(record, "drying_score", "public cell"),
    rank: readNumber(record, "rank", "public cell"),
    rank_change: readNullable(record, "rank_change", "public cell", readNumber),
    components: parseComponents(record.components),
  };
}

export function parseCells(body: unknown): PublicCells {
  const record = readRecord(body, "public cells");
  return {
    region: readString(record, "region", "public cells"),
    week: readString(record, "week", "public cells"),
    cells: readArray(record.cells, "public cells.cells").map(parseCell),
  };
}

function parseDam(value: unknown): PublicDam {
  const record = readRecord(value, "public dam");
  return {
    id: readString(record, "id", "public dam"),
    point: parsePoint(record.point, "public dam.point"),
    last_state: readOneOf(record, "last_state", "public dam", DAM_STATES),
    last_checked_at: readNullable(record, "last_checked_at", "public dam", readString),
    repair_due_at: readNullable(record, "repair_due_at", "public dam", readString),
  };
}

export function parseDams(body: unknown): PublicDam[] {
  return readArray(body, "public dams").map(parseDam);
}

function parseRecordLine(value: unknown): RecordLine {
  const record = readRecord(value, "record line");
  return {
    at: readString(record, "at", "record line"),
    cell_id: readString(record, "cell_id", "record line"),
    kind: readOneOf(record, "kind", "record line", RECORD_KINDS),
    text: readString(record, "text", "record line"),
  };
}

export function parseRecord(body: unknown): RecordLine[] {
  return readArray(body, "record").map(parseRecordLine);
}

function parseCitedValue(value: unknown): CitedValue {
  const record = readRecord(value, "cited");
  const cited = record.value;
  if (cited !== null && typeof cited !== "number" && typeof cited !== "string") {
    throw new ResponseShapeError("cited.value is not a number or a string");
  }
  return { field: readString(record, "field", "cited"), value: cited };
}

function readNullableOneOf<T extends string>(
  record: JsonRecord,
  key: string,
  allowed: readonly T[],
): T | null {
  return record[key] === null ? null : readOneOf(record, key, "bulletin", allowed);
}

export function parseBulletin(body: unknown): PublicBulletin {
  const record = readRecord(body, "bulletin");
  return {
    region: readString(record, "region", "bulletin"),
    week: readString(record, "week", "bulletin"),
    text_id: readNullable(record, "text_id", "bulletin", readString),
    text_en: readNullable(record, "text_en", "bulletin", readString),
    cited: readArray(record.cited, "bulletin.cited").map(parseCitedValue),
    source: readNullableOneOf(record, "source", BULLETIN_SOURCES),
    model: readNullable(record, "model", "bulletin", readString),
    prompt_version: readNullable(record, "prompt_version", "bulletin", readString),
    created_at: readNullable(record, "created_at", "bulletin", readString),
  };
}

export async function fetchSummary(query: PublicQuery, signal?: AbortSignal) {
  const path = publicPath(query.region, "summary", query.week);
  return parseSummary(await apiRequest(path, { signal, anonymous: true }));
}

export async function fetchCells(query: PublicQuery, signal?: AbortSignal) {
  const extra = `limit=${MAP_CELL_LIMIT}`;
  const path = publicPath(query.region, "cells", query.week, extra);
  return parseCells(await apiRequest(path, { signal, anonymous: true }));
}

export async function fetchDams(region: string, signal?: AbortSignal) {
  return parseDams(await apiRequest(publicPath(region, "dams"), { signal, anonymous: true }));
}

export async function fetchRecord(region: string, signal?: AbortSignal) {
  const path = publicPath(region, "record", undefined, `limit=${RECORD_LIMIT}`);
  return parseRecord(await apiRequest(path, { signal, anonymous: true }));
}

export async function fetchBulletin(query: PublicQuery, signal?: AbortSignal) {
  const path = publicPath(query.region, "bulletin", query.week);
  return parseBulletin(await apiRequest(path, { signal, anonymous: true }));
}

export async function fetchTiles(
  layer: TileLayerKind,
  query: PublicQuery,
  signal?: AbortSignal,
): Promise<TileLayer> {
  const params = new URLSearchParams({ region: query.region });
  if (query.week !== undefined) params.set("week", query.week);
  const path = `/api/tiles/${layer}?${params.toString()}`;
  const body = await apiRequest(path, { signal, anonymous: true, timeoutMs: TILES_TIMEOUT_MS });
  return parseTileLayer(body);
}
