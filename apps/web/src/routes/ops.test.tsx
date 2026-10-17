import cases from "@fixtures/cases.json";
import rankings from "@fixtures/rankings_riau_200.json";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetClock } from "../lib/api/clock";
import { setJudgeMode } from "../lib/judge/store";
import { callsTo, headerOf, renderApp, stubApi } from "../test-utils";

vi.mock("../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("claims-token") }));
vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Map: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  useMap: () => null,
}));

describe("/ops", () => {
  beforeEach(async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    setJudgeMode(false);
    localStorage.clear();
    await resetClock();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("opens on the ranked areas tab with the map", async () => {
    renderApp("/ops");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Ops dashboard" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getByTestId("map")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Ranked areas/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("opens on the cases tab from ?tab=cases", async () => {
    renderApp("/ops?tab=cases");

    expect(await screen.findByRole("button", { name: /riau-0412/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Cases/ })).toHaveAttribute("aria-selected", "true");
  });

  it("writes the tab to the URL when the tab changes", async () => {
    const { router } = renderApp("/ops");
    await screen.findByRole("table");

    fireEvent.click(screen.getByRole("tab", { name: /Cases/ }));

    await waitFor(() => expect(router.state.location.search).toMatchObject({ tab: "cases" }));
    expect(await screen.findByRole("button", { name: /riau-0412/ })).toBeInTheDocument();
  });

  it("writes the case to the URL when a row is clicked", async () => {
    const { router } = renderApp("/ops?tab=cases");

    fireEvent.click(await screen.findByRole("button", { name: /riau-0388/ }));

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ tab: "cases", case: "case-0003" }),
    );
    expect(screen.getByRole("button", { name: /riau-0388/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("ignores an unknown tab value", async () => {
    renderApp("/ops?tab=weird");

    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("moves a case chip and countdown when the judge advances the fixture clock", async () => {
    renderApp("/ops?tab=cases");
    const row = await screen.findByRole("button", { name: /riau-0412/ });
    expect(row).toHaveTextContent("Assigned");
    expect(row).toHaveTextContent("Due in 3 d 9 h");

    fireEvent.click(await screen.findByRole("button", { name: "+48h" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /riau-0412/ })).toHaveTextContent("Due in 1 d 9 h"),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /riau-0388/ })).toHaveTextContent(
        "Overdue by 1 d 23 h",
      ),
    );
  });

  it("loads for a real signed-in user with the Bearer token and no judge header", async () => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    vi.stubEnv("VITE_SOURCE_CASES", "live");
    vi.stubEnv("VITE_SOURCE_TILES", "live");
    const fetchMock = stubApi({
      "GET /api/clock": () =>
        Response.json({ now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: false }),
      "GET /api/rankings/riau": () => Response.json(rankings),
      "GET /api/cases?region=riau": () => Response.json(cases),
      "GET /api/tiles/drying?region=riau": () =>
        Response.json({
          layer: "drying",
          region: "riau",
          week: "2026-W42",
          url_template: "https://live.example/{z}/{x}/{y}",
        }),
    });
    renderApp("/ops");

    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Judge mode" })).not.toBeInTheDocument();
    const call = callsTo(fetchMock, "GET /api/rankings/riau")[0];
    expect(headerOf(call, "Authorization")).toBe("Bearer claims-token");
    expect(headerOf(call, "X-Bara-Role")).toBeNull();
  });

  it("tells a signed-in account without the ops role", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    stubApi({ "GET /api/rankings/riau": () => new Response("no", { status: 403 }) });
    renderApp("/ops");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This account does not have the ops role",
    );
  });
});
