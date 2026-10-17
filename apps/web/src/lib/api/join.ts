import type { JoinRequest, JoinResponse } from "../contracts";
import { apiRequest } from "./client";
import { readBoolean, readRecord, readString } from "./parse";

export function parseJoinResponse(body: unknown): JoinResponse {
  const record = readRecord(body, "join response");
  return {
    volunteer_id: readString(record, "volunteer_id", "join response"),
    created: readBoolean(record, "created", "join response"),
  };
}

export async function postJoin(request: JoinRequest, signal?: AbortSignal): Promise<JoinResponse> {
  return parseJoinResponse(
    await apiRequest("/api/join", { method: "POST", body: request, signal }),
  );
}
