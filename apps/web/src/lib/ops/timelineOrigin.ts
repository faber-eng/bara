import type { CaseDetail, TimelineEntry } from "../contracts";

export const RULE_ESCALATION_LABEL = "Escalated by overdue rule";

const ESCALATION_PREFIX = "Escalated to brigade";
const REVIEW_NOTE_PREFIX = "Review note:";
const ESCALATE_TOOL = "escalate";

type DetailForOrigin = Pick<CaseDetail, "timeline" | "agent_runs" | "tasks">;

function isEscalationEntry(entry: TimelineEntry): boolean {
  return entry.text.startsWith(ESCALATION_PREFIX);
}

function agentEscalated(detail: DetailForOrigin): boolean {
  return detail.agent_runs.some((run) =>
    run.tool_calls.some((call) => call.name === ESCALATE_TOOL),
  );
}

function hasReviewNote(detail: DetailForOrigin): boolean {
  return detail.timeline.some((entry) => entry.text.startsWith(REVIEW_NOTE_PREFIX));
}

function hadOverdueTask(detail: DetailForOrigin): boolean {
  return detail.tasks.some((task) => task.status === "overdue");
}

export function ruleEscalationEntries(detail: DetailForOrigin): ReadonlySet<TimelineEntry> {
  const made = hadOverdueTask(detail) && !agentEscalated(detail) && !hasReviewNote(detail);
  if (!made) return new Set();
  return new Set(detail.timeline.filter(isEscalationEntry));
}
