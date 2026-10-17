import { describe, expect, it } from "vitest";
import { isSafeMapUrl, mapPoint } from "./pack";

describe("mapPoint", () => {
  it("reads lat and lon from a Google Maps search url", () => {
    expect(mapPoint("https://www.google.com/maps/search/?api=1&query=0.533,102.204")).toEqual({
      lat: 0.533,
      lon: 102.204,
    });
  });

  it.each([
    ["no query", "https://www.google.com/maps"],
    ["a place name", "https://www.google.com/maps/search/?api=1&query=Pekanbaru"],
    ["one number", "https://www.google.com/maps/search/?api=1&query=0.5"],
    ["not a url", "::"],
  ])("returns null for %s", (_label, url) => {
    expect(mapPoint(url)).toBeNull();
  });
});

describe("isSafeMapUrl", () => {
  it("allows https only", () => {
    expect(isSafeMapUrl("https://maps.example/x")).toBe(true);
    expect(isSafeMapUrl("javascript:alert(1)")).toBe(false);
    expect(isSafeMapUrl("http://maps.example/x")).toBe(false);
  });
});
