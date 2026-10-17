import type { StreamEvent } from "../api/caseStream";
import type { CaseDetail } from "../contracts";

export const POLL_INTERVAL_MS = 3_000;
export const MAX_POLLS = 60;
const REFRESH_EVENTS = ["tool", "final"];

export function runIsFinal(detail: CaseDetail): boolean {
  const latest = detail.agent_runs.at(-1);
  return latest !== undefined && latest.status !== "running";
}

export type FollowDeps = {
  stream: (onEvent: (event: StreamEvent) => void) => Promise<void>;
  refresh: () => Promise<CaseDetail>;
  signal: AbortSignal;
  sleep: (ms: number) => Promise<void>;
};

async function pollUntilFinal(deps: FollowDeps): Promise<void> {
  for (let poll = 0; poll < MAX_POLLS; poll += 1) {
    await deps.sleep(POLL_INTERVAL_MS);
    if (deps.signal.aborted) return;
    try {
      if (runIsFinal(await deps.refresh())) return;
    } catch {}
  }
}

export async function followCase(deps: FollowDeps): Promise<void> {
  try {
    await deps.stream((event) => {
      if (REFRESH_EVENTS.includes(event.name)) void deps.refresh().catch(() => undefined);
    });
  } catch {
    if (deps.signal.aborted) return;
    await pollUntilFinal(deps);
  }
}
