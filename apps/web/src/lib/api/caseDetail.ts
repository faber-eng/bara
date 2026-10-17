import type {
  AgentDecision,
  AgentRun,
  CaseDetail,
  Evidence,
  GeoPoint,
  Task,
  TimelineEntry,
  ToolCall,
  Verdict,
} from "../contracts";
import { sourceFor } from "../sources";
import { fetchFixtureCases, parseCase, TASK_STATUSES } from "./cases";
import { ApiError, apiRequest } from "./client";
import { fixtureClockNowMs } from "./clock";
import { applyFixtureClosure, recordFixtureClosure } from "./fixtureClosures";
import {
  type JsonRecord,
  readArray,
  readBoolean,
  readJsonObjectAt,
  readNullable,
  readNumber,
  readOneOf,
  readRecord,
  readString,
  readStringArray,
} from "./parse";

const TASK_TYPES = ["dam_check", "dam_repair", "patrol_recheck"] as const;
const EVIDENCE_KINDS = ["photo", "video", "audio"] as const;
const SUBJECTS = ["canal_dam", "burned_peat", "smoke_scene", "other"] as const;
const DAM_STATES = [
  "intact",
  "damaged",
  "broken",
  "overtopped",
  "not_applicable",
  "unknown",
] as const;
const SMOKES = ["none", "wisps", "plume", "unknown"] as const;
const HOT_GROUNDS = ["none", "possible", "clear", "unknown"] as const;
const OPEN_FLAMES = ["yes", "no", "unknown"] as const;
const CLOSABLE_FIXTURE_STATUS = "resolved_pending_human";

function parsePoint(value: unknown, label: string): GeoPoint {
  const record = readRecord(value, label);
  return { lat: readNumber(record, "lat", label), lon: readNumber(record, "lon", label) };
}

function parseTask(value: unknown): Task {
  const record = readRecord(value, "task");
  return {
    id: readString(record, "id", "task"),
    case_id: readString(record, "case_id", "task"),
    type: readOneOf(record, "type", "task", TASK_TYPES),
    assignee_id: readString(record, "assignee_id", "task"),
    target: parsePoint(record.target, "task.target"),
    deadline_at: readString(record, "deadline_at", "task"),
    status: readOneOf(record, "status", "task", TASK_STATUSES),
    cloud_task_name: readNullable(record, "cloud_task_name", "task", readString),
    attempt: readNumber(record, "attempt", "task"),
    created_at: readString(record, "created_at", "task"),
    done_at: readNullable(record, "done_at", "task", readString),
  };
}

function parseVerdict(value: unknown): Verdict {
  const record = readRecord(value, "verdict");
  return {
    subject: readOneOf(record, "subject", "verdict", SUBJECTS),
    dam_state: readOneOf(record, "dam_state", "verdict", DAM_STATES),
    smoke: readOneOf(record, "smoke", "verdict", SMOKES),
    hot_ground_signs: readOneOf(record, "hot_ground_signs", "verdict", HOT_GROUNDS),
    open_flame: readOneOf(record, "open_flame", "verdict", OPEN_FLAMES),
    transcript: readNullable(record, "transcript", "verdict", readString),
    transcript_en: readNullable(record, "transcript_en", "verdict", readString),
    reasons: readStringArray(record, "reasons", "verdict"),
    confidence: readNumber(record, "confidence", "verdict"),
    needs_human: readBoolean(record, "needs_human", "verdict"),
  };
}

function parseEvidence(value: unknown): Evidence {
  const record = readRecord(value, "evidence");
  return {
    id: readString(record, "id", "evidence"),
    task_id: readString(record, "task_id", "evidence"),
    case_id: readString(record, "case_id", "evidence"),
    kind: readOneOf(record, "kind", "evidence", EVIDENCE_KINDS),
    gcs_uri: readString(record, "gcs_uri", "evidence"),
    sha256: readString(record, "sha256", "evidence"),
    point: record.point === null ? null : parsePoint(record.point, "evidence.point"),
    captured_at: readNullable(record, "captured_at", "evidence", readString),
    verdict: record.verdict === null ? null : parseVerdict(record.verdict),
    location_ok: readNullable(record, "location_ok", "evidence", readBoolean),
    uploaded_by: readString(record, "uploaded_by", "evidence"),
    sample: readBoolean(record, "sample", "evidence"),
  };
}

