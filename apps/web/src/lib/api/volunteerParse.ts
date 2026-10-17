import type {
  Channel,
  DamState,
  Evidence,
  EvidenceKind,
  GeoPoint,
  HotGround,
  Message,
  MessageThread,
  OpenFlame,
  Smoke,
  Subject,
  Task,
  TaskStatus,
  TaskType,
  Verdict,
} from "../contracts";
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

const SUBJECTS: readonly Subject[] = ["canal_dam", "burned_peat", "smoke_scene", "other"];
const DAM_STATES: readonly DamState[] = [
  "intact",
  "damaged",
  "broken",
  "overtopped",
  "not_applicable",
  "unknown",
];
const SMOKES: readonly Smoke[] = ["none", "wisps", "plume", "unknown"];
const HOT_GROUNDS: readonly HotGround[] = ["none", "possible", "clear", "unknown"];
const OPEN_FLAMES: readonly OpenFlame[] = ["yes", "no", "unknown"];
const EVIDENCE_KINDS: readonly EvidenceKind[] = ["photo", "video", "audio"];
const TASK_TYPES: readonly TaskType[] = ["dam_check", "dam_repair", "patrol_recheck"];
const TASK_STATUSES: readonly TaskStatus[] = ["open", "done", "overdue", "reassigned", "cancelled"];
const THREADS: readonly MessageThread[] = ["volunteer", "brigade", "ops"];
const CHANNELS: readonly Channel[] = ["web", "whatsapp"];

function readStringItem(value: unknown, label: string): string {
  if (typeof value !== "string") throw new ResponseShapeError(`${label} is not a string`);
  return value;
}

export function parseGeoPoint(value: unknown, label: string): GeoPoint {
  const record = readRecord(value, label);
  return { lat: readNumber(record, "lat", label), lon: readNumber(record, "lon", label) };
}

function readPoint(record: JsonRecord, key: string, label: string): GeoPoint {
  return parseGeoPoint(record[key], `${label}.${key}`);
}

export function parseVerdict(value: unknown): Verdict {
  const record = readRecord(value, "verdict");
  return {
    subject: readOneOf(record, "subject", "verdict", SUBJECTS),
    dam_state: readOneOf(record, "dam_state", "verdict", DAM_STATES),
    smoke: readOneOf(record, "smoke", "verdict", SMOKES),
    hot_ground_signs: readOneOf(record, "hot_ground_signs", "verdict", HOT_GROUNDS),
    open_flame: readOneOf(record, "open_flame", "verdict", OPEN_FLAMES),
    transcript: readNullable(record, "transcript", "verdict", readString),
    transcript_en: readNullable(record, "transcript_en", "verdict", readString),
    reasons: readArray(record.reasons, "verdict.reasons").map((item) =>
      readStringItem(item, "verdict.reasons[]"),
    ),
    confidence: readNumber(record, "confidence", "verdict"),
    needs_human: readBoolean(record, "needs_human", "verdict"),
  };
}

function readOptionalPoint(record: JsonRecord): GeoPoint | null {
  return record.point === null || record.point === undefined
    ? null
    : readPoint(record, "point", "evidence");
}

function readOptionalVerdict(record: JsonRecord): Verdict | null {
  return record.verdict === null || record.verdict === undefined
    ? null
    : parseVerdict(record.verdict);
}

export function parseEvidence(value: unknown): Evidence {
  const record = readRecord(value, "evidence");
  return {
    id: readString(record, "id", "evidence"),
    task_id: readString(record, "task_id", "evidence"),
    case_id: readString(record, "case_id", "evidence"),
    kind: readOneOf(record, "kind", "evidence", EVIDENCE_KINDS),
    gcs_uri: readString(record, "gcs_uri", "evidence"),
    sha256: readString(record, "sha256", "evidence"),
    point: readOptionalPoint(record),
    captured_at: readNullable(record, "captured_at", "evidence", readString),
    verdict: readOptionalVerdict(record),
    location_ok: readNullable(record, "location_ok", "evidence", readBoolean),
    uploaded_by: readString(record, "uploaded_by", "evidence"),
    sample: readBoolean(record, "sample", "evidence"),
  };
}

export function parseTask(value: unknown): Task {
  const record = readRecord(value, "task");
  return {
    id: readString(record, "id", "task"),
    case_id: readString(record, "case_id", "task"),
    type: readOneOf(record, "type", "task", TASK_TYPES),
    assignee_id: readString(record, "assignee_id", "task"),
    target: readPoint(record, "target", "task"),
    deadline_at: readString(record, "deadline_at", "task"),
    status: readOneOf(record, "status", "task", TASK_STATUSES),
    cloud_task_name: readNullable(record, "cloud_task_name", "task", readString),
    attempt: readNumber(record, "attempt", "task"),
    created_at: readString(record, "created_at", "task"),
    done_at: readNullable(record, "done_at", "task", readString),
  };
}

function readOptionalCaseId(record: JsonRecord): string | null {
  return record.case_id === null || record.case_id === undefined
    ? null
    : readString(record, "case_id", "message");
}

export function parseMessage(value: unknown): Message {
  const record = readRecord(value, "message");
  return {
    id: readString(record, "id", "message"),
    thread: readOneOf(record, "thread", "message", THREADS),
    to_id: readString(record, "to_id", "message"),
    case_id: readOptionalCaseId(record),
    lang: readString(record, "lang", "message"),
    text: readString(record, "text", "message"),
    text_en: readString(record, "text_en", "message"),
    channel: readOneOf(record, "channel", "message", CHANNELS),
    created_at: readString(record, "created_at", "message"),
    delivered: readBoolean(record, "delivered", "message"),
  };
}
