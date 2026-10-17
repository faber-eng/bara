import { postJoin } from "../api/join";
import { refreshIdToken } from "../auth";
import type { JoinRequest, JoinResponse } from "../contracts";

export async function submitJoin(request: JoinRequest): Promise<JoinResponse> {
  const response = await postJoin(request);
  await refreshIdToken();
  return response;
}
