import { describe, expect, it } from "vitest";
import { parseWeekLabel, weekChoices } from "./weeks";

describe("weekChoices", () => {
  it("lists the latest week first and walks back one ISO week at a time", () => {
    expect(weekChoices("2026-W42", 4)).toEqual(["2026-W42", "2026-W41", "2026-W40", "2026-W39"]);
  });

  it("crosses a year boundary with the right week numbers", () => {
    expect(weekChoices("2027-W02", 4)).toEqual(["2027-W02", "2027-W01", "2026-W53", "2026-W52"]);
  });

  it("stops at the first week the public page holds", () => {
    expect(weekChoices("2026-W21", 5)).toEqual(["2026-W21", "2026-W20"]);
  });
});

describe("parseWeekLabel", () => {
  it("keeps an ISO week and drops anything else", () => {
    expect(parseWeekLabel("2026-W42")).toBe("2026-W42");
    expect(parseWeekLabel("2026-42")).toBeUndefined();
    expect(parseWeekLabel(42)).toBeUndefined();
  });
});
