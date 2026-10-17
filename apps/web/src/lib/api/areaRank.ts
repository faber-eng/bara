import { toGeoJsonPolygon } from "../area/polygon";
import type { AreaCell, AreaRanking, GeoPoint } from "../contracts";
import { apiRequest } from "./client";
import {
  readArray,
  readBoolean,
  readNullable,
  readNumber,
  readOneOf,
  readRecord,
  readString,
} from "./parse";
import { parsePoint } from "./rankings";

export const AREA_RANK_TIMEOUT_MS = 65_000;

function parseAreaCell(value: unknown): AreaCell {
  const record = readRecord(value, "area cell");
  return {
    cell_id: readString(record, "cell_id", "area cell"),
    centroid: parsePoint(record.centroid, "area cell.centroid"),
    drying_score: readNumber(record, "drying_score", "area cell"),
    rank: readNumber(record, "rank", "area cell"),
  };
}

export function parseAreaRanking(body: unknown): AreaRanking {
  const record = readRecord(body, "area ranking");
  return {
    status: readOneOf(record, "status", "area ranking", ["ranked", "no_peat"]),
    region: readString(record, "region", "area ranking"),
    week: readString(record, "week", "area ranking"),
    polygon_hash: readString(record, "polygon_hash", "area ranking"),
    area_km2: readNumber(record, "area_km2", "area ranking"),
    peat_cells: readNumber(record, "peat_cells", "area ranking"),
    cells: readArray(record.cells, "area ranking.cells").map(parseAreaCell),
    tile_url_template: readNullable(record, "tile_url_template", "area ranking", readString),
    cached: readBoolean(record, "cached", "area ranking"),
  };
}

export async function rankArea(points: GeoPoint[], signal?: AbortSignal): Promise<AreaRanking> {
  const body = await apiRequest("/api/areas/rank", {
    method: "POST",
    body: toGeoJsonPolygon(points),
    signal,
    timeoutMs: AREA_RANK_TIMEOUT_MS,
  });
  return parseAreaRanking(body);
}
