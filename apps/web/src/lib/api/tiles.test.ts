import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchTileLayer, parseTileLayer } from "./tiles";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const layer = {
  layer: "drying",
  region: "riau",
  week: "2026-W42",
  url_template: "https://tiles.example/{z}/{x}/{y}",
};

describe("parseTileLayer", () => {
  it("returns a valid layer", () => {
    expect(parseTileLayer(layer)).toEqual(layer);
  });

  it.each(["peat", "burn_scars", "reignition"])("accepts the %s layer", (kind) => {
    expect(parseTileLayer({ ...layer, layer: kind }).layer).toBe(kind);
  });

  it.each([
    ["a non-object", 3],
    ["an unknown layer kind", { ...layer, layer: "clouds" }],
    ["a template without {x}", { ...layer, url_template: "https://t/{z}/{y}" }],
    ["a missing week", { ...layer, week: undefined }],
  ])("rejects %s", (_label, body) => {
    expect(() => parseTileLayer(body)).toThrow();
  });
});

describe("fetchTileLayer", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("serves the fixture with no request by default", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchTileLayer("drying", "riau", undefined);

    expect(result.layer).toBe("drying");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("calls /api/tiles/drying with the region and no week when live", async () => {
    vi.stubEnv("VITE_SOURCE_TILES", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(layer));
    vi.stubGlobal("fetch", fetchMock);

    await fetchTileLayer("drying", "riau", undefined);

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/tiles/drying?region=riau");
  });

  it.each([
    ["peat", "riau", "2026-W30", "/api/tiles/peat?region=riau&week=2026-W30"],
    ["burn_scars", "riau", undefined, "/api/tiles/burn_scars?region=riau"],
    [
      "reignition",
      "congo_cuvette",
      "2026-W21",
      "/api/tiles/reignition?region=congo_cuvette&week=2026-W21",
    ],
  ] as const)("asks for %s in %s", async (kind, region, week, path) => {
    vi.stubEnv("VITE_SOURCE_TILES", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ ...layer, layer: kind }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchTileLayer(kind, region, week);

    expect(fetchMock.mock.calls[0]?.[0]).toBe(path);
  });
});