function parseToolCall(value: unknown): ToolCall {
  const record = readRecord(value, "tool call");
  return {
    name: readString(record, "name", "tool call"),
    args: readJsonObjectAt(record, "args", "tool call"),
    result_summary: readString(record, "result_summary", "tool call"),
    ms: readNumber(record, "ms", "tool call"),
  };
}

function parseDecision(value: unknown): AgentDecision {
  const record = readRecord(value, "agent decision");
  return {
    decision: readString(record, "decision", "agent decision"),
    reason: readString(record, "reason", "agent decision"),
    evidence: readStringArray(record, "evidence", "agent decision"),
    next_check_at: readNullable(record, "next_check_at", "agent decision", readString),
  };
}

function parseAgentRun(value: unknown): AgentRun {
  const record = readRecord(value, "agent run");
  return {
    id: readString(record, "id", "agent run"),
    trigger: readString(record, "trigger", "agent run"),
    tool_calls: readArray(record.tool_calls, "agent run.tool_calls").map(parseToolCall),
    final_json: record.final_json === null ? null : parseDecision(record.final_json),
    model: readString(record, "model", "agent run"),
    prompt_version: readString(record, "prompt_version", "agent run"),
    started_at: readString(record, "started_at", "agent run"),
    ms: readNumber(record, "ms", "agent run"),
  };
}

function parseTimelineEntry(value: unknown): TimelineEntry {
  const record: JsonRecord = readRecord(value, "timeline entry");
  return {
    at: readString(record, "at", "timeline entry"),
    text: readString(record, "text", "timeline entry"),
  };
}

export function parseCaseDetail(body: unknown): CaseDetail {
  const record = readRecord(body, "case detail");
  return {
    case: parseCase(record.case),
    tasks: readArray(record.tasks, "case detail.tasks").map(parseTask),
    evidence: readArray(record.evidence, "case detail.evidence").map(parseEvidence),
    agent_runs: readArray(record.agent_runs, "case detail.agent_runs").map(parseAgentRun),
    timeline: readArray(record.timeline, "case detail.timeline").map(parseTimelineEntry),
  };
}

async function loadFixtureDetail(caseId: string): Promise<CaseDetail> {
  const full = parseCaseDetail((await import("@fixtures/case_detail.json")).default);
  if (full.case.id === caseId) return full;
  const summary = (await fetchFixtureCases()).find((entry) => entry.case.id === caseId);
  if (summary === undefined) throw new ApiError(`GET /api/cases/${caseId} returned 404`, 404);
  return { case: summary.case, tasks: [], evidence: [], agent_runs: [], timeline: [] };
}

async function fetchFixtureDetail(caseId: string): Promise<CaseDetail> {
  const detail = await loadFixtureDetail(caseId);
  return { ...detail, case: applyFixtureClosure(detail.case) };
}

export async function fetchCaseDetail(caseId: string, signal?: AbortSignal): Promise<CaseDetail> {
  if (sourceFor("caseDetail") === "fixture") return fetchFixtureDetail(caseId);
  return parseCaseDetail(await apiRequest(`/api/cases/${encodeURIComponent(caseId)}`, { signal }));
}

async function closeFixtureCase(caseId: string): Promise<void> {
  const detail = await fetchFixtureDetail(caseId);
  if (detail.case.status !== CLOSABLE_FIXTURE_STATUS && detail.case.status !== "human_review") {
    throw new ApiError(`POST /api/cases/${caseId}/close returned 409`, 409);
  }
  recordFixtureClosure(caseId, new Date(await fixtureClockNowMs()).toISOString());
}

export async function closeCase(caseId: string): Promise<void> {
  if (sourceFor("caseDetail") === "fixture") return closeFixtureCase(caseId);
  await apiRequest(`/api/cases/${encodeURIComponent(caseId)}/close`, { method: "POST" });
}
