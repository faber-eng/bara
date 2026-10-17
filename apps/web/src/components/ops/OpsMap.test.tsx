import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, stubApi } from "../../test-utils";
import { OpsMap } from "./OpsMap";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const layerSpies = vi.hoisted(() => ({
  createCellLayer: vi.fn(),
  createDamLayer: vi.fn(),
}));

vi.mock("../../lib/ops/cellLayer", () => layerSpies);

type TileOptions = {
  getTileUrl: (coord: { x: number; y: number }, zoom: number) => string | null;
  opacity: number;
};
const layers: unknown[] = [];
const fakeMap = {
  fitBounds: vi.fn(),
  setOptions: vi.fn(),
  addListener: () => ({ remove: vi.fn() }),
  overlayMapTypes: {
    push: (layer: unknown) => layers.push(layer),
    getArray: () => layers,
    removeAt: (index: number) => layers.splice(index, 1),
  },
};

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: ReactNode }) => <div data-testid="maps">{children}</div>,
  Map: ({ children, mapTypeId }: { children: ReactNode; mapTypeId: string }) => (
    <div data-testid="map" data-type={mapTypeId}>
      {children}
    </div>
  ),
  useMap: () => fakeMap,
}));

class FakeImageMapType {
  options: TileOptions;
  constructor(options: TileOptions) {
    this.options = options;
  }
  setOpacity(value: number) {
    this.options.opacity = value;
  }
}

function renderMap(selectedCellId?: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <OpsMap
        selectedCellId={selectedCellId}
        focus={null}
        onCellSelect={() => {}}
        onCellClear={() => {}}
      />
    </QueryClientProvider>,
  );
}

