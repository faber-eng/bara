import { describe, expect, it } from "vitest";
import {
  buildMapLayers,
  clampOpacity,
  DEFAULT_MAP_TYPE,
  layerOpacity,
  MAP_TYPES,
} from "./mapLayers";

const TILES = {
  layer: "drying",
  region: "riau",
  week: "2026-W42",
  url_template: "https://t.example/{z}/{x}/{y}",
} as const;

describe("buildMapLayers", () => {
  it("lists the drying layer with its template, default opacity and legend", () => {
    const layers = buildMapLayers(TILES);

    expect(layers).toHaveLength(1);
    expect(layers[0]).toMatchObject({
      id: "drying",
      label: "Drying score",
      urlTemplate: "https://t.example/{z}/{x}/{y}",
      defaultOpacity: 0.7,
      legend: { low: "0", high: "100" },
    });
  });

  it("lists no layers until the tiles load", () => {
    expect(buildMapLayers(undefined)).toEqual([]);
  });
});

describe("layerOpacity", () => {
  it("uses the default until the user moves the slider", () => {
    const [layer] = buildMapLayers(TILES);
    if (layer === undefined) throw new Error("no layer");

    expect(layerOpacity(layer, {})).toBe(0.7);
    expect(layerOpacity(layer, { drying: 0.2 })).toBe(0.2);
    expect(layerOpacity(layer, { drying: 0 })).toBe(0);
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
