import { describe, expect, it } from "vitest";
import { isNearBottom, scrollDecision } from "./scroll";

describe("isNearBottom", () => {
  it("is true at the very bottom", () => {
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 600, clientHeight: 400 })).toBe(true);
  });

  it("is true within the threshold", () => {
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 560, clientHeight: 400 })).toBe(true);
  });

  it("is false once the reader scrolled up", () => {
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 200, clientHeight: 400 })).toBe(false);
  });

  it("is true when nothing overflows", () => {
    expect(isNearBottom({ scrollHeight: 300, scrollTop: 0, clientHeight: 400 })).toBe(true);
  });
});

describe("scrollDecision", () => {
  it("follows a new message while the reader is at the bottom", () => {
    expect(scrollDecision({ pinned: true, newestIsMine: false })).toBe("follow");
  });

  it("follows the volunteer's own message even when scrolled up", () => {
    expect(scrollDecision({ pinned: false, newestIsMine: true })).toBe("follow");
  });

  it("only notifies when the reader scrolled up and the reply is not theirs", () => {
    expect(scrollDecision({ pinned: false, newestIsMine: false })).toBe("notify");
  });
});
