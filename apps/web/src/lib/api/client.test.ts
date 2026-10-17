import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { selectPerson, setJudgeMode } from "../judge/store";
import { ApiError, apiRequest } from "./client";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

function stubFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentHeaders(fetchMock: ReturnType<typeof vi.fn>): Headers {
  const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
  return new Headers(init.headers);
}

describe("apiRequest", () => {
  beforeEach(() => {
    setJudgeMode(false);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the Bearer token and returns the parsed body", async () => {
    const fetchMock = stubFetch(Response.json({ ok: true }));

    const body = await apiRequest("/api/clock");

    expect(body).toEqual({ ok: true });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/clock");
    expect(sentHeaders(fetchMock).get("Authorization")).toBe("Bearer token-1");
  });

  it("sends no role header with judge mode off", async () => {
    const fetchMock = stubFetch(Response.json({}));

    await apiRequest("/api/cases");

    expect(sentHeaders(fetchMock).has("X-Bara-Role")).toBe(false);
  });

  it("sends the role of the selected person in judge mode", async () => {
    setJudgeMode(true);
    selectPerson("vol-ari");
    const fetchMock = stubFetch(Response.json({}));

    await apiRequest("/api/cases");

    expect(sentHeaders(fetchMock).get("X-Bara-Role")).toBe("volunteer");
  });

  it("reads the role again on every call", async () => {
    setJudgeMode(true);
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(Response.json({})));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/cases");
    selectPerson("contact-daops-pekanbaru");
    await apiRequest("/api/cases");

    const roles = fetchMock.mock.calls.map(([, init]) =>
      new Headers((init as RequestInit).headers).get("X-Bara-Role"),
    );
    expect(roles).toEqual(["ops", "brigade"]);
  });

  it("posts a JSON body", async () => {
    const fetchMock = stubFetch(Response.json({}));

    await apiRequest("/api/judge/advance", { method: "POST", body: { hours: 48 } });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"hours":48}');
    expect(sentHeaders(fetchMock).get("Content-Type")).toBe("application/json");
  });

  it("throws an ApiError carrying the status", async () => {
    stubFetch(new Response("no", { status: 429 }));

    const failure = await apiRequest("/api/judge/reset", { method: "POST" }).catch(
      (error: unknown) => error,
    );

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(429);
  });

  it("aborts when the caller signal aborts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(
        (_path: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("a", "AbortError")),
            );
          }),
      ),
    );
    const controller = new AbortController();

    const pending = apiRequest("/api/cases", { signal: controller.signal });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
    controller.abort();

    await expect(pending).rejects.toThrow();
  });

  it("aborts after the timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(
        (_path: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("t", "AbortError")),
            );
          }),
      ),
    );

    const pending = apiRequest("/api/cases", { timeoutMs: 5000 });
    const assertion = expect(pending).rejects.toThrow();
    await vi.advanceTimersByTimeAsync(5001);
    await assertion;
    vi.useRealTimers();
  });
});

function jwt(payload: object): string {
  return `h.${btoa(JSON.stringify(payload))}.s`;
}

describe("apiRequest for a signed-in user", () => {
  beforeEach(() => {
    setJudgeMode(true);
    selectPerson("ops");
  });

  afterEach(() => {
    setJudgeMode(false);
    vi.unstubAllGlobals();
  });

  async function authWithToken(token: string) {
    const auth = await import("../auth");
    vi.mocked(auth.getIdToken).mockResolvedValue(token);
  }

  it("keeps the role header off /api/join and the user's own volunteer routes", async () => {
    await authWithToken(jwt({ sub: "u-9", firebase: { sign_in_provider: "google.com" } }));
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(Response.json({})));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/join", { method: "POST", body: {} });
    await apiRequest("/api/v/u-9/inbox");

    for (const call of fetchMock.mock.calls) {
      expect(new Headers((call[1] as RequestInit).headers).has("X-Bara-Role")).toBe(false);
    }
  });

  it("still sends the role header for a signed-in user on other routes", async () => {
    await authWithToken(jwt({ sub: "u-9", firebase: { sign_in_provider: "google.com" } }));
    const fetchMock = stubFetch(Response.json({}));

    await apiRequest("/api/v/vol-ari/inbox");

    expect(sentHeaders(fetchMock).get("X-Bara-Role")).toBe("ops");
  });

  it("keeps the role header for an anonymous user", async () => {
    await authWithToken(jwt({ sub: "u-9", firebase: { sign_in_provider: "anonymous" } }));
    const fetchMock = stubFetch(Response.json({}));

    await apiRequest("/api/v/u-9/inbox");

    expect(sentHeaders(fetchMock).get("X-Bara-Role")).toBe("ops");
  });
});

describe("apiRequest failures", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("carries the detail string of the error body", async () => {
    stubFetch(Response.json({ detail: "invalid_invite_code" }, { status: 403 }));

    const error = await apiRequest("/api/join").catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, detail: "invalid_invite_code" });
  });

  it("has a null detail when the body is not JSON", async () => {
    stubFetch(new Response("boom", { status: 500 }));

    const error = await apiRequest("/api/join").catch((caught: unknown) => caught);

    expect(error).toMatchObject({ status: 500, detail: null });
  });
});
