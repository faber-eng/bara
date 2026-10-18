import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type ReactNode, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { outlineMapsApi } from "../../test-utils";
import { OpsMap } from "./OpsMap";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const layerSpies = vi.hoisted(() => ({ createCellLayer: vi.fn(), createDamLayer: vi.fn() }));
vi.mock("../../lib/ops/cellLayer", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/ops/cellLayer")>()),
  ...layerSpies,
}));

type TileOptions = {
  getTileUrl: (coord: { x: number; y: number }, zoom: number) => string | null;
  opacity: number;
};
const overlays: unknown[] = [];
const fakeMap = {
  fitBounds: vi.fn(),
  setOptions: vi.fn(),
  setCenter: vi.fn(),
  setZoom: vi.fn(),
  addListener: () => ({ remove: vi.fn() }),
  overlayMapTypes: {
    push: (layer: unknown) => overlays.push(layer),
    getArray: () => overlays,
    removeAt: (index: number) => overlays.splice(index, 1),
    insertAt: (index: number, layer: unknown) => overlays.splice(index, 0, layer),
  },
};

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Map: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
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

const UNCACHED_DELAY_MS = 80;
const LATEST = "2026-W42";
const requested: string[] = [];

function rankingsBody(week: string) {
  return { region: "riau", week, cells: [], dams: [] };
}

function tileBody(layer: string, week: string) {
  return {
    layer,
    region: "riau",
    week,
    url_template: `https://t.example/${layer}/${week}/{z}/{x}/{y}`,
  };
}

function weekOf(url: URL): string {
  return url.searchParams.get("week") ?? LATEST;
}

async function answer(url: URL): Promise<Response> {
  if (url.pathname === "/api/cells") {
    return Response.json({ region: "riau", week: LATEST, cells: [] });
  }
  if (url.pathname.startsWith("/api/rankings/")) {
    return Response.json(rankingsBody(weekOf(url)));
  }
  const layer = url.pathname.replace("/api/tiles/", "");
  const week = weekOf(url);
  const prefetched = Number(week.slice(-2)) >= Number(LATEST.slice(-2)) - 1;
  if (!prefetched) await new Promise((resolve) => setTimeout(resolve, UNCACHED_DELAY_MS));
  return Response.json(tileBody(layer, week));
}

function stubLive() {
  const fetchMock = vi.fn().mockImplementation((path: string) => {
    if (path === "/api/health") return Promise.resolve(Response.json({}));
    const url = new URL(path, "http://localhost");
    requested.push(`${url.pathname}${url.search}`);
    return answer(url);
  });
  vi.stubGlobal("fetch", fetchMock);
}

function Harness() {
  const [week, setWeek] = useState<string | undefined>(undefined);
  return (
    <OpsMap
      region="riau"
      week={week}
      selectedCellId={undefined}
      focus={null}
      onRegionChange={() => {}}
      onWeekChange={setWeek}
      onCellSelect={() => {}}
      onDamSelect={() => {}}
      onCaseSelect={() => {}}
    />
  );
}

function renderHarness() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Harness />
    </QueryClientProvider>,
  );
}

function slideTo(week: string) {
  fireEvent.change(screen.getByRole("slider", { name: /Week/ }), {
    target: { value: String(Number(week.slice(-2)) - 20) },
  });
}

function currentUrl(): string | null {
  const layer = overlays[0] as FakeImageMapType | undefined;
  return layer?.options.getTileUrl({ x: 1, y: 2 }, 3) ?? null;
}

function swapMillis(): number[] {
  return performance.getEntriesByName("ops-week-swap").map((entry) => entry.duration);
}

