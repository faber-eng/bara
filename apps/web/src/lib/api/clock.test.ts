import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { roleHeaderValue, setJudgeMode } from "../judge/store";
import { ApiError } from "./client";
import { advanceClock, fetchClock, parseClockState, resetClock } from "./clock";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const liveState = { now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: true };

describe("parseClockState", () => {
  it("returns a valid state", () => {
    expect(parseClockState(liveState)).toEqual(liveState);
  });

  it.each([
    ["null", null],
    ["a missing now", { ...liveState, now: undefined }],
    ["a string offset", { ...liveState, offset_seconds: "0" }],
    ["a non-boolean judge_mode", { ...liveState, judge_mode: "yes" }],
  ])("rejects %s", (_label, body) => {
    expect(() => parseClockState(body)).toThrow();
  });
});

describe("live clock", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    setJudgeMode(false);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("reads GET /api/clock and turns judge mode on", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(liveState));
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchClock()).toEqual(liveState);

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/clock");
    expect(roleHeaderValue()).toBe("ops");
  });

  it("turns judge mode off when the server says so", async () => {
    setJudgeMode(true);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ ...liveState, judge_mode: false })),
    );

    await fetchClock();

    expect(roleHeaderValue()).toBeUndefined();
  });

  it("turns judge mode off when the request fails", async () => {
    setJudgeMode(true);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("x", { status: 404 })));

    await expect(fetchClock()).rejects.toBeInstanceOf(ApiError);

    expect(roleHeaderValue()).toBeUndefined();
  });

  it("posts the hours to /api/judge/advance", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(liveState));
    vi.stubGlobal("fetch", fetchMock);

    await advanceClock(48);

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/judge/advance");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"hours":48}');
  });

  it("posts to /api/judge/reset", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(liveState));
    vi.stubGlobal("fetch", fetchMock);

    await resetClock();

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/judge/reset");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.method).toBe("POST");
  });
});

describe("fixture clock", () => {
  beforeEach(async () => {
    setJudgeMode(false);
    await resetClock();
  });

  it("serves the clock fixture without a request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const state = await fetchClock();

    expect(state).toEqual(liveState);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(roleHeaderValue()).toBe("ops");
    vi.unstubAllGlobals();
  });

  it("moves the sim time forward on advance and back on reset", async () => {
    const advanced = await advanceClock(48);

    expect(advanced.offset_seconds).toBe(48 * 3600);
    expect(Date.parse(advanced.now)).toBe(Date.parse(liveState.now) + 48 * 3_600_000);
    expect((await fetchClock()).offset_seconds).toBe(48 * 3600);

    const reset = await resetClock();

    expect(reset).toEqual(liveState);
  });
});

describe("live clock cold start", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(
        (_path: string, init: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("t", "AbortError")),
            );
          }),
      ),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("keeps waiting through a cold start and gives up after 15 seconds", async () => {
    const outcome = fetchClock().then(
      () => "answered",
      () => "failed",
    );

    await vi.advanceTimersByTimeAsync(14_900);
    const early = await Promise.race([outcome, Promise.resolve("waiting")]);
    await vi.advanceTimersByTimeAsync(200);

    expect(early).toBe("waiting");
    expect(await outcome).toBe("failed");
  });
});
