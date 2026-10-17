import type { CellFacts } from "../contracts";
import { apiRequest } from "./client";
import {
  type JsonRecord,
  readArray,
  readNullable,
  readNumber,
  readOneOf,
  readRecord,
  readString,
} from "./parse";
import { DAM_STATES, parseComponents, parseExplanation } from "./rankings";

const CELL_FACTS_TIMEOUT_MS = 90_000;
const SMOKE_VALUES = ["none", "wisps", "plume", "unknown"] as const;

function parseTrend(value: unknown): CellFacts["trend"] {
  return readArray(value, "trend").map((entry) => {
    const record = readRecord(entry, "trend entry");
    return {
      week: readString(record, "week", "trend entry"),
      drying_score: readNumber(record, "drying_score", "trend entry"),
    };
  });
}

function parseNearbyDams(value: unknown): CellFacts["nearby_dams"] {
  return readArray(value, "nearby_dams").map((entry) => {
    const record = readRecord(entry, "nearby dam");
    return {
      dam_id: readString(record, "dam_id", "nearby dam"),
      distance_m: readNumber(record, "distance_m", "nearby dam"),
      last_state: readOneOf(record, "last_state", "nearby dam", DAM_STATES),
    };
  });
}

function parsePastFires(value: unknown): CellFacts["past_fires"] {
  return readArray(value, "past_fires").map((entry) => {
    const record = readRecord(entry, "past fire");
    return {
      event_id: readString(record, "event_id", "past fire"),
      start_date: readString(record, "start_date", "past fire"),
      quiet_date: readNullable(record, "quiet_date", "past fire", readString),
      p_reignite: readNullable(record, "p_reignite", "past fire", readNumber),
    };
  });
}

function parsePastChecks(value: unknown): CellFacts["past_checks"] {
  return readArray(value, "past_checks").map((entry) => {
    const record: JsonRecord = readRecord(entry, "past check");
    return {
      task_id: readString(record, "task_id", "past check"),
      checked_at: readString(record, "checked_at", "past check"),
      dam_state: readOneOf(record, "dam_state", "past check", DAM_STATES),
      smoke: readOneOf(record, "smoke", "past check", SMOKE_VALUES),
    };
  });
}

export function parseCellFacts(body: unknown): CellFacts {
  const record = readRecord(body, "cell facts");
  return {
    cell_id: readString(record, "cell_id", "cell facts"),
    region: readString(record, "region", "cell facts"),
    components: parseComponents(record.components),
    drying_score: readNumber(record, "drying_score", "cell facts"),
    rank: readNumber(record, "rank", "cell facts"),
    trend: parseTrend(record.trend),
    nearby_dams: parseNearbyDams(record.nearby_dams),
    past_fires: parsePastFires(record.past_fires),
    past_checks: parsePastChecks(record.past_checks),
    explanation: parseExplanation(record.explanation ?? null),
  };
}

export async function fetchCellFacts(cellId: string, signal?: AbortSignal): Promise<CellFacts> {
  const path = `/api/cells/${encodeURIComponent(cellId)}`;
  return parseCellFacts(await apiRequest(path, { signal, timeoutMs: CELL_FACTS_TIMEOUT_MS }));
}
