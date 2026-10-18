import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchHealth, parseHealth } from "./health";

const validBody = {
  status: "ok",
  models: { reasoning: "gemini-3.8-flash", fast: "gemini-3.5-flash" },
  fallback_used: false,
  git_sha: "0123456789abcdef",
};

describe("parseHealth", () => {
  it("returns the health for a valid body", () => {
    expect(parseHealth(validBody)).toEqual(validBody);
  });

  it.each([
    ["null", null],
    ["a string", "ok"],
    ["missing models", { ...validBody, models: undefined }],
    ["a non-string models.fast", { ...validBody, models: { reasoning: "r", fast: 3 } }],
    ["missing git_sha", { ...validBody, git_sha: undefined }],
    ["a non-boolean fallback_used", { ...validBody, fallback_used: "no" }],
  ])("throws on %s", (_label, body) => {
    expect(() => parseHealth(body)).toThrow();
  });
});

describe("fetchHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads GET /api/health", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(validBody));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHealth()).resolves.toEqual(validBody);
    expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.anything());
  });

  it("throws on a non-2xx status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("down", { status: 500 })));

    await expect(fetchHealth()).rejects.toThrow("500");
  });

  it("aborts the request when the caller aborts", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(validBody));
    vi.stubGlobal("fetch", fetchMock);
    const caller = new AbortController();
    caller.abort();

    await fetchHealth(caller.signal);
    const init: RequestInit = fetchMock.mock.calls[0]?.[1];
    expect(init.signal?.aborted).toBe(true);
  });

  it("aborts the request after the timeout", async () => {
    vi.useFakeTimers();
    let seen: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((_path: string, init: RequestInit) => {
        seen = init.signal ?? undefined;
        return new Promise(() => {});
      }),
    );

    void fetchHealth();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(seen?.aborted).toBe(true);
    vi.useRealTimers();
  });
});
