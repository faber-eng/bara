import { afterEach, describe, expect, it, vi } from "vitest";
import { initOf } from "../../test-utils";
import { sendFailure } from "../ops/sendSomeone";
import { ApiError } from "./client";
import { sendPath, sendSomeone } from "./send";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

async function failureOf(response: Response): Promise<unknown> {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
  return sendSomeone("riau-1").catch((error: unknown) => error);
}

describe("sendSomeone", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts to the cell send route with no body and returns the ids", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(Response.json({ cell_id: "riau-1", message_id: "m1" }, { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendSomeone("riau-1");

    const call = fetchMock.mock.calls[0];
    expect(call?.[0]).toBe("/api/ops/cells/riau-1/send");
    expect(initOf(call).method).toBe("POST");
    expect(initOf(call).body).toBeUndefined();
    expect(result).toEqual({ cell_id: "riau-1", message_id: "m1" });
  });

  it("encodes the cell id in the path", () => {
    expect(sendPath("a/b")).toBe("/api/ops/cells/a%2Fb/send");
  });

  it("throws an ApiError carrying the status and detail", async () => {
    const failure = await failureOf(Response.json({ detail: "case_open" }, { status: 409 }));

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(409);
    expect((failure as ApiError).detail).toBe("case_open");
  });
});

describe("sendFailure", () => {
  it("maps case_open", () => {
    expect(sendFailure(new ApiError("x", 409, "case_open"))).toEqual({ kind: "case_open" });
  });

  it("maps region_without_flow", () => {
    expect(sendFailure(new ApiError("x", 409, "region_without_flow"))).toEqual({
      kind: "no_flow",
    });
  });

  it("keeps the server text on 429", () => {
    expect(sendFailure(new ApiError("x", 429, "Slow down for a minute."))).toEqual({
      kind: "rate_limited",
      detail: "Slow down for a minute.",
    });
  });

  it("maps 404 to not_ranked", () => {
    expect(sendFailure(new ApiError("x", 404, "unknown_cell"))).toEqual({ kind: "not_ranked" });
  });

  it.each([
    new ApiError("x", 502, "publish_failed"),
    new ApiError("x", 429, null),
    new ApiError("x", 409, "other"),
    new Error("network"),
  ])("maps other errors to failed", (error) => {
    expect(sendFailure(error)).toEqual({ kind: "failed" });
  });
});
