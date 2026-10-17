import type { AllCells, CellPoint } from "../contracts";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import { ResponseShapeError, readArray, readRecord, readString } from "./parse";
import { parseRankings } from "./rankings";

const ALL_CELLS_TIMEOUT_MS = 30_000;
const ROW_LENGTH = 5;

function numberAt(row: unknown[], index: number, label: string): number {
  const value = row[index];
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new ResponseShapeError(`${label}[${index}] is not a number`);
  }
  return value;
}

function parseRow(value: unknown): CellPoint {
  const row = readArray(value, "cell row");
  if (row.length !== ROW_LENGTH) throw new ResponseShapeError("cell row has the wrong length");
  const id = row[0];
  if (typeof id !== "string") throw new ResponseShapeError("cell row[0] is not a string");
  return {
    cell_id: id,
    centroid: { lat: numberAt(row, 1, "cell row"), lon: numberAt(row, 2, "cell row") },
    drying_score: numberAt(row, 3, "cell row"),
    rank: numberAt(row, 4, "cell row"),
  };
}

export function parseAllCells(body: unknown): AllCells {
  const record = readRecord(body, "cells");
  const rows = readArray(record.cells, "cells.cells");
  const cells: CellPoint[] = [];
  for (const row of rows) cells.push(parseRow(row));
  return {
    region: readString(record, "region", "cells"),
    week: readString(record, "week", "cells"),
    cells,
  };
}

async function fixtureCells(): Promise<AllCells> {
  const rankings = parseRankings((await import("@fixtures/rankings_riau_200.json")).default);
  return { region: rankings.region, week: rankings.week, cells: rankings.cells };
}

export async function fetchAllCells(region: string, signal?: AbortSignal): Promise<AllCells> {
  if (sourceFor("rankings") === "fixture") return fixtureCells();
  const path = `/api/cells?region=${encodeURIComponent(region)}`;
  return parseAllCells(await apiRequest(path, { signal, timeoutMs: ALL_CELLS_TIMEOUT_MS }));
}