describe("OpsMap", () => {
  beforeEach(() => {
    layers.length = 0;
    layerSpies.createCellLayer.mockReset().mockReturnValue({
      select: vi.fn(),
      focus: vi.fn(),
      destroy: vi.fn(),
    });
    layerSpies.createDamLayer.mockReset().mockReturnValue({ destroy: vi.fn() });
    vi.stubGlobal("google", { maps: { ImageMapType: FakeImageMapType, Size: class {} } });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("explains a missing Maps key instead of loading the map", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "");
    renderMap();

    expect(screen.getByRole("alert")).toHaveTextContent("Map key is missing");
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
  });

  it("adds the drying overlay from the fixture and shows the legend", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    renderMap();

    await waitFor(() => expect(layers).toHaveLength(1));
    expect(screen.getByText("Drying score (0 to 100)")).toBeInTheDocument();
    expect(screen.getByText(/2026-W42/)).toBeInTheDocument();
  });

  it("asks /api/tiles/drying for the region with no week when the source is live", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    vi.stubEnv("VITE_SOURCE_TILES", "live");
    const fetchMock = stubApi({
      "GET /api/tiles/drying?region=riau": () =>
        Response.json({
          layer: "drying",
          region: "riau",
          week: "2026-W42",
          url_template: "https://live.example/{z}/{x}/{y}",
        }),
    });
    renderMap();

    await waitFor(() => expect(layers).toHaveLength(1));
    expect(callsTo(fetchMock, "GET /api/tiles/drying?region=riau")).toHaveLength(1);
    const layer = layers[0] as FakeImageMapType;
    expect(layer.options.getTileUrl({ x: 3, y: 4 }, 5)).toBe("https://live.example/5/3/4");
  });

  it("keeps the map and says the layer is unavailable when the tiles fail", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    vi.stubEnv("VITE_SOURCE_TILES", "live");
    stubApi({ "GET /api/tiles/drying?region=riau": () => new Response("x", { status: 502 }) });
    renderMap();

    expect(await screen.findByText("Drying layer is unavailable right now.")).toBeInTheDocument();
    expect(screen.getByTestId("map")).toBeInTheDocument();
    expect(layers).toHaveLength(0);
  });

  it("starts on the hybrid base map and switches type from the control", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    renderMap();

    expect(screen.getByTestId("map")).toHaveAttribute("data-type", "hybrid");
    fireEvent.click(screen.getByRole("button", { name: "Terrain" }));

    expect(screen.getByTestId("map")).toHaveAttribute("data-type", "terrain");
    expect(screen.getByRole("button", { name: "Terrain" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the legend range and moves the overlay opacity in place", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    renderMap();
    await waitFor(() => expect(layers).toHaveLength(1));
    const layer = layers[0] as FakeImageMapType;

    expect(screen.getByText("0 low")).toBeInTheDocument();
    expect(screen.getByText("100 high")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("slider", { name: "Opacity" }), { target: { value: "30" } });

    expect(layers).toHaveLength(1);
    expect(layers[0]).toBe(layer);
    expect(layer.options.opacity).toBe(0.3);
  });

  it("builds the cell and dam layers once and keeps them when the opacity changes", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    renderMap();
    await waitFor(() => expect(layerSpies.createCellLayer).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(layers).toHaveLength(1));

    fireEvent.change(screen.getByRole("slider", { name: "Opacity" }), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Map" }));

    expect(layerSpies.createCellLayer).toHaveBeenCalledTimes(1);
    expect(layerSpies.createDamLayer).toHaveBeenCalledTimes(1);
    const cells = layerSpies.createCellLayer.mock.calls[0]?.[1] as unknown[];
    expect(cells).toHaveLength(200);
  });

  it("fits the view to the ranked cells once, capped at zoom 11", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    fakeMap.fitBounds.mockReset();
    renderMap();
    await waitFor(() => expect(layerSpies.createCellLayer).toHaveBeenCalledTimes(1));

    expect(fakeMap.fitBounds).toHaveBeenCalledTimes(1);
    expect(fakeMap.setOptions).toHaveBeenCalledWith({ maxZoom: 11 });
  });

  it("draws every area from /api/cells when the source is live", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    const rows = Array.from({ length: 3769 }, (_, i) => [`c${i}`, 0.5, 101.4, 50, i + 1]);
    stubApi({
      "GET /api/cells?region=riau": () =>
        Response.json({ region: "riau", week: "2026-W42", cells: rows }),
      "GET /api/rankings/riau": () =>
        Response.json({ region: "riau", week: "2026-W42", cells: [], dams: [] }),
    });
    renderMap();

    await waitFor(() => expect(layerSpies.createCellLayer).toHaveBeenCalledTimes(1));
    const cells = layerSpies.createCellLayer.mock.calls[0]?.[1] as unknown[];
    expect(cells).toHaveLength(3769);
  });

  it("falls back to the ranked cells and says so when all areas fail to load", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    stubApi({
      "GET /api/cells?region=riau": () => new Response("x", { status: 502 }),
      "GET /api/rankings/riau": () =>
        Response.json({ region: "riau", week: "2026-W42", cells: [], dams: [] }),
    });
    renderMap();

    expect(await screen.findByText(/Only the top 200 areas are clickable/)).toBeInTheDocument();
  });

  it("opens the cell panel for the selected cell and reads its facts", async () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    const fetchMock = stubApi({
      "GET /api/cells/riau-0412": () =>
        Response.json({
          cell_id: "riau-0412",
          region: "riau",
          components: {
            s1_anom_db: -2.8,
            rain_30d_mm: 41.2,
            rain_deficit_pct: 0.62,
            canal_dist_m: 180,
            peat_class: 1,
          },
          drying_score: 91.4,
          rank: 1,
          trend: [],
          nearby_dams: [],
          past_fires: [],
          past_checks: [],
          explanation: { text: "Ranks first on radar and rain.", cited: {} },
        }),
    });
    renderMap("riau-0412");

    const panel = await screen.findByRole("region", { name: "Cell riau-0412" });
    expect(await screen.findByText("Ranks first on radar and rain.")).toBeInTheDocument();
    expect(panel).toHaveTextContent("91.4");
    expect(panel).toHaveTextContent("180 m");
    expect(callsTo(fetchMock, "GET /api/cells/riau-0412")).toHaveLength(1);
  });

  it("shows no panel when no cell is selected", () => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    renderMap();

    expect(screen.queryByRole("region", { name: /^Cell / })).not.toBeInTheDocument();
  });
});
