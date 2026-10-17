import { describe, expect, it } from "vitest";
import type { PublicSummary } from "../contracts";
import { statReadings } from "./stats";

const SUMMARY: PublicSummary = {
  region: "riau",
  week: "2026-W42",
  high_risk_cells: 12,
  dams_broken: 0,
  cases_open: 4,
  cases_escalated: 1,
  cases_closed: 2,
  median_days_to_repair: null,
  tasks_on_time_pct: 80,
  data_as_of: { s1_pass_date: "2026-10-12", ranking_run_at: "2026-10-11T17:00:00Z" },
};

describe("statReadings", () => {
  it("returns the five stats in order and keeps a zero and a null as they are", () => {
    const readings = statReadings(SUMMARY, false);

    expect(readings.map((reading) => reading.key)).toEqual([
      "high_risk_cells",
      "dams_broken",
      "cases_open",
      "median_days_to_repair",
      "tasks_on_time_pct",
    ]);
    expect(readings[1]?.value).toBe(0);
    expect(readings[3]?.value).toBeNull();
    expect(readings[2]?.escalated).toBe(1);
  });

  it("shows only the ranking stat for a ranking-only region", () => {
    expect(statReadings(SUMMARY, true).map((reading) => reading.key)).toEqual(["high_risk_cells"]);
  });
});
