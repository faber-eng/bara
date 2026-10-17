import { ApiError } from "../api/client";

export type JoinFailure =
  | "wrong_code"
  | "too_many_attempts"
  | "already_has_role"
  | "not_signed_in"
  | "unavailable"
  | "network"
  | "unknown";

function failureForStatus(error: ApiError): JoinFailure {
  if (error.status === 403 && error.detail === "invalid_invite_code") return "wrong_code";
  if (error.status === 403 && error.detail === "anonymous_not_allowed") return "not_signed_in";
  if (error.status === 409 && error.detail === "already_has_role") return "already_has_role";
  if (error.status === 401) return "not_signed_in";
  if (error.status === 429) return "too_many_attempts";
  if (error.status === 502 || error.status === 503) return "unavailable";
  return "unknown";
}

export function classifyJoinError(error: unknown): JoinFailure {
  if (error instanceof ApiError) return failureForStatus(error);
  if (error instanceof Error) return "network";
  return "unknown";
}
