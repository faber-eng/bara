import { describe, expect, it } from "vitest";
import {
  clampOpacity,
  DEFAULT_MAP_TYPE,
  defaultEnabledLayers,
  definitionFor,
  enabledKinds,
  LAYER_DEFINITIONS,
  MAP_TYPES,
} from "./mapLayers";

describe("layer definitions", () => {
  it("offers drying, peat, burn scars and re-ignition, each with a legend", () => {
    expect(LAYER_DEFINITIONS.map((layer) => layer.id)).toEqual([
      "drying",
      "peat",
      "burn_scars",
      "reignition",
    ]);
    expect(LAYER_DEFINITIONS.every((layer) => layer.legend !== undefined)).toBe(true);
  });

  it("marks peat as the one layer that does not change by week", () => {
    expect(LAYER_DEFINITIONS.filter((layer) => !layer.weekly).map((layer) => layer.id)).toEqual([
      "peat",
    ]);
  });

  it("starts with the drying surface alone", () => {
    expect(enabledKinds(defaultEnabledLayers())).toEqual(["drying"]);
  });

  it("keeps the drying legend range 0 to 100", () => {
    expect(definitionFor("drying").legend).toEqual({
      kind: "ramp",
      low: "0 low",
      high: "100 high",
    });
  });
});

describe("drying default opacity", () => {
  it("lets the base map show through", () => {
    expect(definitionFor("drying").defaultOpacity).toBe(0.45);
  });
});

describe("clampOpacity", () => {
  it("keeps the value between 0 and 1", () => {
    expect(clampOpacity(-1)).toBe(0);
    expect(clampOpacity(0.4)).toBe(0.4);
    expect(clampOpacity(3)).toBe(1);
    expect(clampOpacity(Number.NaN)).toBe(0);
  });
});

describe("map types", () => {
  it("defaults to hybrid and offers roadmap, terrain and hybrid", () => {
    expect(DEFAULT_MAP_TYPE).toBe("hybrid");
    expect(MAP_TYPES.map((type) => type.id)).toEqual(["roadmap", "terrain", "hybrid"]);
  });
});
