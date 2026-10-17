import { afterEach, describe, expect, it, vi } from "vitest";
import { initOf } from "../../test-utils";
import { parseAreaRanking, rankArea } from "./areaRank";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const ranking = {
  status: "ranked",
  region: "riau",
  week: "2026-W42",
  polygon_hash: "a".repeat(64),
  area_km2: 99.5,
  peat_cells: 121,
  cells: [{ cell_id: "riau-1-2", centroid: { lat: 0.5, lon: 102 }, drying_score: 80, rank: 1 }],
  tile_url_template: "https://tiles.example/{z}/{x}/{y}",
  cached: false,
};

describe("parseAreaRanking", () => {
  it("reads a ranked area", () => {
    expect(parseAreaRanking(ranking)).toEqual(ranking);
  });

  it("reads a no-peat area with a null tile url", () => {
    const empty = { ...ranking, status: "no_peat", cells: [], tile_url_template: null };
    expect(parseAreaRanking(empty).tile_url_template).toBeNull();
  });

  it.each([
    ["an unknown status", { ...ranking, status: "maybe" }],
    ["a missing cells list", { ...ranking, cells: undefined }],
    ["a non-object", 4],
  ])("rejects %s", (_label, body) => {
    expect(() => parseAreaRanking(body)).toThrow();
  });
});

describe("rankArea", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts the closed polygon as GeoJSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(ranking));
    vi.stubGlobal("fetch", fetchMock);
    const points = [
      { lat: 0.5, lon: 102 },
      { lat: 0.5, lon: 102.1 },
      { lat: 0.6, lon: 102.1 },
    ];

    const result = await rankArea(points);

    expect(result.cells).toHaveLength(1);
    const [path, init] = fetchMock.mock.calls[0] ?? [];
    expect(path).toBe("/api/areas/rank");
    expect(initOf([path, init]).method).toBe("POST");
    const sent = JSON.parse(String(initOf([path, init]).body));
    expect(sent.type).toBe("Polygon");
    expect(sent.coordinates[0]).toHaveLength(4);
  });
});
