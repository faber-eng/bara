import { afterEach, describe, expect, it, vi } from "vitest";

const KEY = "bara.copy-language";

async function freshModule() {
  vi.resetModules();
  return import("./language");
}

describe("copy language default", () => {
  afterEach(() => {
    localStorage.clear();
    document.documentElement.lang = "en";
  });

  it("opens in English with html lang en when nothing is stored", async () => {
    localStorage.clear();
    const { setCopyLanguage } = await freshModule();
    expect(document.documentElement.lang).toBe("en");
    setCopyLanguage("en");
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("remembers Indonesian after the user picks it and keeps html lang matching", async () => {
    const first = await freshModule();
    first.setCopyLanguage("id");
    expect(localStorage.getItem(KEY)).toBe("id");
    expect(document.documentElement.lang).toBe("id");

    await freshModule();
    expect(document.documentElement.lang).toBe("id");
  });

  it("falls back to English for an unknown stored value", async () => {
    localStorage.setItem(KEY, "fr");
    await freshModule();
    expect(document.documentElement.lang).toBe("en");
  });

  it("falls back to English when storage reads throw", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    await freshModule();
    expect(document.documentElement.lang).toBe("en");
    vi.restoreAllMocks();
  });

  it("still switches when storage writes throw", async () => {
    const { setCopyLanguage } = await freshModule();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => setCopyLanguage("id")).not.toThrow();
    expect(document.documentElement.lang).toBe("id");
    vi.restoreAllMocks();
  });
});
