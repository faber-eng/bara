import { describe, expect, it } from "vitest";
import { areaKm2, draftState, MAX_AREA_KM2, toGeoJsonPolygon } from "./polygon";

function square(west: number, south: number, side: number) {
  return [
    { lat: south, lon: west },
    { lat: south, lon: west + side },
    { lat: south + side, lon: west + side },
    { lat: south + side, lon: west },
  ];
}

describe("areaKm2", () => {
  it("measures a 0.09 degree square near the equator as about 100 km2", () => {
    expect(areaKm2(square(102, 0.5, 0.09))).toBeGreaterThan(97);
    expect(areaKm2(square(102, 0.5, 0.09))).toBeLessThan(103);
  });

  it("is zero below three corners", () => {
    expect(areaKm2(square(102, 0.5, 0.09).slice(0, 2))).toBe(0);
  });
});

describe("toGeoJsonPolygon", () => {
  it("closes the ring in lon, lat order", () => {
    const polygon = toGeoJsonPolygon(square(102, 0.5, 0.09));
    const ring = polygon.coordinates[0] ?? [];
    expect(ring).toHaveLength(5);
    expect(ring[0]).toEqual([102, 0.5]);
    expect(ring[4]).toEqual(ring[0]);
  });
});

describe("draftState", () => {
  it("walks from empty to ready and flags a polygon over the limit", () => {
    expect(draftState([])).toBe("empty");
    expect(draftState(square(102, 0.5, 0.09).slice(0, 2))).toBe("too_few");
    expect(draftState(square(102, 0.5, 0.09))).toBe("ready");
    expect(areaKm2(square(102, 0, 0.6))).toBeGreaterThan(MAX_AREA_KM2);
    expect(draftState(square(102, 0, 0.6))).toBe("too_large");
  });
});
