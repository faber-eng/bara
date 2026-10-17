import { describe, expect, it } from "vitest";
import type { RankingComponents } from "../contracts";
import { clampShare, componentBars } from "./componentBars";

const COMPONENTS: RankingComponents = {
  s1_anom_db: -1.5,
  rain_30d_mm: 20,
  rain_deficit_pct: 0.6,
  canal_dist_m: 0,
  peat_class: 2,
};

describe("componentBars", () => {
  it("returns four bars in a fixed order with units on the values", () => {
    const bars = componentBars(COMPONENTS);

    expect(bars.map((bar) => bar.key)).toEqual([
      "s1_anom_db",
      "rain_deficit_pct",
      "canal_dist_m",
      "peat_class",
    ]);
    expect(bars.map((bar) => bar.value)).toEqual(["-1.5 dB", "60%", "0 m", "class 2"]);
  });

  it("scales each bar into 0 to 1", () => {
    const shares = componentBars(COMPONENTS).map((bar) => bar.share);

    expect(shares[0]).toBeCloseTo(0.5);
    expect(shares[1]).toBeCloseTo(0.6);
    expect(shares[2]).toBe(1);
    expect(shares[3]).toBe(0.6);
  });

  it("shows an empty radar bar and n/a when there is no radar value", () => {
    const [radar] = componentBars({ ...COMPONENTS, s1_anom_db: null });

    expect(radar).toMatchObject({ share: 0, value: "n/a" });
  });

  it("keeps a wet anomaly and a negative deficit at zero", () => {
    const bars = componentBars({ ...COMPONENTS, s1_anom_db: 2, rain_deficit_pct: -0.4 });

    expect(bars[0]?.share).toBe(0);
    expect(bars[1]?.share).toBe(0);
  });
});

describe("clampShare", () => {
  it("clamps and treats NaN as zero", () => {
    expect(clampShare(2)).toBe(1);
    expect(clampShare(-2)).toBe(0);
    expect(clampShare(Number.NaN)).toBe(0);
  });
});
