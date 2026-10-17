import type { Escalation, TimelineEntry } from "../contracts";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import { isFixtureAcked, recordFixtureAck } from "./fixtureOverrides";
import { readArray, readNullable, readRecord, readString, readStringArray } from "./parse";

function parseTimelineEntry(value: unknown): TimelineEntry {
  const record = readRecord(value, "timeline entry");
  return {
    at: readString(record, "at", "timeline entry"),
    text: readString(record, "text", "timeline entry"),
  };
}

function parseEscalation(value: unknown): Escalation {
  const record = readRecord(value, "escalation");
  const pack = readRecord(record.pack, "escalation.pack");
  return {
    id: readString(record, "id", "escalation"),
    case_id: readString(record, "case_id", "escalation"),
    contact_id: readString(record, "contact_id", "escalation"),
    brief_id: readString(record, "brief_id", "escalation"),
    brief_en: readString(record, "brief_en", "escalation"),
    pack: {
      photos: readStringArray(pack, "photos", "escalation.pack"),
      map_url: readString(pack, "map_url", "escalation.pack"),
      timeline: readArray(pack.timeline, "escalation.pack.timeline").map(parseTimelineEntry),
    },
    created_at: readString(record, "created_at", "escalation"),
    acknowledged_at: readNullable(record, "acknowledged_at", "escalation", readString),
  };
}

export function parseEscalations(body: unknown): Escalation[] {
  return readArray(body, "escalations").map(parseEscalation);
}

function isOpen(escalation: Escalation): boolean {
  return escalation.acknowledged_at === null;
}

async function fetchFixtureInbox(): Promise<Escalation[]> {
  const all = parseEscalations([(await import("@fixtures/escalation.json")).default]);
  return all.filter((escalation) => !isFixtureAcked(escalation.id));
}

async function fetchLiveInbox(contactId: string, signal?: AbortSignal): Promise<Escalation[]> {
  const path = `/api/brigade/${encodeURIComponent(contactId)}/inbox`;
  return parseEscalations(await apiRequest(path, { signal }));
}

export async function fetchBrigadeInbox(
  contactId: string,
  signal?: AbortSignal,
): Promise<Escalation[]> {
  const all =
    sourceFor("escalations") === "fixture"
      ? await fetchFixtureInbox()
      : await fetchLiveInbox(contactId, signal);
  return all.filter(isOpen);
}

async function ackFixture(escalationId: string): Promise<void> {
  const target = (await fetchFixtureInbox()).find((escalation) => escalation.id === escalationId);
  if (target === undefined) return;
  recordFixtureAck(target.id, target.case_id);
}

export async function ackEscalation(escalationId: string): Promise<void> {
  if (sourceFor("escalations") === "fixture") return ackFixture(escalationId);
  await apiRequest(`/api/brigade/escalations/${encodeURIComponent(escalationId)}/ack`, {
    method: "POST",
  });
}
