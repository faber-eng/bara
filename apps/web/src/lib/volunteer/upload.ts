import { completeUpload, requestUpload } from "../api/volunteer";
import type { Evidence, EvidenceKind, GeoPoint, UploadTicket } from "../contracts";
import { putFile } from "./putFile";

export type UploadInput = {
  volunteerId: string;
  taskId: string;
  kind: EvidenceKind;
  blob: Blob;
  contentType: string;
  sample: boolean;
  point: GeoPoint | null;
  ticket: UploadTicket | null;
  onTicket: (ticket: UploadTicket) => void;
  onProgress: (fraction: number) => void;
};

export type UploadResult = { evidenceId: string; evidence: Evidence | null };

async function ticketFor(input: UploadInput): Promise<UploadTicket> {
  if (input.ticket !== null) return input.ticket;
  const ticket = await requestUpload(input.volunteerId, {
    task_id: input.taskId,
    kind: input.kind,
    content_type: input.contentType,
    size_bytes: input.blob.size,
    sample: input.sample,
  });
  input.onTicket(ticket);
  return ticket;
}

export async function uploadEvidence(input: UploadInput): Promise<UploadResult> {
  const ticket = await ticketFor(input);
  await putFile({
    url: ticket.upload_url,
    blob: input.blob,
    headers: ticket.headers,
    onProgress: input.onProgress,
  });
  const evidence = await completeUpload(input.volunteerId, ticket.evidence_id, {
    point: input.point,
    captured_at: new Date().toISOString(),
  });
  return { evidenceId: ticket.evidence_id, evidence };
}
