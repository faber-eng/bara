import { completeUpload, requestUpload } from "../api/volunteer";
import type { Evidence, EvidenceKind, GeoPoint, UploadTicket } from "../contracts";
import { putFile, UploadTransferError } from "./putFile";

export const TICKET_LIFE_MS = 14 * 60_000;

export type IssuedTicket = { ticket: UploadTicket; issuedAt: number };

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
  const issued = { ticket, issuedAt: Date.now() };
  input.onTicket(issued);
  return issued;
}

function isExpiredAnswer(error: unknown): boolean {
  return error instanceof UploadTransferError && error.status === 403;
}

function putWith(input: UploadInput, ticket: UploadTicket): Promise<void> {
  return putFile({
    url: ticket.upload_url,
    blob: input.blob,
    headers: ticket.headers,
    onProgress: input.onProgress,
  });
}

async function putReusingWhenFresh(input: UploadInput): Promise<UploadTicket> {
  const reused = input.ticket !== null && isFresh(input.ticket) ? input.ticket : null;
  if (reused === null) {
    const issued = await issueTicket(input);
    await putWith(input, issued.ticket);
    return issued.ticket;
  }
  try {
    await putWith(input, reused.ticket);
    return reused.ticket;
  } catch (error) {
    if (!isExpiredAnswer(error)) throw error;
  }
  const renewed = await issueTicket(input);
  await putWith(input, renewed.ticket);
  return renewed.ticket;
}

export async function uploadEvidence(input: UploadInput): Promise<UploadResult> {
  const ticket = await putReusingWhenFresh(input);
  const evidence = await completeUpload(input.volunteerId, ticket.evidence_id, {
    point: input.point,
    captured_at: new Date().toISOString(),
  });
  return { evidenceId: ticket.evidence_id, evidence };
}
