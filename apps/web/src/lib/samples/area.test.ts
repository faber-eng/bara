import { describe, expect, it } from "vitest";
import { summarizeArea } from "./area";

const square = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "Riau area 1" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [102.1, 0.55],
            [102.18, 0.55],
            [102.18, 0.62],
            [102.1, 0.62],
            [102.1, 0.55],
          ],
        ],
      },
    },
  ],
};

describe("summarizeArea", () => {
  it("names the area and counts its corners without the closing point", () => {
    expect(summarizeArea(square)).toEqual({ name: "Riau area 1", vertices: 4 });
  });

  it("rejects an empty collection", () => {
    expect(() => summarizeArea({ type: "FeatureCollection", features: [] })).toThrow();
  });

  it("rejects a point", () => {
    const point = {
      ...square,
      features: [{ ...square.features[0], geometry: { type: "Point", coordinates: [1, 2] } }],
    };
    expect(() => summarizeArea(point)).toThrow();
  });

  it("rejects something that is not an object", () => {
    expect(() => summarizeArea("x")).toThrow();
  });
});
