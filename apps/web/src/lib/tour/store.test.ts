import { beforeEach, describe, expect, it, vi } from "vitest";
import { clampStep, LAST_STEP } from "./steps";
import { finishTour, getTourSnapshot, goToStep, skipTour, startTour } from "./store";

describe("tour store", () => {
  beforeEach(() => {
    localStorage.clear();
    finishTour();
  });

  it("starts open at the first step", () => {
    startTour();

    expect(getTourSnapshot()).toEqual({ open: true, step: 0 });
  });

  it("keeps the step when skipped so it can resume", () => {
    goToStep(3);
    skipTour();

    expect(getTourSnapshot()).toEqual({ open: false, step: 3 });
  });

  it("resets to the first step when finished", () => {
    goToStep(4);
    finishTour();

    expect(getTourSnapshot()).toEqual({ open: false, step: 0 });
  });

  it("restores the saved step after a reload", async () => {
    localStorage.setItem("bara.tour", JSON.stringify({ open: true, step: 5 }));
    vi.resetModules();
    const fresh = await import("./store");

    expect(fresh.getTourSnapshot()).toEqual({ open: true, step: 5 });
  });

  it("falls back to the start on corrupt storage", async () => {
    localStorage.setItem("bara.tour", "{not json");
    vi.resetModules();
    const fresh = await import("./store");

    expect(fresh.getTourSnapshot()).toEqual({ open: false, step: 0 });
  });

  it("still works when storage throws", async () => {
    const blocked = () => {
      throw new Error("blocked");
    };
    vi.stubGlobal("localStorage", { getItem: blocked, setItem: blocked });

    expect(() => goToStep(2)).not.toThrow();
    expect(getTourSnapshot().step).toBe(2);
    vi.resetModules();
    const fresh = await import("./store");
    expect(fresh.getTourSnapshot()).toEqual({ open: false, step: 0 });
    vi.unstubAllGlobals();
  });

  it("clamps a step outside the tour", () => {
    expect(clampStep(99)).toBe(LAST_STEP);
    expect(clampStep(-4)).toBe(0);
    expect(clampStep(Number.NaN)).toBe(0);
  });
});
