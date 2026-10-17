import { describe, expect, it } from "vitest";
import { countdown, countdownLabel, formatSimTime } from "./simClock";

const NOW = Date.parse("2026-07-20T08:00:00+07:00");
const HOUR = 3_600_000;
const MINUTE = 60_000;

function deadlineAfter(ms: number): string {
  return new Date(NOW + ms).toISOString();
}

describe("countdown", () => {
  it("counts days and hours to a future deadline", () => {
    const result = countdown(deadlineAfter(81 * HOUR), NOW);

    expect(result).toEqual({ kind: "due", days: 3, hours: 9 });
    expect(countdownLabel(result)).toBe("Due in 3 d 9 h");
  });

  it("says less than 1 h under an hour", () => {
    const result = countdown(deadlineAfter(59 * MINUTE), NOW);

    expect(result).toEqual({ kind: "due", days: 0, hours: 0 });
    expect(countdownLabel(result)).toBe("Due in less than 1 h");
  });

  it("treats a deadline equal to now as overdue", () => {
    expect(countdown(deadlineAfter(0), NOW)).toEqual({ kind: "overdue", days: 0, hours: 0 });
  });

  it("counts hours past a deadline", () => {
    const result = countdown(deadlineAfter(-2 * HOUR), NOW);

    expect(result).toEqual({ kind: "overdue", days: 0, hours: 2 });
    expect(countdownLabel(result)).toBe("Overdue by 2 h");
  });

  it("includes days when overdue by more than a day", () => {
    expect(countdownLabel(countdown(deadlineAfter(-28 * HOUR), NOW))).toBe("Overdue by 1 d 4 h");
  });

  it("ignores a few milliseconds of drift", () => {
    expect(countdown(deadlineAfter(81 * HOUR - 5), NOW)).toEqual({
      kind: "due",
      days: 3,
      hours: 9,
    });
  });

  it("flips a due deadline to overdue after the clock moves 48 h", () => {
    const deadline = deadlineAfter(40 * HOUR);

    expect(countdown(deadline, NOW).kind).toBe("due");
    expect(countdown(deadline, NOW + 48 * HOUR).kind).toBe("overdue");
  });
});

describe("formatSimTime", () => {
  it("formats in Asia/Jakarta whatever the offset of the input", () => {
    expect(formatSimTime("2026-07-20T01:00:00Z")).toBe("20 Jul 2026, 08:00");
    expect(formatSimTime("2026-07-22T08:00:00+07:00")).toBe("22 Jul 2026, 08:00");
  });
});
