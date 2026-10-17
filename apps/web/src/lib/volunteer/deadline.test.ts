import { describe, expect, it } from "vitest";
import { formatDeadline, isPastDeadline } from "./deadline";

describe("formatDeadline", () => {
  it("writes the Jakarta time in Indonesian", () => {
    expect(formatDeadline("2026-07-23T10:00:00Z", "id")).toBe("Kamis, 23 Juli, 17.00 WIB");
  });

  it("writes the Jakarta time in English", () => {
    expect(formatDeadline("2026-07-23T10:00:00Z", "en")).toBe("Thursday, 23 July, 17:00 WIB");
  });
});

describe("isPastDeadline", () => {
  it("is true at and after the deadline", () => {
    const deadline = "2026-07-23T10:00:00Z";
    expect(isPastDeadline(deadline, Date.parse(deadline) - 1)).toBe(false);
    expect(isPastDeadline(deadline, Date.parse(deadline))).toBe(true);
  });
});
