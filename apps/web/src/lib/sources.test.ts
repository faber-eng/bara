import { afterEach, describe, expect, it, vi } from "vitest";
import { sourceFor } from "./sources";

describe("sourceFor", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("defaults every area to live", () => {
    vi.unstubAllEnvs();

    expect(sourceFor("rankings")).toBe("live");
    expect(sourceFor("cases")).toBe("live");
    expect(sourceFor("caseDetail")).toBe("live");
    expect(sourceFor("escalations")).toBe("live");
    expect(sourceFor("tiles")).toBe("live");
    expect(sourceFor("clock")).toBe("live");
  });

  it("lets the environment switch one area to its fixture", () => {
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "fixture");

    expect(sourceFor("escalations")).toBe("fixture");
  });

  it("ignores an unknown value", () => {
    vi.stubEnv("VITE_SOURCE_CASES", "maybe");

    expect(sourceFor("cases")).toBe("live");
  });
});
