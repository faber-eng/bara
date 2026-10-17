import { ApiError } from "../api/client";

export type AreaErrorKind =
  | "limit"
  | "too_large"
  | "outside"
  | "invalid"
  | "busy"
  | "timeout"
  | "failed";

function kindForDetail(detail: string | null): AreaErrorKind {
  if (detail === "area_too_large") return "too_large";
  if (detail === "outside_regions") return "outside";
  if (detail?.startsWith("invalid_polygon")) return "invalid";
  return "failed";
}

function kindForStatus(error: ApiError): AreaErrorKind {
  if (error.status === 429) return "limit";
  if (error.status === 503) return "busy";
  if (error.status === 504) return "timeout";
  if (error.status === 422) return kindForDetail(error.detail);
  return "failed";
}

export function areaErrorKind(error: unknown): AreaErrorKind {
  if (error instanceof ApiError) return kindForStatus(error);
  if (error instanceof DOMException && error.name === "AbortError") return "timeout";
  return "failed";
}
