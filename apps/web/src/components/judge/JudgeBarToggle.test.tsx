import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { reloadJudgeBar } from "../../lib/judge/barState";
import { setJudgeMode } from "../../lib/judge/store";
import { finishTour, goToStep } from "../../lib/tour/store";
import { callsTo, initOf, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const clockOn = { now: "2026-10-18T10:37:00+07:00", offset_seconds: 0, judge_mode: true };

function stubClock() {
  return stubApi({
    "GET /api/clock": () => Response.json(clockOn),
    "POST /api/judge/advance": () => Response.json(clockOn),
    "POST /api/judge/trigger": () => Response.json({}),
  });
}

function pill() {
  return screen.findByRole("button", { name: /^Demo Panel · / });
}

describe("judge bar collapse", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    setJudgeMode(false);
    finishTour();
    localStorage.clear();
    reloadJudgeBar();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("opens on the first visit with a collapse button and every label", async () => {
    stubClock();
    renderApp("/nope");

    const bar = await screen.findByRole("region", { name: "Demo Panel" });

    expect(within(bar).getByRole("button", { name: "Collapse Demo Panel" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    for (const name of [
      "+6h",
      "+24h",
      "+48h",
      "Reset scenario",
      "Start: weekly ranking",
      "Start: fire goes quiet",
    ]) {
      expect(within(bar).getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("collapses to a pill showing the sim time and expands again", async () => {
    stubClock();
    renderApp("/nope");
    fireEvent.click(await screen.findByRole("button", { name: "Collapse Demo Panel" }));

    const collapsed = await pill();
    expect(collapsed).toHaveTextContent("Demo Panel · 18 Oct 10:37");
    expect(collapsed).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "+48h" })).not.toBeInTheDocument();
    expect(localStorage.getItem("bara.judgeBar")).toBe("closed");

    fireEvent.click(collapsed);

    expect(await screen.findByRole("button", { name: "+48h" })).toBeInTheDocument();
    expect(localStorage.getItem("bara.judgeBar")).toBe("open");
  });

  it("starts collapsed when the stored choice is closed", async () => {
    localStorage.setItem("bara.judgeBar", "closed");
    reloadJudgeBar();
    stubClock();
    renderApp("/nope");

    expect(await pill()).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Demo Panel" })).not.toBeInTheDocument();
  });

  it("falls back to open on an unknown stored value", async () => {
    localStorage.setItem("bara.judgeBar", "sideways");
    reloadJudgeBar();
    stubClock();
    renderApp("/nope");

    expect(await screen.findByRole("region", { name: "Demo Panel" })).toBeInTheDocument();
  });

  it("still toggles when storage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    reloadJudgeBar();
    stubClock();
    renderApp("/nope");

    fireEvent.click(await screen.findByRole("button", { name: "Collapse Demo Panel" }));

    expect(await pill()).toBeInTheDocument();
  });

  it("lets the tour act while the bar is collapsed", async () => {
    localStorage.setItem("bara.judgeBar", "closed");
    reloadJudgeBar();
    const fetchMock = stubClock();
    goToStep(2);
    renderApp("/nope");
    await pill();

    fireEvent.click(await screen.findByRole("button", { name: "Start: weekly ranking" }));

    await waitFor(() => expect(callsTo(fetchMock, "POST /api/judge/trigger")).toHaveLength(1));
    expect(
      JSON.parse(String(initOf(callsTo(fetchMock, "POST /api/judge/trigger")[0]).body)),
    ).toEqual({ event: "drying.ranked" });
  });
});
