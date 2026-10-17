import { completeUpload, requestUpload } from "../api/volunteer";
import type { Evidence, EvidenceKind, GeoPoint, UploadTicket } from "../contracts";
import { putFile, UploadTransferError } from "./putFile";

export const TICKET_LIFE_MS = 14 * 60_000;

export type IssuedTicket = { ticket: UploadTicket; issuedAt: number; uploaded: boolean };

export type UploadInput = {
  volunteerId: string;
  taskId: string;
  kind: EvidenceKind;
  blob: Blob;
  contentType: string;
  sample: boolean;
  point: GeoPoint | null;
  ticket: IssuedTicket | null;
  onTicket: (issued: IssuedTicket) => void;
  onProgress: (fraction: number) => void;
};

export type UploadResult = { evidenceId: string; evidence: Evidence | null };

function isFresh(issued: IssuedTicket): boolean {
  return Date.now() - issued.issuedAt < TICKET_LIFE_MS;
}

async function issueTicket(input: UploadInput): Promise<IssuedTicket> {
  const ticket = await requestUpload(input.volunteerId, {
    task_id: input.taskId,
    kind: input.kind,
    content_type: input.contentType,
    size_bytes: input.blob.size,
    sample: input.sample,
  });
  const issued = { ticket, issuedAt: Date.now(), uploaded: false };
  input.onTicket(issued);
  return issued;
}

function isExpiredAnswer(error: unknown): boolean {
  return error instanceof UploadTransferError && (error.status === 400 || error.status === 403);
}

function putWith(input: UploadInput, ticket: UploadTicket): Promise<void> {
  return putFile({
    url: ticket.upload_url,
    blob: input.blob,
    headers: ticket.headers,
    onProgress: input.onProgress,
  });
}

async function putAndMark(input: UploadInput, issued: IssuedTicket): Promise<UploadTicket> {
  await putWith(input, issued.ticket);
  input.onTicket({ ...issued, uploaded: true });
  return issued.ticket;
}

async function putReusingWhenFresh(input: UploadInput): Promise<UploadTicket> {
  const reused = input.ticket !== null && isFresh(input.ticket) ? input.ticket : null;
  if (reused === null) return putAndMark(input, await issueTicket(input));
  try {
    return await putAndMark(input, reused);
  } catch (error) {
    if (!isExpiredAnswer(error)) throw error;
  }
  return putAndMark(input, await issueTicket(input));
}

async function ticketReadyToComplete(input: UploadInput): Promise<UploadTicket> {
  if (input.ticket?.uploaded) return input.ticket.ticket;
  return putReusingWhenFresh(input);
}

export async function uploadEvidence(input: UploadInput): Promise<UploadResult> {
  const ticket = await ticketReadyToComplete(input);
  const evidence = await completeUpload(input.volunteerId, ticket.evidence_id, {
    point: input.point,
    captured_at: new Date().toISOString(),
  });
  return { evidenceId: ticket.evidence_id, evidence };
}
