import { apiRequest } from "./client";
import { readRecord, readString } from "./parse";

export type SendResult = { cell_id: string; message_id: string };

export function sendPath(cellId: string): string {
  return `/api/ops/cells/${encodeURIComponent(cellId)}/send`;
}

export async function sendSomeone(cellId: string): Promise<SendResult> {
  const body = readRecord(await apiRequest(sendPath(cellId), { method: "POST" }), "send");
  return {
    cell_id: readString(body, "cell_id", "send"),
    message_id: readString(body, "message_id", "send"),
  };
}
