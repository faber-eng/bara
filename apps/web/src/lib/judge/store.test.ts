import { beforeEach, describe, expect, it } from "vitest";
import { JUDGE_PEOPLE, personFor } from "./people";
import {
  getJudgeSnapshot,
  roleHeaderValue,
  selectPerson,
  setJudgeMode,
  subscribeJudge,
} from "./store";

describe("judge store", () => {
  beforeEach(() => {
    setJudgeMode(false);
    localStorage.clear();
  });

  it("lists the five example people with the agreed ids", () => {
    expect(JUDGE_PEOPLE.map((person) => person.key)).toEqual([
      "ops",
      "vol-ari",
      "team-sari",
      "vol-dedi",
      "contact-daops-pekanbaru",
    ]);
    expect(JUDGE_PEOPLE.slice(1).every((person) => person.label.endsWith("(example)"))).toBe(true);
  });

  it("sends no role header while judge mode is off", () => {
    expect(roleHeaderValue()).toBeUndefined();
  });

  it("defaults to ops once judge mode turns on", () => {
    setJudgeMode(true);

    expect(roleHeaderValue()).toBe("ops");
  });

  it.each([
    ["vol-ari", "volunteer"],
    ["team-sari", "volunteer"],
    ["vol-dedi", "volunteer"],
    ["contact-daops-pekanbaru", "brigade"],
    ["ops", "ops"],
  ])("maps %s to the %s role header", (key, role) => {
    setJudgeMode(true);
    selectPerson(key);

    expect(roleHeaderValue()).toBe(role);
  });

  it("clears the stored person when judge mode turns off", () => {
    setJudgeMode(true);
    selectPerson("vol-ari");
    expect(localStorage.getItem("bara.judge.person")).toBe("vol-ari");

    setJudgeMode(false);

    expect(localStorage.getItem("bara.judge.person")).toBeNull();
    expect(roleHeaderValue()).toBeUndefined();
    expect(getJudgeSnapshot().personKey).toBe("ops");
  });

  it("restores the stored person when judge mode turns on", () => {
    localStorage.setItem("bara.judge.person", "vol-dedi");
    setJudgeMode(true);

    expect(roleHeaderValue()).toBe("volunteer");
    expect(getJudgeSnapshot().personKey).toBe("vol-dedi");
  });

  it("ignores a key that is not a judge person", () => {
    setJudgeMode(true);
    selectPerson("someone-else");

    expect(getJudgeSnapshot().personKey).toBe("ops");
  });

  it("notifies subscribers on a change", () => {
    let calls = 0;
    const unsubscribe = subscribeJudge(() => {
      calls += 1;
    });

    setJudgeMode(true);
    selectPerson("vol-ari");
    unsubscribe();
    selectPerson("ops");

    expect(calls).toBe(2);
  });

  it("finds a person by key", () => {
    expect(personFor("team-sari")?.label).toBe("Repair team Sari (example)");
    expect(personFor("nobody")).toBeUndefined();
  });
});
