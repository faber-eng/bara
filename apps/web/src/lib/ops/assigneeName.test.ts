import { describe, expect, it } from "vitest";
import { assigneeName } from "./assigneeName";

describe("assigneeName", () => {
  it("returns the display name when the API sent one", () => {
    expect(assigneeName({ "vol-ari": "Ari" }, "vol-ari")).toBe("Ari");
  });

  it("falls back to the uid when no name is known", () => {
    expect(assigneeName({ "vol-ari": "Ari" }, "team-sari")).toBe("team-sari");
  });

  it("falls back to the uid when the name is empty", () => {
    expect(assigneeName({ "vol-ari": "" }, "vol-ari")).toBe("vol-ari");
  });
});
