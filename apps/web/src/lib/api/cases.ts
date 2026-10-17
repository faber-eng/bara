import type {
  Case,
  CaseStatus,
  CaseSummary,
  CaseType,
  IsoDateTime,
  TaskStatus,
} from "../contracts";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import { fixtureClockNowMs } from "./clock";
import { applyFixtureOverrides } from "./fixtureOverrides";
import {
  type JsonRecord,
  readArray,
  readBoolean,
  readNullable,
  readNumber,
  readOneOf,
  readRecord,
  readString,
} from "./parse";

const CASE_TYPES: readonly CaseType[] = ["dam_risk", "reignition", "hotspot"];
const CASE_STATUSES: readonly CaseStatus[] = [
  "open",
  "assigned",
  "reviewing",
  "resolved_pending_human",
  "human_review",
  "overdue",
  "escalated",
  "monitoring",
  "closed",
];
export const TASK_STATUSES: readonly TaskStatus[] = [
  "open",
  "done",
  "overdue",
  "reassigned",
  "cancelled",
];

export function parseCase(value: unknown): Case {
  const record = readRecord(value, "case");
  const risk = readRecord(record.risk, "case.risk");
  const flags = readRecord(record.history_flags, "case.history_flags");
  return {
    id: readString(record, "id", "case"),
    type: readOneOf(record, "type", "case", CASE_TYPES),
    region: readString(record, "region", "case"),
    cell_id: readString(record, "cell_id", "case"),
    dam_id: readNullable(record, "dam_id", "case", readString),
    event_id: readNullable(record, "event_id", "case", readString),
    status: readOneOf(record, "status", "case", CASE_STATUSES),
    risk: {
      drying_score: readNullable(risk, "drying_score", "case.risk", readNumber),
      p_reignite: readNullable(risk, "p_reignite", "case.risk", readNumber),
    },
    opened_at: readString(record, "opened_at", "case"),
    closed_by: readNullable(record, "closed_by", "case", readString),
    closed_at: readNullable(record, "closed_at", "case", readString),
    history_flags: { smoke_seen: readBoolean(flags, "smoke_seen", "case.history_flags") },
    example: readBoolean(record, "example", "case"),
  };
}

function parseCaseSummary(value: unknown): CaseSummary {
  const record: JsonRecord = readRecord(value, "case summary");
  return {
    case: parseCase(record.case),
    next_deadline_at: readNullable(record, "next_deadline_at", "case summary", readString),
    task_status: readNullable(record, "task_status", "case summary", (r, key, label) =>
      readOneOf(r, key, label, TASK_STATUSES),
    ),
  };
}

export function parseCaseSummaries(body: unknown): CaseSummary[] {
  return readArray(body, "cases").map(parseCaseSummary);
}

function isPastDeadline(deadline: IsoDateTime | null, nowMs: number): boolean {
  return deadline !== null && Date.parse(deadline) <= nowMs;
}

function sweepFixtureCase(source: CaseSummary, nowMs: number): CaseSummary {
  const summary = { ...source, case: applyFixtureOverrides(source.case) };
  const dueAndOpen =
    summary.task_status === "open" && isPastDeadline(summary.next_deadline_at, nowMs);
  if (!dueAndOpen || summary.case.status !== "assigned") return summary;
  return { ...summary, task_status: "overdue", case: { ...summary.case, status: "overdue" } };
}

export async function fetchFixtureCases(): Promise<CaseSummary[]> {
  const cases = parseCaseSummaries((await import("@fixtures/cases.json")).default);
  const nowMs = await fixtureClockNowMs();
  return cases.map((summary) => sweepFixtureCase(summary, nowMs));
}

const CASES_LIMIT = 200;

export async function fetchCases(region: string, signal?: AbortSignal): Promise<CaseSummary[]> {
  if (sourceFor("cases") === "fixture") return fetchFixtureCases();
  const path = `/api/cases?region=${encodeURIComponent(region)}&limit=${CASES_LIMIT}`;
  return parseCaseSummaries(await apiRequest(path, { signal }));
}
