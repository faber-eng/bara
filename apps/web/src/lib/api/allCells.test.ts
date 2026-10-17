import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAllCells, parseAllCells } from "./allCells";
import { ResponseShapeError } from "./parse";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const BODY = {
  region: "riau",
  week: "2026-W42",
  cells: [
    ["riau-1-1", 0.5, 101.4, 90.5, 1],
    ["riau-1-2", 0.51, 101.41, 12, 3000],
  ],
};

describe("parseAllCells", () => {
  it("reads compact rows into points", () => {
    const parsed = parseAllCells(BODY);

    expect(parsed.week).toBe("2026-W42");
    expect(parsed.cells[1]).toEqual({
      cell_id: "riau-1-2",
      centroid: { lat: 0.51, lon: 101.41 },
      drying_score: 12,
      rank: 3000,
    });
  });

  it.each([
    ["a non-object", "nope"],
    ["no cells", { region: "riau", week: "2026-W42" }],
    ["a short row", { ...BODY, cells: [["a", 1, 2]] }],
    ["a text score", { ...BODY, cells: [["a", 1, 2, "3", 4]] }],
    ["a numeric id", { ...BODY, cells: [[7, 1, 2, 3, 4]] }],
  ])("rejects %s", (_, body) => {
    expect(() => parseAllCells(body)).toThrow(ResponseShapeError);
  });

  it("parses 3,769 rows", () => {
    const cells = Array.from({ length: 3769 }, (_, i) => [`c${i}`, 0.5, 101.4, 50, i + 1]);

    const parsed = parseAllCells({ ...BODY, cells });

    expect(parsed.cells).toHaveLength(3769);
  });
});

describe("fetchAllCells", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("reads the ranked fixture when the source is a fixture", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "fixture");

    const parsed = await fetchAllCells("riau");

    expect(parsed.cells).toHaveLength(200);
  });

  it("asks for the region with the bearer token", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(BODY)));
    vi.stubGlobal("fetch", fetchMock);

    const parsed = await fetchAllCells("riau");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/cells?region=riau");
    expect(parsed.cells).toHaveLength(2);
  });
});
