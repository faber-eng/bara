import { beforeEach, describe, expect, it, vi } from "vitest";
import { getIdToken } from "../auth";
import { setJudgeMode } from "../judge/store";
import { brigadeContactId } from "./contact";

vi.mock("../auth", () => ({ getIdToken: vi.fn() }));

function tokenFor(uid: string, provider: string): string {
  return `h.${btoa(JSON.stringify({ sub: uid, firebase: { sign_in_provider: provider } }))}.s`;
}

describe("brigadeContactId", () => {
  beforeEach(() => {
    setJudgeMode(false);
    localStorage.clear();
  });

  it("uses the uid of a real user outside judge mode", async () => {
    vi.mocked(getIdToken).mockResolvedValue(tokenFor("uid-b", "google.com"));
    expect(await brigadeContactId()).toBe("uid-b");
  });

  it("keeps the uid of a real user while judge mode is on", async () => {
    setJudgeMode(true);
    vi.mocked(getIdToken).mockResolvedValue(tokenFor("uid-b", "google.com"));
    expect(await brigadeContactId()).toBe("uid-b");
  });

  it("uses the example contact for an anonymous visitor in judge mode", async () => {
    setJudgeMode(true);
    vi.mocked(getIdToken).mockResolvedValue(tokenFor("anon-1", "anonymous"));
    expect(await brigadeContactId()).toBe("contact-daops-pekanbaru");
  });

  it("fails when the token has no user id", async () => {
    vi.mocked(getIdToken).mockResolvedValue("not-a-jwt");
    await expect(brigadeContactId()).rejects.toThrow("no user id");
  });
});
