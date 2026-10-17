import { describe, expect, it } from "vitest";
import { tileUrl } from "./tileUrl";

const TEMPLATE = "https://tiles.example/v1/{z}/{x}/{y}";

describe("tileUrl", () => {
  it("fills the template", () => {
    expect(tileUrl(TEMPLATE, 3, 4, 5)).toBe("https://tiles.example/v1/5/3/4");
  });

  it("wraps x around the world", () => {
    expect(tileUrl(TEMPLATE, -1, 1, 2)).toBe("https://tiles.example/v1/2/3/1");
    expect(tileUrl(TEMPLATE, 5, 1, 2)).toBe("https://tiles.example/v1/2/1/1");
  });

  it("returns null above or below the world", () => {
    expect(tileUrl(TEMPLATE, 0, -1, 2)).toBeNull();
    expect(tileUrl(TEMPLATE, 0, 4, 2)).toBeNull();
  });
});
