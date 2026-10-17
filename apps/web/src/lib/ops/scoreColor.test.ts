import { describe, expect, it } from "vitest";
import { RISK_COLORS, scoreColor } from "./scoreColor";

describe("scoreColor", () => {
  it("maps 0 to 100 onto five steps", () => {
    expect(scoreColor(0)).toBe(RISK_COLORS[0]);
    expect(scoreColor(19.9)).toBe(RISK_COLORS[0]);
    expect(scoreColor(20)).toBe(RISK_COLORS[1]);
    expect(scoreColor(79.9)).toBe(RISK_COLORS[3]);
    expect(scoreColor(100)).toBe(RISK_COLORS[4]);
  });

  it("clamps out-of-range scores", () => {
    expect(scoreColor(-5)).toBe(RISK_COLORS[0]);
    expect(scoreColor(140)).toBe(RISK_COLORS[4]);
  });
});
