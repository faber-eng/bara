import { afterEach, describe, expect, it, vi } from "vitest";
import { sourceFor } from "./sources";

describe("sourceFor", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("defaults the clock and the tiles to live and the rest to their fixture", () => {
    vi.unstubAllEnvs();

    expect(sourceFor("rankings")).toBe("fixture");
    expect(sourceFor("cases")).toBe("fixture");
    expect(sourceFor("tiles")).toBe("live");
    expect(sourceFor("clock")).toBe("live");
  });

  it("lets the environment switch one area to live", () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");

    expect(sourceFor("rankings")).toBe("live");
    expect(sourceFor("cases")).toBe("fixture");
  });

  it("ignores an unknown value", () => {
    vi.stubEnv("VITE_SOURCE_CASES", "maybe");

    expect(sourceFor("cases")).toBe("fixture");
  });
});
