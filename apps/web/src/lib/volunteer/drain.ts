import { ApiError } from "../api/client";
import { listOutboxItems, type OutboxItem, removeOutboxItem, saveOutboxTicket } from "./outbox";
import { UploadTransferError } from "./putFile";
import { uploadEvidence } from "./upload";

const LOCK_NAME = "bara-outbox";
const RETRYABLE_STATUSES = [408, 429];

export type DrainResult = { sent: number; dropped: number; waiting: number };

type Uploader = typeof uploadEvidence;

export function isPermanentFailure(error: unknown): boolean {
  if (!(error instanceof ApiError || error instanceof UploadTransferError)) return false;
  const status = error.status;
  if (status === null) return false;
  return status >= 400 && status < 500 && !RETRYABLE_STATUSES.includes(status);
}

async function uploadOne(item: OutboxItem, upload: Uploader) {
  let saving: Promise<void> = Promise.resolve();
  try {
    await upload({
      volunteerId: item.volunteerId,
      taskId: item.taskId,
      kind: item.kind,
      blob: item.blob,
      contentType: item.contentType,
      sample: item.sample,
      point: item.point,
      ticket: item.ticket,
      onTicket: (issued) => {
        saving = saving.then(() => saveOutboxTicket(item.id, issued)).catch(() => undefined);
      },
      onProgress: () => undefined,
    });
  } finally {
    await saving;
  }
}

async function drainNow(volunteerId: string, upload: Uploader): Promise<DrainResult> {
  const items = await listOutboxItems(volunteerId);
  let sent = 0;
  let dropped = 0;
  for (const item of items) {
    try {
      await uploadOne(item, upload);
      await removeOutboxItem(item.id);
      sent += 1;
    } catch (error) {
      if (!isPermanentFailure(error)) break;
      await removeOutboxItem(item.id);
      dropped += 1;
    }
  }
  return { sent, dropped, waiting: items.length - sent - dropped };
}

export async function drainOutbox(
  volunteerId: string,
  upload: Uploader = uploadEvidence,
): Promise<DrainResult> {
  const locks: LockManager | null = navigator.locks ?? null;
  if (locks === null) return drainNow(volunteerId, upload);
  return locks.request(LOCK_NAME, () => drainNow(volunteerId, upload));
}
