import type { CaseStatus, JsonValue } from "../contracts";

const CLOSABLE_STATUSES: readonly CaseStatus[] = ["resolved_pending_human", "human_review"];
const PERCENT = 100;

export function canCloseCase(status: CaseStatus): boolean {
  return CLOSABLE_STATUSES.includes(status);
}

export function evidenceImageUrl(uri: string): string | null {
  return uri.startsWith("https://") ? uri : null;
}

export function confidenceLabel(confidence: number): string {
  return `${Math.round(confidence * PERCENT)}%`;
}

export function toolCallArgs(args: { [key: string]: JsonValue }): string {
  return Object.entries(args)
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
    .join(", ");
}

export function spaced(value: string): string {
  return value.replaceAll("_", " ");
}
