import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, stubApi } from "../../test-utils";
import { OpsMap } from "./OpsMap";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

type TileOptions = { getTileUrl: (coord: { x: number; y: number }, zoom: number) => string | null };
const layers: unknown[] = [];
const fakeMap = {
  overlayMapTypes: {
    push: (layer: unknown) => layers.push(layer),
    getArray: () => layers,
    removeAt: (index: number) => layers.splice(index, 1),
  },
};

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: ReactNode }) => <div data-testid="maps">{children}</div>,
  Map: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  useMap: () => fakeMap,
}));

class FakeImageMapType {
  options: TileOptions;
  constructor(options: TileOptions) {
    this.options = options;
  }
}

function renderMap() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <OpsMap />
    </QueryClientProvider>,
  );
}

describe("OpsMap", () => {
  beforeEach(() => {
    layers.length = 0;
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
});
