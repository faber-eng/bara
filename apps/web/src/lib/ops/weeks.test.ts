import { describe, expect, it } from "vitest";
import {
  effectiveWeek,
  FIRST_WEEK,
  neighbourWeeks,
  parseWeek,
  requestWeek,
  selectedWeek,
  weekRange,
} from "./weeks";

describe("weekRange", () => {
  it("runs from W20 to the latest week", () => {
    const weeks = weekRange("2026-W42");

    expect(weeks).toHaveLength(23);
    expect(weeks[0]).toBe(FIRST_WEEK);
    expect(weeks.at(-1)).toBe("2026-W42");
  });

  it("is only the first week while the latest week is unknown or before it", () => {
    expect(weekRange(undefined)).toEqual([FIRST_WEEK]);
    expect(weekRange("2026-W10")).toEqual([FIRST_WEEK]);
  });

  it("crosses the year end", () => {
    const weeks = weekRange("2027-W02");

    expect(weeks).toContain("2026-W52");
    expect(weeks).toContain("2026-W53");
    expect(weeks).toContain("2027-W01");
    expect(weeks.at(-1)).toBe("2027-W02");
  });
});

describe("parseWeek", () => {
  it.each([
    ["2026-W20", "2026-W20"],
    ["2026-W53", "2026-W53"],
    ["2027-W53", undefined],
    ["2026-W00", undefined],
    ["2026-20", undefined],
    [42, undefined],
    [undefined, undefined],
  ])("%s -> %s", (value, expected) => {
    expect(parseWeek(value)).toBe(expected);
  });
});

describe("neighbourWeeks", () => {
  const weeks = weekRange("2026-W23");

  it("returns both sides in the middle", () => {
    expect(neighbourWeeks(weeks, "2026-W21")).toEqual(["2026-W20", "2026-W22"]);
  });

  it("returns one side at the ends", () => {
    expect(neighbourWeeks(weeks, "2026-W20")).toEqual(["2026-W21"]);
    expect(neighbourWeeks(weeks, "2026-W23")).toEqual(["2026-W22"]);
  });

  it("returns none for a week outside the range", () => {
    expect(neighbourWeeks(weeks, "2026-W40")).toEqual([]);
  });
});

describe("requestWeek and selectedWeek", () => {
  it("asks for the latest week with no week so the cache key stays one", () => {
    expect(requestWeek("2026-W42", "2026-W42")).toBeUndefined();
    expect(requestWeek("2026-W41", "2026-W42")).toBe("2026-W41");
    expect(requestWeek(undefined, "2026-W42")).toBeUndefined();
  });

  it("shows the latest week when none is chosen", () => {
    expect(selectedWeek(undefined, "2026-W42")).toBe("2026-W42");
    expect(selectedWeek("2026-W30", "2026-W42")).toBe("2026-W30");
  });
});

describe("effectiveWeek", () => {
  it("drops a week outside W20 to the latest and the latest itself", () => {
    expect(effectiveWeek("2025-W01", "2026-W42")).toBeUndefined();
    expect(effectiveWeek("2026-W50", "2026-W42")).toBeUndefined();
    expect(effectiveWeek("2026-W42", "2026-W42")).toBeUndefined();
  });

  it("keeps a week inside the range, and any week until the latest is known", () => {
    expect(effectiveWeek("2026-W30", "2026-W42")).toBe("2026-W30");
    expect(effectiveWeek("2026-W30", undefined)).toBe("2026-W30");
    expect(effectiveWeek(undefined, "2026-W42")).toBeUndefined();
  });
});
