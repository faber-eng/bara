import { beforeEach, describe, expect, it, vi } from "vitest";
import { setJudgeMode } from "../judge/store";
import { brigadeContactId } from "./contact";

vi.mock("../auth", () => ({ getUid: vi.fn().mockResolvedValue("uid-brigade-1") }));

describe("brigadeContactId", () => {
  beforeEach(() => {
    setJudgeMode(false);
    localStorage.clear();
  });

  it("uses the signed-in uid outside judge mode", async () => {
    expect(await brigadeContactId()).toBe("uid-brigade-1");
  });

  it("uses the example brigade contact in judge mode", async () => {
    setJudgeMode(true);
    expect(await brigadeContactId()).toBe("contact-daops-pekanbaru");
  });
});
