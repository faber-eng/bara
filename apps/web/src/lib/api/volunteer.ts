import type { CompleteRequest, Evidence, Inbox, UploadRequest, UploadTicket } from "../contracts";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import { ResponseShapeError, readArray, readRecord, readString, readStringRecord } from "./parse";
import { parseEvidence, parseHome, parseMessage, parseTask } from "./volunteerParse";
import type { ChatRequest } from "./volunteerTypes";

const COMPLETE_TIMEOUT_MS = 30_000;

function readEvidenceList(value: unknown): Evidence[] {
  if (value === undefined || value === null) return [];
  return readArray(value, "inbox.evidence").map(parseEvidence);
}

function readStringList(value: unknown): string[] {
  if (value === undefined || value === null) return [];
  return readArray(value, "inbox.area_case_ids").map((item) => String(item));
}

export function parseInbox(body: unknown): Inbox {
  const record = readRecord(body, "inbox");
  return {
    tasks: readArray(record.tasks, "inbox.tasks").map(parseTask),
    messages: readArray(record.messages, "inbox.messages").map(parseMessage),
    evidence: readEvidenceList(record.evidence),
    area_case_ids: readStringList(record.area_case_ids),
    ...parseHome(record),
  };
}

export function parseEvidenceOrNull(body: unknown): Evidence | null {
  try {
    return parseEvidence(body);
  } catch (error) {
    if (error instanceof ResponseShapeError) return null;
    throw error;
  }
}

export function parseUploadTicket(body: unknown): UploadTicket {
  const record = readRecord(body, "upload ticket");
  return {
    evidence_id: readString(record, "evidence_id", "upload ticket"),
    upload_url: readString(record, "upload_url", "upload ticket"),
    headers: readStringRecord(record, "headers", "upload ticket"),
  };
}

async function fetchFixtureInbox(): Promise<Inbox> {
  return parseInbox((await import("./inboxFixture.json")).default);
}

export async function fetchInbox(volunteerId: string, signal?: AbortSignal): Promise<Inbox> {
  if (sourceFor("inbox") === "fixture") return fetchFixtureInbox();
  return parseInbox(
    await apiRequest(`/api/v/${encodeURIComponent(volunteerId)}/inbox`, { signal }),
  );
}

export async function requestUpload(
  volunteerId: string,
  request: UploadRequest,
  signal?: AbortSignal,
): Promise<UploadTicket> {
  const path = `/api/v/${encodeURIComponent(volunteerId)}/uploads`;
  return parseUploadTicket(await apiRequest(path, { method: "POST", body: request, signal }));
}

export async function completeUpload(
  volunteerId: string,
  evidenceId: string,
  request: CompleteRequest,
  signal?: AbortSignal,
): Promise<Evidence | null> {
  const path = `/api/v/${encodeURIComponent(volunteerId)}/evidence/${encodeURIComponent(evidenceId)}/complete`;
  const body = await apiRequest(path, {
    method: "POST",
    body: request,
    signal,
    timeoutMs: COMPLETE_TIMEOUT_MS,
  });
  return parseEvidenceOrNull(body);
}

export async function sendChat(
  volunteerId: string,
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<void> {
  const path = `/api/v/${encodeURIComponent(volunteerId)}/chat`;
  await apiRequest(path, { method: "POST", body: request, signal, timeoutMs: COMPLETE_TIMEOUT_MS });
}
