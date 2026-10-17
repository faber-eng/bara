export type Health = {
  status: string;
  models: { reasoning: string; fast: string };
  fallback_used: boolean;
  git_sha: string;
};

const HEALTH_PATH = "/api/health";
const HEALTH_TIMEOUT_MS = 5_000;

export class HealthResponseError extends Error {
  override name = "HealthResponseError";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  if (typeof value !== "string") throw new HealthResponseError(`health.${key} is not a string`);
  return value;
}

function readBoolean(record: Record<string, unknown>, key: string): boolean {
  const value = record[key];
  if (typeof value !== "boolean") throw new HealthResponseError(`health.${key} is not a boolean`);
  return value;
}

export function parseHealth(body: unknown): Health {
  if (!isRecord(body)) throw new HealthResponseError("health body is not an object");
  const models = body.models;
  if (!isRecord(models)) throw new HealthResponseError("health.models is not an object");
  return {
    status: readString(body, "status"),
    models: { reasoning: readString(models, "reasoning"), fast: readString(models, "fast") },
    fallback_used: readBoolean(body, "fallback_used"),
    git_sha: readString(body, "git_sha"),
  };
}

function withTimeout(signal: AbortSignal | undefined): AbortSignal {
  const timeout = AbortSignal.timeout(HEALTH_TIMEOUT_MS);
  if (signal === undefined) return timeout;
  return AbortSignal.any([signal, timeout]);
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch(HEALTH_PATH, { signal: withTimeout(signal) });
  if (!response.ok) throw new HealthResponseError(`GET ${HEALTH_PATH} returned ${response.status}`);
  return parseHealth(await response.json());
}
