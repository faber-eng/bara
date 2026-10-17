import { afterEach, describe, expect, it, vi } from "vitest";
import { sourceFor } from "./sources";

describe("sourceFor", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("defaults the ops reads, the clock and the tiles to live and the brigade inbox to its fixture", () => {
    vi.unstubAllEnvs();

    expect(sourceFor("rankings")).toBe("live");
    expect(sourceFor("cases")).toBe("live");
    expect(sourceFor("caseDetail")).toBe("live");
    expect(sourceFor("escalations")).toBe("fixture");
    expect(sourceFor("tiles")).toBe("live");
    expect(sourceFor("clock")).toBe("live");
  });

  it("lets the environment switch one area to live", () => {
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");

    expect(sourceFor("escalations")).toBe("live");
  });

  it("ignores an unknown value", () => {
    vi.stubEnv("VITE_SOURCE_CASES", "maybe");

    expect(sourceFor("cases")).toBe("live");
  });
});
