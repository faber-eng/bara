import { describe, expect, it } from "vitest";
import { baseContentType } from "./recorder";

describe("baseContentType", () => {
  it("drops the codec parameter", () => {
    expect(baseContentType("audio/webm;codecs=opus")).toBe("audio/webm");
    expect(baseContentType("audio/mp4")).toBe("audio/mp4");
  });
});
