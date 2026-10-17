import type { Evidence, EvidenceKind, GeoPoint, IsoDateTime, Message, Task } from "../contracts";

export type Inbox = { tasks: Task[]; messages: Message[]; evidence: Evidence[] };

export type UploadRequest = {
  task_id: string;
  kind: EvidenceKind;
  content_type: string;
  size_bytes: number;
  sample: boolean;
};

export type UploadTicket = { evidence_id: string; upload_url: string };

export type CompleteRequest = { point: GeoPoint | null; captured_at: IsoDateTime };

export type ChatRequest = { text: string };
