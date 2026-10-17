import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { areaErrorKind } from "./errors";

describe("areaErrorKind", () => {
  it.each([
    [429, "area_rank_limit", "limit"],
    [503, "area_busy", "busy"],
    [504, "area_timeout", "timeout"],
    [422, "area_too_large", "too_large"],
    [422, "outside_regions", "outside"],
    [422, "invalid_polygon: the ring must be closed", "invalid"],
    [502, "area_source_failed", "failed"],
  ])("maps %s %s to %s", (status, detail, kind) => {
    expect(areaErrorKind(new ApiError("x", status, detail))).toBe(kind);
  });

  it("treats an abort as a timeout and anything else as failed", () => {
    expect(areaErrorKind(new DOMException("a", "AbortError"))).toBe("timeout");
    expect(areaErrorKind(new Error("x"))).toBe("failed");
  });
});
