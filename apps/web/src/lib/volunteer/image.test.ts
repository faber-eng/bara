import { describe, expect, it } from "vitest";
import { fitWithin } from "./image";

describe("fitWithin", () => {
  it("keeps a photo that is already small enough", () => {
    expect(fitWithin({ width: 1200, height: 800 }, 1600)).toEqual({ width: 1200, height: 800 });
    expect(fitWithin({ width: 1600, height: 1600 }, 1600)).toEqual({ width: 1600, height: 1600 });
  });

  it("scales a landscape photo so the long edge is 1600", () => {
    expect(fitWithin({ width: 4000, height: 3000 }, 1600)).toEqual({ width: 1600, height: 1200 });
  });

  it("scales a portrait photo so the long edge is 1600", () => {
    expect(fitWithin({ width: 3000, height: 4000 }, 1600)).toEqual({ width: 1200, height: 1600 });
  });

  it("rounds to whole pixels", () => {
    expect(fitWithin({ width: 4001, height: 3001 }, 1600)).toEqual({ width: 1600, height: 1200 });
  });
});
