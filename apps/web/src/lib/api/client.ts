import { getIdToken } from "../auth";
import { roleHeaderValue } from "../judge/store";

const DEFAULT_TIMEOUT_MS = 10_000;
const ROLE_HEADER = "X-Bara-Role";

export class ApiError extends Error {
  override name = "ApiError";
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
};

async function buildHeaders(hasBody: boolean): Promise<Headers> {
  const headers = new Headers({ Authorization: `Bearer ${await getIdToken()}` });
  const role = roleHeaderValue();
  if (role !== undefined) headers.set(ROLE_HEADER, role);
  if (hasBody) headers.set("Content-Type", "application/json");
  return headers;
}

async function send(path: string, options: RequestOptions, signal: AbortSignal): Promise<Response> {
  const hasBody = options.body !== undefined;
  return fetch(path, {
    method: options.method ?? "GET",
    headers: await buildHeaders(hasBody),
    body: hasBody ? JSON.stringify(options.body) : undefined,
    signal,
  });
}

export async function apiRequest(path: string, options: RequestOptions = {}): Promise<unknown> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timer = setTimeout(abort, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  try {
    const response = await send(path, options, controller.signal);
    if (!response.ok) {
      const method = options.method ?? "GET";
      throw new ApiError(`${method} ${path} returned ${response.status}`, response.status);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}
