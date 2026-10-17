import { describe, expect, it } from "vitest";
import type { CaseStatus } from "../contracts";
import { canCloseCase, confidenceLabel, evidenceImageUrl, toolCallArgs } from "./caseDrawer";

describe("canCloseCase", () => {
  it.each<[CaseStatus, boolean]>([
    ["open", false],
    ["assigned", false],
    ["reviewing", false],
    ["resolved_pending_human", true],
    ["human_review", true],
    ["overdue", false],
    ["escalated", false],
    ["monitoring", false],
    ["closed", false],
  ])("%s -> %s", (status, expected) => {
    expect(canCloseCase(status)).toBe(expected);
  });
});

describe("evidenceImageUrl", () => {
  it("passes an https url through", () => {
    expect(evidenceImageUrl("https://storage.example/ev.jpg")).toBe(
      "https://storage.example/ev.jpg",
    );
  });

  it("returns null for a storage path the browser cannot load", () => {
    expect(evidenceImageUrl("gs://bucket/ev-0001.jpg")).toBeNull();
  });
});

describe("confidenceLabel", () => {
  it("shows whole percent", () => {
    expect(confidenceLabel(0.9)).toBe("90%");
    expect(confidenceLabel(0.855)).toBe("86%");
  });
});

describe("toolCallArgs", () => {
  it("lists arguments as key=value in order", () => {
    expect(toolCallArgs({ region: "riau", limit: 10, flag: true })).toBe(
      'region="riau", limit=10, flag=true',
    );
  });

  it("shows no arguments as an empty string", () => {
    expect(toolCallArgs({})).toBe("");
  });
});
