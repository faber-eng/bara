import { QueryClient } from "@tanstack/react-query";
import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { setJudgeMode } from "../../lib/judge/store";
import { callsTo, headerOf, initOf, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const clockOn = { now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: true };
const accepted = (event: string) => Response.json({ event, message_id: "m1" }, { status: 202 });

function bar() {
  return screen.getByRole("region", { name: "Judge mode" });
}

async function openBar() {
  renderApp("/public");
  await screen.findByRole("region", { name: "Judge mode" });
}

describe("scenario controls", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    setJudgeMode(false);
    setCopyLanguage("en");
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    setCopyLanguage("id");
  });

  it.each([
    ["Start: weekly ranking", "drying.ranked"],
    ["Start: fire goes quiet", "fire.quiet"],
  ])("%s posts %s with the judge role and shows the wait note", async (label, event) => {
    const fetchMock = stubApi({
      "GET /api/clock": () => Response.json(clockOn),
      "POST /api/judge/trigger": () => accepted(event),
    });
    await openBar();

    fireEvent.click(within(bar()).getByRole("button", { name: label }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Cases are being created, about 30 s",
    );
    const call = callsTo(fetchMock, "POST /api/judge/trigger")[0];
    expect(JSON.parse(String(initOf(call).body))).toEqual({ event });
    expect(headerOf(call, "X-Bara-Role")).toBe("judge");
  });

  it("speaks Indonesian by default", async () => {
    setCopyLanguage("id");
    stubApi({
      "GET /api/clock": () => Response.json(clockOn),
      "POST /api/judge/trigger": () => accepted("drying.ranked"),
    });
    await openBar();

    fireEvent.click(within(bar()).getByRole("button", { name: "Mulai: peringkat mingguan" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Kasus sedang dibuat, sekitar 30 dtk",
    );
  });

  it.each([
    [403, "not allowed"],
    [429, "Too many requests"],
    [409, "No ranking data"],
    [502, "Could not start"],
    [500, "Could not start"],
  ])("explains a %s in plain words", async (status, text) => {
    stubApi({
      "GET /api/clock": () => Response.json(clockOn),
      "POST /api/judge/trigger": () => new Response("x", { status }),
    });
    await openBar();

    fireEvent.click(within(bar()).getByRole("button", { name: "Start: weekly ranking" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(text);
    expect(within(bar()).getByRole("button", { name: "Start: weekly ranking" })).toBeEnabled();
  });

  it("refetches the cases list for about 90 s, then stops", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      stubApi({
        "GET /api/clock": () => Response.json(clockOn),
        "POST /api/judge/trigger": () => accepted("drying.ranked"),
      });
      const queryClient = new QueryClient();
      const spy = vi.spyOn(queryClient, "invalidateQueries");
      renderApp("/public", queryClient);
      await screen.findByRole("region", { name: "Judge mode" });
      fireEvent.click(within(bar()).getByRole("button", { name: "Start: weekly ranking" }));
      await screen.findByRole("status");
      const casesCalls = () =>
        spy.mock.calls.filter(([filters]) => filters?.queryKey?.[0] === "cases").length;
      const before = casesCalls();

      await vi.advanceTimersByTimeAsync(10_000);
      expect(casesCalls()).toBeGreaterThan(before);

      await vi.advanceTimersByTimeAsync(85_000);
      const stopped = casesCalls();
      await vi.advanceTimersByTimeAsync(30_000);
      expect(casesCalls()).toBe(stopped);
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
