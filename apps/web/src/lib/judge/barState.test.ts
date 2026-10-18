import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getJudgeBarSnapshot, reloadJudgeBar } from "./barState";

const PHONE_QUERY = "(max-width: 700px)";

function stubViewport(narrow: boolean) {
  const matchMedia = vi.fn((query: string) => ({ matches: narrow && query === PHONE_QUERY }));
  vi.stubGlobal("matchMedia", matchMedia);
  return matchMedia;
}

function stateAfterReload() {
  reloadJudgeBar();
  return getJudgeBarSnapshot();
}

describe("judge bar default", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("defaults to closed on a narrow viewport with no stored choice", () => {
    const matchMedia = stubViewport(true);

    expect(stateAfterReload()).toBe("closed");
    expect(matchMedia).toHaveBeenCalledWith(PHONE_QUERY);
  });

  it("defaults to open on a wide viewport with no stored choice", () => {
    stubViewport(false);

    expect(stateAfterReload()).toBe("open");
  });

  it("keeps a stored open choice on a narrow viewport", () => {
    stubViewport(true);
    localStorage.setItem("bara.judgeBar", "open");

    expect(stateAfterReload()).toBe("open");
  });

  it("keeps a stored closed choice on a wide viewport", () => {
    stubViewport(false);
    localStorage.setItem("bara.judgeBar", "closed");

    expect(stateAfterReload()).toBe("closed");
  });

  it("defaults by viewport when the stored value is unknown", () => {
    stubViewport(true);
    localStorage.setItem("bara.judgeBar", "sideways");

    expect(stateAfterReload()).toBe("closed");
  });

  it("defaults to open when matchMedia is missing", () => {
    vi.stubGlobal("matchMedia", undefined);

    expect(stateAfterReload()).toBe("open");
  });
});
