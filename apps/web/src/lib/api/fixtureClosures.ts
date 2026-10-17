import type { Case } from "../contracts";

const FIXTURE_CLOSER = "ops";

const closedAtById = new Map<string, string>();

export function recordFixtureClosure(caseId: string, closedAt: string): void {
  closedAtById.set(caseId, closedAt);
}

export function clearFixtureClosures(): void {
  closedAtById.clear();
}

export function applyFixtureClosure(record: Case): Case {
  const closedAt = closedAtById.get(record.id);
  if (closedAt === undefined) return record;
  return { ...record, status: "closed", closed_by: FIXTURE_CLOSER, closed_at: closedAt };
}
