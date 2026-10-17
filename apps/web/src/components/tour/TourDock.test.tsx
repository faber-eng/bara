import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TOUR_STEPS } from "../../lib/tour/steps";
import { finishTour, getTourSnapshot, goToStep, skipTour } from "../../lib/tour/store";
import { callsTo, initOf, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

describe("landing and guided tour", () => {
  beforeEach(() => {
    localStorage.clear();
    finishTour();
    return () => vi.unstubAllGlobals();
  });

  it("links to the four entry screens", async () => {
    stubApi({});
    renderApp("/");

    const nav = await screen.findByRole("navigation", { name: "Open a screen" });
    const hrefs = Array.from(nav.querySelectorAll("a")).map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(["/public", "/ops", "/area/new", "/join"]);
  });

  it("starts the tour on the public page and walks forward and back", async () => {
    stubApi({});
    const { router } = renderApp("/");

    fireEvent.click(await screen.findByRole("button", { name: "Start the guided tour" }));

    expect(await screen.findByText(`Step 1 of ${TOUR_STEPS.length}`)).toBeInTheDocument();
    expect(router.history.location.pathname).toBe("/public");

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText(`Step 2 of ${TOUR_STEPS.length}`)).toBeInTheDocument();
    expect(router.history.location.pathname).toBe("/ops");

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByText(`Step 1 of ${TOUR_STEPS.length}`)).toBeInTheDocument();
  });

  it("skips and then resumes at the same step", async () => {
    stubApi({});
    renderApp("/");

    fireEvent.click(await screen.findByRole("button", { name: "Start the guided tour" }));
    fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    fireEvent.click(await screen.findByRole("button", { name: "Skip tour" }));

    expect(screen.queryByRole("complementary", { name: "Guided tour" })).not.toBeInTheDocument();
    expect(getTourSnapshot()).toEqual({ open: false, step: 1 });
  });

  it("resumes at the saved step from the landing page", async () => {
    stubApi({});
    const { router } = renderApp("/");
    goToStep(1);
    skipTour();

    fireEvent.click(await screen.findByRole("button", { name: /Resume at step 2 of/ }));

    expect(await screen.findByText(`Step 2 of ${TOUR_STEPS.length}`)).toBeInTheDocument();
    expect(router.history.location.pathname).toBe("/ops");
  });

  it("posts drying.ranked when the action button is pressed", async () => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    const clock = { now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: true };
    const fetchMock = stubApi({
      "GET /api/clock": () => Response.json(clock),
      "POST /api/judge/trigger": () => Response.json({}),
    });
    goToStep(2);
    renderApp("/nope");

    fireEvent.click(await screen.findByRole("button", { name: "Start: weekly ranking" }));

    await waitFor(() => expect(callsTo(fetchMock, "POST /api/judge/trigger")).toHaveLength(1));
    const call = callsTo(fetchMock, "POST /api/judge/trigger")[0];
    expect(JSON.parse(String(initOf(call).body))).toEqual({ event: "drying.ranked" });
    vi.unstubAllEnvs();
  });
});
