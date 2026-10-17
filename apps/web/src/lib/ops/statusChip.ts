import type { CaseStatus } from "../contracts";

export type StatusChip = { className: string; label: string };

const STATUS_CHIPS = {
  open: { className: "chip-open", label: "Open" },
  assigned: { className: "chip-assigned", label: "Assigned" },
  reviewing: { className: "chip-reviewing", label: "Reviewing" },
  resolved_pending_human: { className: "chip-resolved", label: "Resolved, pending human" },
  human_review: { className: "chip-human-review", label: "Human review" },
  overdue: { className: "chip-overdue", label: "Overdue" },
  escalated: { className: "chip-escalated", label: "Escalated" },
  monitoring: { className: "chip-monitoring", label: "Monitoring" },
  closed: { className: "chip-closed", label: "Closed" },
} as const satisfies Record<CaseStatus, StatusChip>;

export function statusChip(status: CaseStatus): StatusChip {
  return STATUS_CHIPS[status];
}
