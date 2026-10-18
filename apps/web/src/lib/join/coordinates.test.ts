import { describe, expect, it } from "vitest";
import { parseCoordinates } from "./coordinates";

describe("parseCoordinates", () => {
  it.each([
    ["0.79990, 102.47081", { lat: 0.7999, lon: 102.47081 }],
    ["0.79990,102.47081", { lat: 0.7999, lon: 102.47081 }],
    ["0.79990 102.47081", { lat: 0.7999, lon: 102.47081 }],
    ["  -6.2, 106.8  ", { lat: -6.2, lon: 106.8 }],
    ["(0.5, 101.4)", { lat: 0.5, lon: 101.4 }],
  ])("reads %s", (text, expected) => {
    expect(parseCoordinates(text)).toEqual(expected);
  });

  it.each(["", "abc", "0.5", "91, 100", "-91, 100", "0, 181", "0, -181", "1, 2, 3", "1.2.3, 4"])(
    "rejects %s",
    (text) => {
      expect(parseCoordinates(text)).toBeNull();
    },
  );
});
