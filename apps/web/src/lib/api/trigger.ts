import { apiRequest } from "./client";

export type ScenarioEvent = "drying.ranked" | "fire.quiet";

const TRIGGER_PATH = "/api/judge/trigger";
const TRIGGER_TIMEOUT_MS = 20_000;

export async function triggerScenario(event: ScenarioEvent): Promise<void> {
  await apiRequest(TRIGGER_PATH, {
    method: "POST",
    body: { event },
    timeoutMs: TRIGGER_TIMEOUT_MS,
  });
}
