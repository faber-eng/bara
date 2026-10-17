import { describe, expect, it } from "vitest";
import { buildCellIndex, CELL_SIZE_M, cellRing, cellSquare, findCellAt } from "./cellGrid";

const CELLS = [
  { cell_id: "a", centroid: { lat: 0.5, lon: 102.1 } },
  { cell_id: "b", centroid: { lat: 0.5, lon: 102.2 } },
  { cell_id: "c", centroid: { lat: 0.6, lon: 102.1 } },
];

describe("cellSquare", () => {
  it("spans 1 km around the centroid", () => {
    const square = cellSquare({ lat: 0, lon: 102 });

    const heightM = (square.north - square.south) * 111_320;
    const widthM = (square.east - square.west) * 111_320;
    expect(CELL_SIZE_M).toBe(1000);
    expect(heightM).toBeCloseTo(1000, 0);
    expect(widthM).toBeCloseTo(1000, 0);
  });

  it("widens in degrees of longitude away from the equator", () => {
    const equator = cellSquare({ lat: 0, lon: 102 });
    const north = cellSquare({ lat: 60, lon: 102 });

    expect(north.east - north.west).toBeGreaterThan((equator.east - equator.west) * 1.9);
  });
});

describe("cellRing", () => {
  it("is a closed ring of five points", () => {
    const ring = cellRing({ lat: 0.5, lon: 102.1 });

    expect(ring).toHaveLength(5);
    expect(ring[0]).toEqual(ring[4]);
  });
});

describe("findCellAt", () => {
  const index = buildCellIndex(CELLS);

  it("finds the cell that contains the point", () => {
    expect(findCellAt(index, { lat: 0.5002, lon: 102.1002 }, 0)?.cell_id).toBe("a");
    expect(findCellAt(index, { lat: 0.6001, lon: 102.0999 }, 0)?.cell_id).toBe("c");
  });

  it("returns undefined outside every cell", () => {
    expect(findCellAt(index, { lat: 0.55, lon: 102.15 }, 0)).toBeUndefined();
  });

  it("accepts a point within the tolerance and picks the nearest cell", () => {
    const point = { lat: 0.5, lon: 102.1055 };

    expect(findCellAt(index, point, 0)).toBeUndefined();
    expect(findCellAt(index, point, 0.01)?.cell_id).toBe("a");
  });

  it("returns undefined for an empty index", () => {
    expect(findCellAt(buildCellIndex([]), { lat: 0, lon: 0 }, 0.01)).toBeUndefined();
  });

  it("stays a lookup, not a scan, for thousands of cells", () => {
    const many = Array.from({ length: 3769 }, (_, i) => ({
      cell_id: `c${i}`,
      centroid: { lat: -1 + (i % 60) * 0.02, lon: 101 + Math.floor(i / 60) * 0.02 },
    }));
    const big = buildCellIndex(many);

    expect(findCellAt(big, { lat: -1 + 7 * 0.02, lon: 101 + 9 * 0.02 }, 0)?.cell_id).toBe("c547");
  });
});
