import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { headerOf, initOf } from "../../test-utils";
import { setJudgeMode } from "../judge/store";
import { ApiError } from "./client";
import { triggerScenario } from "./trigger";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

describe("triggerScenario", () => {
  beforeEach(() => {
    setJudgeMode(true);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(["drying.ranked", "fire.quiet"] as const)(
    "posts %s with the judge role",
    async (event) => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue(Response.json({ event, message_id: "m1" }, { status: 202 }));
      vi.stubGlobal("fetch", fetchMock);

      await triggerScenario(event);

      const call = fetchMock.mock.calls[0];
      expect(call?.[0]).toBe("/api/judge/trigger");
      expect(initOf(call).method).toBe("POST");
      expect(JSON.parse(String(initOf(call).body))).toEqual({ event });
      expect(headerOf(call, "X-Bara-Role")).toBe("judge");
    },
  );

  it("throws an ApiError carrying the status on 403", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("no", { status: 403 })));

    const failure = await triggerScenario("fire.quiet").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(403);
  });
});
