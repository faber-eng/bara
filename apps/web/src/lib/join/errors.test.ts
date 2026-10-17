import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { classifyJoinError } from "./errors";

describe("classifyJoinError", () => {
  it("maps the API answers to a failure", () => {
    expect(classifyJoinError(new ApiError("x", 403, "invalid_invite_code"))).toBe("wrong_code");
    expect(classifyJoinError(new ApiError("x", 403, "anonymous_not_allowed"))).toBe(
      "not_signed_in",
    );
    expect(classifyJoinError(new ApiError("x", 401, "unauthorized"))).toBe("not_signed_in");
    expect(classifyJoinError(new ApiError("x", 429, "too_many_attempts"))).toBe(
      "too_many_attempts",
    );
    expect(classifyJoinError(new ApiError("x", 503, "join_unavailable"))).toBe("unavailable");
    expect(classifyJoinError(new ApiError("x", 500, null))).toBe("unknown");
  });

  it("treats a thrown network error as network", () => {
    expect(classifyJoinError(new TypeError("Failed to fetch"))).toBe("network");
  });

  it("does not guess on a plain 403", () => {
    expect(classifyJoinError(new ApiError("x", 403, "forbidden"))).toBe("unknown");
  });
});
