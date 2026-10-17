import fixture from "@fixtures/cases.json";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchCases, parseCaseSummaries } from "./cases";
import { advanceClock, resetClock } from "./clock";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

describe("parseCaseSummaries", () => {
  it("accepts the cases fixture", () => {
    expect(parseCaseSummaries(fixture)).toHaveLength(9);
  });

  it.each([
    ["a non-array", { cases: [] }],
    ["an unknown status", [{ ...fixture[0], case: { ...fixture[0]?.case, status: "weird" } }]],
    ["a missing case", [{ next_deadline_at: null, task_status: null }]],
    ["a numeric deadline", [{ ...fixture[0], next_deadline_at: 5 }]],
    ["an unknown task status", [{ ...fixture[0], task_status: "later" }]],
  ])("rejects %s", (_label, body) => {
    expect(() => parseCaseSummaries(body)).toThrow();
  });
});

describe("fetchCases", () => {
  beforeEach(async () => {
    await resetClock();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("serves the fixture with no request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const cases = await fetchCases("riau");

    expect(cases).toHaveLength(9);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("asks GET /api/cases for the region when live", async () => {
    vi.stubEnv("VITE_SOURCE_CASES", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(fixture));
    vi.stubGlobal("fetch", fetchMock);

    await fetchCases("riau");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/cases?region=riau");
  });

  it("flips an assigned case to overdue once the fixture clock passes its deadline", async () => {
    const before = await fetchCases("riau");
    const assigned = before.find((entry) => entry.case.id === "case-0001");
    expect(assigned?.case.status).toBe("assigned");
    expect(assigned?.task_status).toBe("open");

    await advanceClock(96);
    const after = await fetchCases("riau");

    const flipped = after.find((entry) => entry.case.id === "case-0001");
    expect(flipped?.case.status).toBe("overdue");
    expect(flipped?.task_status).toBe("overdue");
  });
});
