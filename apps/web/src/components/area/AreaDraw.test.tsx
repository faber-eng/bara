import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { callsTo, initOf, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

type ClickEvent = { detail: { latLng: { lat: number; lng: number } | null } };
const CORNERS = [
  { lat: 0.5, lng: 102.0 },
  { lat: 0.5, lng: 102.09 },
  { lat: 0.59, lng: 102.09 },
];

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Map: ({ children, onClick }: { children: ReactNode; onClick: (event: ClickEvent) => void }) => (
    <div data-testid="map">
      {CORNERS.map((corner) => (
        <button
          key={`${corner.lat}-${corner.lng}`}
          type="button"
          onClick={() => onClick({ detail: { latLng: corner } })}
        >
          corner {corner.lat} {corner.lng}
        </button>
      ))}
      {children}
    </div>
  ),
  useMap: () => null,
}));

const ranked = {
  status: "ranked",
  region: "riau",
  week: "2026-W42",
  polygon_hash: "a".repeat(64),
  area_km2: 99.5,
  peat_cells: 121,
  cells: [
    { cell_id: "riau-1-2", centroid: { lat: 0.5, lon: 102 }, drying_score: 80.04, rank: 1 },
    { cell_id: "riau-1-3", centroid: { lat: 0.51, lon: 102 }, drying_score: 60, rank: 2 },
  ],
  tile_url_template: "https://tiles.example/{z}/{x}/{y}",
  cached: false,
};

function drawTriangle() {
  for (const button of screen.getAllByRole("button", { name: /^corner/ })) fireEvent.click(button);
}

describe("draw an area", () => {
  beforeEach(() => {
    setCopyLanguage("en");
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("keeps Rank disabled until three corners are placed", async () => {
    stubApi({});
    renderApp("/area/new");
    const rank = await screen.findByRole("button", { name: "Rank this area" });

    expect(rank).toBeDisabled();
    const corners = screen.getAllByRole("button", { name: /^corner/ });
    fireEvent.click(corners[0] as HTMLElement);
    fireEvent.click(corners[1] as HTMLElement);
    expect(screen.getByText("Place at least 3 corners.")).toBeInTheDocument();
    fireEvent.click(corners[2] as HTMLElement);

    expect(rank).toBeEnabled();
  });

  it("posts the polygon and lists the top cells", async () => {
    const fetchMock = stubApi({ "POST /api/areas/rank": () => Response.json(ranked) });
    renderApp("/area/new");
    await screen.findByRole("button", { name: "Rank this area" });
    drawTriangle();

    fireEvent.click(screen.getByRole("button", { name: "Rank this area" }));

    const first = await screen.findByRole("button", { name: /riau-1-2/ });
    expect(first).toHaveTextContent("Rank 1 of 2");
    expect(first).toHaveTextContent("80.0");
    expect(screen.getByRole("button", { name: /riau-1-3/ })).toHaveTextContent("Rank 2 of 2");
    expect(screen.queryByText(/1\. 1\./)).not.toBeInTheDocument();
    const sent = JSON.parse(String(initOf(callsTo(fetchMock, "POST /api/areas/rank")[0]).body));
    expect(sent.coordinates[0]).toHaveLength(4);
  });

  it("opens one cell's detail dialog from its row", async () => {
    stubApi({ "POST /api/areas/rank": () => Response.json(ranked) });
    renderApp("/area/new");
    await screen.findByRole("button", { name: "Rank this area" });
    drawTriangle();
    fireEvent.click(screen.getByRole("button", { name: "Rank this area" }));

    fireEvent.click(await screen.findByRole("button", { name: /riau-1-2/ }));

    const dialog = await screen.findByRole("dialog", { name: "Cell riau-1-2" });
    expect(dialog).toHaveTextContent("This circle is a ranked peat cell inside the area you drew.");
    expect(dialog).toHaveTextContent("80.0 / 100");
    expect(within(dialog).getByRole("button", { name: "Copy cell ID" })).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("says plainly when the area has no mapped peat", async () => {
    stubApi({
      "POST /api/areas/rank": () =>
        Response.json({ ...ranked, status: "no_peat", cells: [], tile_url_template: null }),
    });
    renderApp("/area/new");
    await screen.findByRole("button", { name: "Rank this area" });
    drawTriangle();

    fireEvent.click(screen.getByRole("button", { name: "Rank this area" }));

    expect(
      await screen.findByText("No mapped peat in this area. Move it or make it larger."),
    ).toBeInTheDocument();
  });

  it("shows the hourly limit message on a 429", async () => {
    stubApi({
      "POST /api/areas/rank": () =>
        Response.json(
          { detail: "area_rank_limit" },
          { status: 429, headers: { "Retry-After": "90" } },
        ),
    });
    renderApp("/area/new");
    await screen.findByRole("button", { name: "Rank this area" });
    drawTriangle();

    fireEvent.click(screen.getByRole("button", { name: "Rank this area" }));

    expect(await screen.findByTestId("area-error")).toHaveTextContent("all 10 rankings");
  });

  it("removes the last corner and clears all", async () => {
    stubApi({});
    renderApp("/area/new");
    await screen.findByRole("button", { name: "Rank this area" });
    drawTriangle();

    fireEvent.click(screen.getByRole("button", { name: "Remove last corner" }));
    expect(screen.getByText(/^2 corners/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));

    expect(screen.queryByText(/corners, about/)).not.toBeInTheDocument();
  });

  it("loads a sample into the draft so it can be ranked", async () => {
    stubApi({
      "GET /api/samples?kind=area": () =>
        Response.json([
          {
            id: "a1",
            kind: "area",
            label: "Riau area 1",
            credit: "c",
            url: "/api/samples/a1/file",
          },
        ]),
      "GET /api/samples/a1/file": () =>
        Response.json({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { name: "Riau area 1" },
              geometry: {
                type: "Polygon",
                coordinates: [
                  [
                    [102.1, 0.55],
                    [102.18, 0.55],
                    [102.18, 0.62],
                    [102.1, 0.62],
                    [102.1, 0.55],
                  ],
                ],
              },
            },
          ],
        }),
    });
    renderApp("/area/new");

    fireEvent.click(await screen.findByRole("button", { name: "Use a sample" }));
    fireEvent.click(await screen.findByRole("button", { name: /Riau area 1/ }));

    expect(await screen.findByText(/^4 corners, about/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rank this area" })).toBeEnabled();
  });
});
