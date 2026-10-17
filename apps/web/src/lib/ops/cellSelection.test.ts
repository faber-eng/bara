import { describe, expect, it } from "vitest";
import type { RankedCell, RankedDam } from "../contracts";
import { damCellId, parseCellId, rowSelection, selectedCell } from "./cellSelection";

function cell(id: string, rank: number): RankedCell {
  return {
    cell_id: id,
    region: "riau",
    week_start: "2026-10-12",
    centroid: { lat: 0.5, lon: 102.1 },
    components: {
      s1_anom_db: null,
      rain_30d_mm: 1,
      rain_deficit_pct: 0.5,
      canal_dist_m: 10,
      peat_class: 1,
    },
    drying_score: 90,
    rank,
    rank_change: null,
    stale_s1: false,
    explanation: null,
  };
}

const CELLS = [cell("riau-1", 1), cell("riau-2", 2)];

describe("selectedCell", () => {
  it("finds the ranked cell for an id", () => {
    expect(selectedCell(CELLS, "riau-2")?.rank).toBe(2);
  });

  it("is undefined for no id or an unranked id", () => {
    expect(selectedCell(CELLS, undefined)).toBeUndefined();
    expect(selectedCell(CELLS, "riau-9")).toBeUndefined();
  });
});

describe("rowSelection", () => {
  it("marks only the row whose cell is selected", () => {
    expect(rowSelection("riau-1", "riau-1")).toBe(true);
    expect(rowSelection("riau-1", "riau-2")).toBe(false);
    expect(rowSelection("riau-1", undefined)).toBe(false);
  });
});

describe("damCellId", () => {
  it("opens the panel of the cell that holds the dam", () => {
    const dam = { dam_id: "d1", cell_id: "riau-2" } as RankedDam;

    expect(damCellId(dam)).toBe("riau-2");
  });
});

describe("parseCellId", () => {
  it("keeps a non-empty string and drops anything else", () => {
    expect(parseCellId("riau-1")).toBe("riau-1");
    expect(parseCellId("")).toBeUndefined();
    expect(parseCellId(4)).toBeUndefined();
  });
});
