import { describe, expect, it } from "vitest";
import type { CaseSummary, RankedCell, RankedDam } from "../../lib/contracts";
import {
  brokenDamCells,
  filterCounts,
  mainReason,
  matchesFilter,
  openCaseByCell,
} from "./rankedRows";

function cell(id: string, components: Partial<RankedCell["components"]> = {}): RankedCell {
  return {
    cell_id: id,
    region: "riau",
    week_start: "2026-10-12",
    centroid: { lat: 0, lon: 0 },
    components: {
      s1_anom_db: 0,
      rain_30d_mm: 100,
      rain_deficit_pct: 0,
      canal_dist_m: 50_000,
      peat_class: 1,
      ...components,
    },
    drying_score: 80,
    rank: 1,
    rank_change: null,
    stale_s1: false,
    explanation: null,
  } as RankedCell;
}

function summary(cellId: string, status: string): CaseSummary {
  return {
    case: { id: `case-${cellId}`, cell_id: cellId, status, type: "dam_risk" },
    next_deadline_at: null,
    task_status: null,
  } as unknown as CaseSummary;
}

describe("mainReason", () => {
  it("picks the component with the largest share", () => {
    expect(mainReason(cell("a", { s1_anom_db: -2.7, rain_deficit_pct: 0.3 }), new Set())).toEqual({
      kind: "radar",
      value: -2.7,
    });
    expect(mainReason(cell("b", { s1_anom_db: -0.3, rain_deficit_pct: 0.31 }), new Set())).toEqual({
      kind: "rain",
      value: 0.31,
    });
    expect(mainReason(cell("c", { canal_dist_m: 120, rain_deficit_pct: 0.2 }), new Set())).toEqual({
      kind: "canal",
      value: 120,
    });
  });

  it("names a broken dam in the cell before any component", () => {
    const dams = [{ cell_id: "a", last_state: "broken" }] as RankedDam[];
    expect(mainReason(cell("a", { s1_anom_db: -3 }), brokenDamCells(dams))).toEqual({
      kind: "brokenDam",
    });
  });

  it("gives no reason when no component contributes", () => {
    expect(mainReason(cell("a", { s1_anom_db: null, canal_dist_m: 1e9 }), new Set())).toBeNull();
  });
});

describe("filters", () => {
  it("counts cells with and without an open case, ignoring closed cases", () => {
    const open = openCaseByCell([summary("a", "assigned"), summary("b", "closed")]);
    const counts = filterCounts([cell("a"), cell("b"), cell("c")], open);

    expect(counts).toEqual({ all: 3, needsPerson: 2, caseOpen: 1 });
    expect(matchesFilter("caseOpen", open.has("a"))).toBe(true);
    expect(matchesFilter("needsPerson", open.has("a"))).toBe(false);
    expect(matchesFilter("all", false)).toBe(true);
  });
});
