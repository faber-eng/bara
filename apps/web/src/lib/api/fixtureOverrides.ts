import type { Case } from "../contracts";

const FIXTURE_CLOSER = "ops";

const closedAtById = new Map<string, string>();
const monitoringIds = new Set<string>();
const ackedEscalationIds = new Set<string>();

export function recordFixtureClosure(caseId: string, closedAt: string): void {
  closedAtById.set(caseId, closedAt);
}

export function recordFixtureAck(escalationId: string, caseId: string): void {
  ackedEscalationIds.add(escalationId);
  monitoringIds.add(caseId);
}

export function isFixtureAcked(escalationId: string): boolean {
  return ackedEscalationIds.has(escalationId);
}

export function clearFixtureOverrides(): void {
  closedAtById.clear();
  monitoringIds.clear();
  ackedEscalationIds.clear();
}

export function applyFixtureOverrides(record: Case): Case {
  const closedAt = closedAtById.get(record.id);
  if (closedAt !== undefined) {
    return { ...record, status: "closed", closed_by: FIXTURE_CLOSER, closed_at: closedAt };
  }
  if (monitoringIds.has(record.id)) return { ...record, status: "monitoring" };
  return record;
}
