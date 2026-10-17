import type { Health } from "./contracts";

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

async function fetchWithTimeout(path: string, signal: AbortSignal | undefined): Promise<Response> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timer = setTimeout(abort, HEALTH_TIMEOUT_MS);
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  try {
    return await fetch(path, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetchWithTimeout(HEALTH_PATH, signal);
  if (!response.ok) throw new HealthResponseError(`GET ${HEALTH_PATH} returned ${response.status}`);
  return parseHealth(await response.json());
}
