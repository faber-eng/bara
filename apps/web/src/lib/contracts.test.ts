import { describe, expect, it } from "vitest";
import cases from "../../../../data/fixtures/cases.json";
import clock from "../../../../data/fixtures/clock.json";
import type { CaseSummary, ClockState } from "./contracts";

const typedClock: ClockState = clock;

describe("contract fixtures", () => {
  it("clock.json has the ClockState keys", () => {
    expect(Object.keys(typedClock).sort()).toEqual(["judge_mode", "now", "offset_seconds"]);
  });

  it("cases.json entries have the CaseSummary keys and the example flag", () => {
    const expected: (keyof CaseSummary)[] = ["case", "next_deadline_at", "task_status"];

    for (const entry of cases) {
      expect(Object.keys(entry).sort()).toEqual(expected);
      expect(entry.case.example).toBe(true);
    }
  });
});
