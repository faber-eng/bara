import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchDryingTiles, parseTileLayer } from "./tiles";

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

  it.each([
    ["a non-object", 3],
    ["another layer kind", { ...layer, layer: "peat" }],
    ["a template without {x}", { ...layer, url_template: "https://t/{z}/{y}" }],
    ["a missing week", { ...layer, week: undefined }],
  ])("rejects %s", (_label, body) => {
    expect(() => parseTileLayer(body)).toThrow();
  });
});

describe("fetchDryingTiles", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("serves the fixture with no request by default", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchDryingTiles("riau");

    expect(result.layer).toBe("drying");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("calls /api/tiles/drying with the region and no week when live", async () => {
    vi.stubEnv("VITE_SOURCE_TILES", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(layer));
    vi.stubGlobal("fetch", fetchMock);

    await fetchDryingTiles("riau");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/tiles/drying?region=riau");
  });
});
