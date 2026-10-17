import { afterEach, describe, expect, it, vi } from "vitest";
import { isValidNote, reviewCase, reviewPath, trimmedNote } from "./review";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const CASE = {
  id: "case-1",
  type: "dam_risk",
  region: "riau",
  cell_id: "riau-1",
  dam_id: null,
  event_id: null,
  status: "closed",
  risk: { drying_score: 80, p_reignite: null },
  opened_at: "2026-10-01T00:00:00Z",
  closed_by: "ops-1",
  closed_at: "2026-10-02T00:00:00Z",
  history_flags: { smoke_seen: false },
  example: false,
};

describe("review note", () => {
  it.each([
    ["", false],
    ["   ", false],
    ["ok", true],
    ["a".repeat(500), true],
    ["a".repeat(501), false],
  ])("%j valid -> %s", (note, expected) => {
    expect(isValidNote(note)).toBe(expected);
  });

  it("trims the note", () => {
    expect(trimmedNote("  done \n")).toBe("done");
  });
});

describe("reviewCase", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("posts the action and the trimmed note to the review route", async () => {
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(CASE));
    vi.stubGlobal("fetch", fetchMock);

    const result = await reviewCase("case-1", { action: "close", note: "  fixed on site " });

    expect(fetchMock.mock.calls[0]?.[0]).toBe(reviewPath("case-1"));
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ action: "close", note: "fixed on site" });
    expect(result?.status).toBe("closed");
  });

  it("sends nothing from the fixture source", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect(await reviewCase("case-1", { action: "assign", note: "go" })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