describe("OpsMap week slider and layers", () => {
  beforeEach(() => {
    overlays.length = 0;
    requested.length = 0;
    performance.clearMeasures();
    layerSpies.createCellLayer.mockReset().mockReturnValue({
      select: vi.fn(),
      focus: vi.fn(),
      destroy: vi.fn(),
    });
    layerSpies.createDamLayer.mockReset().mockReturnValue({ destroy: vi.fn() });
    vi.stubGlobal("google", {
      maps: { ImageMapType: FakeImageMapType, Size: class {}, ...outlineMapsApi },
    });
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    vi.stubEnv("VITE_SOURCE_TILES", "live");
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    stubLive();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("offers W20 to the latest week and starts on the latest", async () => {
    renderHarness();

    const slider = await screen.findByRole("slider", { name: /Week/ });
    await waitFor(() => expect(slider).toHaveAttribute("max", "22"));
    expect(slider).toHaveAttribute("min", "0");
    expect(slider).toHaveAttribute("aria-valuetext", LATEST);
  });

  it("swaps a prefetched week in place without rebuilding anything", async () => {
    renderHarness();
    await waitFor(() => expect(currentUrl()).toBe(`https://t.example/drying/${LATEST}/3/1/2`));
    await waitFor(() => expect(requested).toContain("/api/tiles/drying?region=riau&week=2026-W41"));
    const layer = overlays[0];

    slideTo("2026-W41");

    await waitFor(() => expect(currentUrl()).toBe("https://t.example/drying/2026-W41/3/1/2"));
    expect(overlays).toHaveLength(1);
    expect(overlays[0]).toBe(layer);
    expect(layerSpies.createCellLayer).toHaveBeenCalledTimes(1);
    expect(layerSpies.createDamLayer).toHaveBeenCalledTimes(1);
    const tileCalls = requested.filter(
      (entry) => entry === "/api/tiles/drying?region=riau&week=2026-W41",
    );
    expect(tileCalls).toHaveLength(1);
    console.info("week switch cached ms", swapMillis());
  });

  it("keeps the old surface until an uncached week arrives, then swaps in place", async () => {
    renderHarness();
    await waitFor(() => expect(currentUrl()).toBe(`https://t.example/drying/${LATEST}/3/1/2`));
    const layer = overlays[0];

    slideTo("2026-W30");
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(currentUrl()).toBe(`https://t.example/drying/${LATEST}/3/1/2`);
    await waitFor(() => expect(currentUrl()).toBe("https://t.example/drying/2026-W30/3/1/2"));

    expect(overlays[0]).toBe(layer);
    expect(layerSpies.createCellLayer).toHaveBeenCalledTimes(1);
    console.info("week switch uncached ms", swapMillis());
  });

  it("asks only for the week the slider rests on when dragged", async () => {
    renderHarness();
    await waitFor(() => expect(currentUrl()).not.toBeNull());

    for (const week of ["2026-W36", "2026-W35", "2026-W34", "2026-W33", "2026-W32"]) slideTo(week);

    await waitFor(() => expect(currentUrl()).toBe("https://t.example/drying/2026-W32/3/1/2"));
    const skipped = requested.filter((entry) => /week=2026-W3[4-6]/.test(entry));
    expect(skipped).toEqual([]);
  });

  it("toggles a layer on and off in place and keeps the legend for the layers on", async () => {
    renderHarness();
    await waitFor(() => expect(overlays).toHaveLength(1));

    fireEvent.click(screen.getByRole("checkbox", { name: "Peat" }));
    await waitFor(() => expect(overlays).toHaveLength(2));
    expect(screen.getByText(/^Peat map:/)).toBeInTheDocument();
    expect(screen.getByText(/^Square = a 1 km peat area/)).toBeInTheDocument();
    expect(requested).toContain("/api/tiles/peat?region=riau");

    fireEvent.click(screen.getByRole("checkbox", { name: "Peat" }));
    await waitFor(() => expect(overlays).toHaveLength(1));
    expect(screen.queryByText(/^Peat map:/)).not.toBeInTheDocument();
    expect(screen.getByText(/^Square = a 1 km peat area/)).toBeInTheDocument();
    expect(layerSpies.createCellLayer).toHaveBeenCalledTimes(1);
    console.info(
      "layer shown ms",
      performance.getEntriesByName("ops-layer-shown").map((entry) => entry.duration),
    );
  });

  it("does not fetch a peat layer again when the week changes", async () => {
    renderHarness();
    await waitFor(() => expect(overlays).toHaveLength(1));
    fireEvent.click(screen.getByRole("checkbox", { name: "Peat" }));
    await waitFor(() => expect(overlays).toHaveLength(2));

    slideTo("2026-W41");
    await waitFor(() => expect(currentUrl()).toBe("https://t.example/drying/2026-W41/3/1/2"));

    expect(requested.filter((entry) => entry.startsWith("/api/tiles/peat"))).toEqual([
      "/api/tiles/peat?region=riau",
    ]);
  });

  it("says a layer is unavailable and keeps the others", async () => {
    stubLive();
    const original = globalThis.fetch;
    vi.stubGlobal("fetch", (path: string, init?: RequestInit) => {
      if (path.startsWith("/api/tiles/burn_scars")) {
        return Promise.resolve(new Response("x", { status: 404 }));
      }
      return original(path, init);
    });
    renderHarness();
    await waitFor(() => expect(overlays).toHaveLength(1));

    fireEvent.click(screen.getByRole("checkbox", { name: "Burn scars" }));

    expect(
      await screen.findByText("Burn scars layer is unavailable right now."),
    ).toBeInTheDocument();
    expect(overlays).toHaveLength(1);
  });
});
