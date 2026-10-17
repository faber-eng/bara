import { afterEach, describe, expect, it, vi } from "vitest";
import { splitEvents, streamCase, streamUrl } from "./caseStream";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

function sseResponse(chunks: Array<{ at: number; text: string }>): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        setTimeout(() => controller.enqueue(encoder.encode(chunk.text)), chunk.at);
      }
      const last = chunks.at(-1)?.at ?? 0;
      setTimeout(() => controller.close(), last + 1);
    },
  });
  return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
}

describe("streamUrl", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("is same origin when no base is set", () => {
    vi.stubEnv("VITE_STREAM_BASE", "");
    expect(streamUrl("c 1")).toBe("/api/cases/c%201/stream");
  });

  it("starts from the build-time base", () => {
    vi.stubEnv("VITE_STREAM_BASE", "https://bara-api.example");
    expect(streamUrl("c1")).toBe("https://bara-api.example/api/cases/c1/stream");
  });
});

describe("splitEvents", () => {
  it("returns whole events, skips keepalives and keeps a partial tail", () => {
    const parsed = splitEvents(
      'event: open\ndata: {"a":1}\n\n: keepalive\n\nevent: tool\ndata: {"b"',
    );
    expect(parsed.events).toEqual([{ name: "open", data: '{"a":1}' }]);
    expect(parsed.rest).toBe('event: tool\ndata: {"b"');
  });
});

describe("streamCase", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("sends the token and role headers to the base URL and reports each event when it arrives", async () => {
    vi.useFakeTimers();
    vi.stubEnv("VITE_STREAM_BASE", "https://bara-api.example");
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        { at: 100, text: 'event: open\ndata: {"case_id":"c1"}\n\n' },
        { at: 8_900, text: 'event: tool\ndata: {"index":0}\n\n' },
        { at: 15_600, text: 'event: tool\ndata: {"index":1}\n\n' },
        { at: 39_400, text: 'event: final\ndata: {"status":"done"}\n\n' },
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    const arrivals: Array<{ name: string; at: number }> = [];
    const started = Date.now();

    const done = streamCase(
      "c1",
      (event) => arrivals.push({ name: event.name, at: Date.now() - started }),
      new AbortController().signal,
    );
    await vi.advanceTimersByTimeAsync(40_000);
    await done;

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://bara-api.example/api/cases/c1/stream");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer token-1");
    expect(arrivals.map((arrival) => arrival.name)).toEqual(["open", "tool", "tool", "final"]);
    expect(arrivals.find((arrival) => arrival.name === "tool")?.at).toBe(8_900);
  });

  it("fails when the server refuses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("no", { status: 403 })));
    await expect(streamCase("c1", vi.fn(), new AbortController().signal)).rejects.toThrow("403");
  });
});
