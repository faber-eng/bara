import type { Case, ReviewRequest } from "../contracts";
import { sourceFor } from "../sources";
import { parseCase } from "./cases";
import { apiRequest } from "./client";

const REVIEW_TIMEOUT_MS = 90_000;
export const REVIEW_NOTE_MAX = 500;

export function reviewPath(caseId: string): string {
  return `/api/cases/${encodeURIComponent(caseId)}/review`;
}

export function trimmedNote(note: string): string {
  return note.trim();
}

export function isValidNote(note: string): boolean {
  const trimmed = trimmedNote(note);
  return trimmed.length > 0 && trimmed.length <= REVIEW_NOTE_MAX;
}

export async function reviewCase(caseId: string, request: ReviewRequest): Promise<Case | null> {
  if (sourceFor("caseDetail") === "fixture") return null;
  const body = { action: request.action, note: trimmedNote(request.note) };
  const response = await apiRequest(reviewPath(caseId), {
    method: "POST",
    body,
    timeoutMs: REVIEW_TIMEOUT_MS,
  });
  return parseCase(response);
}
