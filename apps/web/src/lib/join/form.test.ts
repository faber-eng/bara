import { describe, expect, it } from "vitest";
import { EMPTY_JOIN_FORM, type JoinFormValues, validateJoinForm } from "./form";

const valid: JoinFormValues = {
  inviteCode: " RIAU-2026 ",
  name: "  Ari Wibowo ",
  home: { lat: 0.51, lon: 101.45 },
  language: "id",
  whatsapp: "",
};

describe("validateJoinForm", () => {
  it("builds a request with trimmed text and a null WhatsApp number", () => {
    expect(validateJoinForm(valid)).toEqual({
      request: {
        invite_code: "RIAU-2026",
        name: "Ari Wibowo",
        home: { lat: 0.51, lon: 101.45 },
        language: "id",
        whatsapp: null,
      },
    });
  });

  it("lists every field that fails on an empty form", () => {
    expect(validateJoinForm(EMPTY_JOIN_FORM)).toEqual({
      errors: ["inviteCode", "name", "home"],
    });
  });

  it("strips spaces and dashes from a WhatsApp number", () => {
    const result = validateJoinForm({ ...valid, whatsapp: "+62 812-3456 7890" });
    expect(result).toMatchObject({ request: { whatsapp: "+6281234567890" } });
  });

  it("rejects a WhatsApp number without the plus sign", () => {
    expect(validateJoinForm({ ...valid, whatsapp: "081234567890" })).toEqual({
      errors: ["whatsapp"],
    });
  });

  it("rejects a name longer than 80 characters", () => {
    expect(validateJoinForm({ ...valid, name: "a".repeat(81) })).toEqual({ errors: ["name"] });
  });

  it("rejects a blank invite code", () => {
    expect(validateJoinForm({ ...valid, inviteCode: "   " })).toEqual({ errors: ["inviteCode"] });
  });
});
