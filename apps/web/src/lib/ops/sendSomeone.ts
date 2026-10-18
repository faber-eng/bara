import { ApiError } from "../api/client";

export type SendFailure =
  | { kind: "case_open" }
  | { kind: "no_flow" }
  | { kind: "rate_limited"; detail: string }
  | { kind: "failed" };

const STATUS_CONFLICT = 409;
const STATUS_RATE_LIMITED = 429;
const FAILED: SendFailure = { kind: "failed" };

function conflictFailure(detail: string | null): SendFailure {
  if (detail === "case_open") return { kind: "case_open" };
  if (detail === "region_without_flow") return { kind: "no_flow" };
  return FAILED;
}

export function sendFailure(error: unknown): SendFailure {
  if (!(error instanceof ApiError)) return FAILED;
  if (error.status === STATUS_CONFLICT) return conflictFailure(error.detail);
  if (error.status === STATUS_RATE_LIMITED && error.detail !== null) {
    return { kind: "rate_limited", detail: error.detail };
  }
  return FAILED;
}
