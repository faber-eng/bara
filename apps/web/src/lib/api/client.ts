import { getIdToken } from "../auth";
import { roleHeaderValue } from "../judge/store";
import { isRealUser, readTokenIdentity, type TokenIdentity } from "../tokenIdentity";
import { readRecord } from "./parse";

const DEFAULT_TIMEOUT_MS = 10_000;
const ROLE_HEADER = "X-Bara-Role";

export class ApiError extends Error {
  override name = "ApiError";
  readonly status: number;
  readonly detail: string | null;

  constructor(message: string, status: number, detail: string | null = null) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export function isNotFoundError(error: Error | null): boolean {
  return error instanceof ApiError && error.status === 404;
}

export type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
  anonymous?: boolean;
};

const BRIGADE_PATH = "/api/brigade/";
const BRIGADE_ROLE = "brigade";
const VOLUNTEER_PATH = "/api/v/";
const VOLUNTEER_ROLE = "volunteer";
const JUDGE_PATH = "/api/judge/";
const JUDGE_ROLE = "judge";

function isOwnLivePath(path: string, identity: TokenIdentity): boolean {
  return (
    path === "/api/join" ||
    path.startsWith(`${VOLUNTEER_PATH}${identity.uid}/`) ||
    path.startsWith(`${BRIGADE_PATH}${identity.uid}/`) ||
    path.startsWith(`${BRIGADE_PATH}escalations/`)
  );
}

function roleForPath(path: string): string | undefined {
  const role = roleHeaderValue();
  if (role === undefined) return undefined;
  if (path.startsWith(JUDGE_PATH)) return JUDGE_ROLE;
  if (path.startsWith(BRIGADE_PATH)) return BRIGADE_ROLE;
  if (path.startsWith(VOLUNTEER_PATH)) return VOLUNTEER_ROLE;
  return role;
}

function shouldSendRole(path: string, identity: TokenIdentity | null): boolean {
  if (!isRealUser(identity)) return true;
  return !isOwnLivePath(path, identity);
}

export async function buildHeaders(path: string, hasBody: boolean): Promise<Headers> {
  const token = await getIdToken();
  const headers = new Headers({ Authorization: `Bearer ${token}` });
  const role = roleForPath(path);
  if (role !== undefined && shouldSendRole(path, readTokenIdentity(token))) {
    headers.set(ROLE_HEADER, role);
  }
  if (hasBody) headers.set("Content-Type", "application/json");
  return headers;
}

async function send(path: string, options: RequestOptions, signal: AbortSignal): Promise<Response> {
  const hasBody = options.body !== undefined;
  return fetch(path, {
    method: options.method ?? "GET",
    headers: options.anonymous ? new Headers() : await buildHeaders(path, hasBody),
    body: hasBody ? JSON.stringify(options.body) : undefined,
    signal,
  });
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const detail = readRecord(await response.json(), "error").detail;
    return typeof detail === "string" ? detail : null;
  } catch {
    return null;
  }
}

async function failureFrom(response: Response, path: string, method: string): Promise<ApiError> {
  const detail = await readDetail(response);
  return new ApiError(`${method} ${path} returned ${response.status}`, response.status, detail);
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  return text === "" ? null : JSON.parse(text);
}

export async function apiRequest(path: string, options: RequestOptions = {}): Promise<unknown> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timer = setTimeout(abort, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  try {
    const response = await send(path, options, controller.signal);
    if (!response.ok) throw await failureFrom(response, path, options.method ?? "GET");
    return await readBody(response);
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}
