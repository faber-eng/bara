import { describe, expect, it } from "vitest";
import { isRealUser, readTokenIdentity } from "./tokenIdentity";

function tokenWith(payload: object): string {
  const body = btoa(JSON.stringify(payload)).replace(/\+/g, "-").replace(/\//g, "_");
  return `header.${body}.signature`;
}

describe("readTokenIdentity", () => {
  it("reads the uid and the sign-in provider", () => {
    const token = tokenWith({ sub: "u-1", firebase: { sign_in_provider: "google.com" } });
    expect(readTokenIdentity(token)).toEqual({ uid: "u-1", provider: "google.com" });
  });

  it("returns a null provider when the token has none", () => {
    expect(readTokenIdentity(tokenWith({ sub: "u-1" }))).toEqual({ uid: "u-1", provider: null });
  });

  it("returns null for a token that is not a JWT", () => {
    expect(readTokenIdentity("token-1")).toBeNull();
    expect(readTokenIdentity("a.%%%.c")).toBeNull();
  });

  it("returns null when the payload has no subject", () => {
    expect(readTokenIdentity(tokenWith({ firebase: {} }))).toBeNull();
  });
});

describe("isRealUser", () => {
  it("is true for Google and false for anonymous or unknown", () => {
    expect(isRealUser({ uid: "u", provider: "google.com" })).toBe(true);
    expect(isRealUser({ uid: "u", provider: "anonymous" })).toBe(false);
    expect(isRealUser({ uid: "u", provider: null })).toBe(false);
    expect(isRealUser(null)).toBe(false);
  });
});
