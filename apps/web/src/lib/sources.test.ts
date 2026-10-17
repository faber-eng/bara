import { afterEach, describe, expect, it, vi } from "vitest";
import { sourceFor } from "./sources";

describe("sourceFor", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("defaults the clock to live and the rest to their fixture", () => {
    vi.unstubAllEnvs();

    expect(sourceFor("rankings")).toBe("fixture");
    expect(sourceFor("cases")).toBe("fixture");
    expect(sourceFor("tiles")).toBe("fixture");
    expect(sourceFor("clock")).toBe("live");
  });

  it("lets the environment switch one area to live", () => {
    vi.stubEnv("VITE_SOURCE_TILES", "live");

    expect(sourceFor("tiles")).toBe("live");
    expect(sourceFor("rankings")).toBe("fixture");
  });

  it("ignores an unknown value", () => {
    vi.stubEnv("VITE_SOURCE_TILES", "maybe");

    expect(sourceFor("tiles")).toBe("fixture");
  });
});
