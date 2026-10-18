import fixture from "@fixtures/rankings_riau_200.json";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResponseShapeError } from "./parse";
import { fetchRankings, parseExplanation, parseRankings } from "./rankings";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

describe("parseRankings", () => {
  it("accepts the 200 cell fixture", () => {
    const rankings = parseRankings(fixture);

    expect(rankings.cells).toHaveLength(200);
    expect(rankings.dams).toHaveLength(50);
  });

  it("keeps null rank_change, null explanation and null s1", () => {
    const { cells } = parseRankings(fixture);

    expect(cells.some((cell) => cell.rank_change === null)).toBe(true);
    expect(cells.some((cell) => cell.explanation === null)).toBe(true);
    expect(cells.some((cell) => cell.components.s1_anom_db === null)).toBe(true);
  });

  it.each([
    ["a non-object", "nope"],
    ["missing cells", { ...fixture, cells: undefined }],
    ["a cell without rank", { ...fixture, cells: [{ ...fixture.cells[0], rank: "1" }] }],
    [
      "a bad peat class",
      {
        ...fixture,
        cells: [
          { ...fixture.cells[0], components: { ...fixture.cells[0]?.components, peat_class: 3 } },
        ],
      },
    ],
    ["a bad dam state", { ...fixture, dams: [{ ...fixture.dams[0], last_state: "gone" }] }],
    [
      "an explanation without text",
      { ...fixture, cells: [{ ...fixture.cells[0], explanation: { cited: {} } }] },
    ],
  ])("rejects %s", (_label, body) => {
    expect(() => parseRankings(body)).toThrow();
  });
});

describe("parseExplanation", () => {
  const base = { text: "Dry.", cited: {} };

  it("defaults a missing summary and points to null and empty", () => {
    expect(parseExplanation(base)).toMatchObject({ summary: null, points: [] });
    expect(parseExplanation({ ...base, summary: null, points: [] })).toMatchObject({
      summary: null,
      points: [],
    });
  });

  it("reads the summary and each point", () => {
    const points = [{ field: "rain_30d_mm", effect: "raises", text: "Little rain." }];
    expect(parseExplanation({ ...base, summary: "One.", points })).toMatchObject({
      summary: "One.",
      points,
    });
  });

  it.each([
    ["an unknown effect", [{ field: "a", effect: "big", text: "x" }]],
    ["a point without text", [{ field: "a", effect: "small" }]],
    ["points that are not a list", "nope"],
  ])("rejects %s", (_label, points) => {
    expect(() => parseExplanation({ ...base, points })).toThrow(ResponseShapeError);
  });
});

describe("fetchRankings", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("serves the fixture with no request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect((await fetchRankings("riau", undefined)).cells).toHaveLength(200);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("asks GET /api/rankings/riau when live", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(fixture));
    vi.stubGlobal("fetch", fetchMock);

    await fetchRankings("riau", undefined);

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/rankings/riau");
  });

  it("adds the week to the path when one is asked", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(fixture));
    vi.stubGlobal("fetch", fetchMock);

    await fetchRankings("congo_cuvette", "2026-W30");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/rankings/congo_cuvette?week=2026-W30");
  });
});
