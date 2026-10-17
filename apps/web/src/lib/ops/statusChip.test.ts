import { describe, expect, it } from "vitest";
import type { CaseStatus } from "../contracts";
import { statusChip } from "./statusChip";

const CASES: [CaseStatus, string, string][] = [
  ["open", "chip-open", "Open"],
  ["assigned", "chip-assigned", "Assigned"],
  ["reviewing", "chip-reviewing", "Reviewing"],
  ["resolved_pending_human", "chip-resolved", "Resolved, pending human"],
  ["human_review", "chip-human-review", "Human review"],
  ["overdue", "chip-overdue", "Overdue"],
  ["escalated", "chip-escalated", "Escalated"],
  ["monitoring", "chip-monitoring", "Monitoring"],
  ["closed", "chip-closed", "Closed"],
];

describe("statusChip", () => {
  it.each(CASES)("maps %s to %s", (status, className, label) => {
    expect(statusChip(status)).toEqual({ className, label });
  });
});
