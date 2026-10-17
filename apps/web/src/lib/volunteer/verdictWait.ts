import type { Evidence } from "../contracts";

export const VERDICT_POLL_MS = 2_000;
export const VERDICT_POLL_LIMIT = 15;

export type VerdictWaitInput = {
  evidenceId: string;
  readEvidence: () => Promise<Evidence[]>;
  wait: (ms: number) => Promise<void>;
  attempts?: number;
  isCancelled?: () => boolean;
};

function judged(
  evidence: Evidence | undefined,
): evidence is Evidence & { verdict: NonNullable<Evidence["verdict"]> } {
  return evidence !== undefined && evidence.verdict !== null;
}

export async function waitForVerdict(input: VerdictWaitInput): Promise<Evidence | null> {
  const attempts = input.attempts ?? VERDICT_POLL_LIMIT;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (input.isCancelled?.()) return null;
    const found = (await input.readEvidence()).find((item) => item.id === input.evidenceId);
    if (judged(found)) return found;
    await input.wait(VERDICT_POLL_MS);
  }
  return null;
}
