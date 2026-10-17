import fixture from "@fixtures/cell_facts.json";
import { describe, expect, it, vi } from "vitest";
import { stubApi } from "../../test-utils";
import { fetchCellFacts, parseCellFacts } from "./cellFacts";
import { ResponseShapeError } from "./parse";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

describe("parseCellFacts", () => {
  it("reads the fixture", () => {
    const facts = parseCellFacts(fixture);

    expect(facts.cell_id).toBe("riau-0412");
    expect(facts.rank).toBe(1);
    expect(facts.components.canal_dist_m).toBe(180);
    expect(facts.explanation?.text).toContain("ranks first");
    expect(facts.nearby_dams[0]?.last_state).toBe("broken");
  });

  it("keeps a missing explanation as null", () => {
    expect(parseCellFacts({ ...fixture, explanation: null }).explanation).toBeNull();
  });

  it("rejects a body without a score", () => {
    expect(() => parseCellFacts({ ...fixture, drying_score: "high" })).toThrow(ResponseShapeError);
  });
});

describe("fetchCellFacts", () => {
  it("reads GET /api/cells/{id}", async () => {
    const fetchMock = stubApi({ "GET /api/cells/riau-0412": () => Response.json(fixture) });

    const facts = await fetchCellFacts("riau-0412");

    expect(facts.drying_score).toBe(91.4);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
