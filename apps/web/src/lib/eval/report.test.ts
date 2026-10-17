import { describe, expect, it } from "vitest";
import evalJson from "../../eval/eval.json";
import { parseEvalReport } from "./report";

const MINIMAL = { generated_at: "2026-10-18T05:00:00Z" };

const AGENT = {
  run_at: "2026-10-18T05:00:00Z",
  model: "m",
  cases: 4,
  passed: 3,
  pass_rate: 0.75,
};

describe("parseEvalReport", () => {
  it("accepts the shipped eval file", () => {
    expect(parseEvalReport(evalJson).ok).toBe(true);
  });

  it("treats absent sections as not run", () => {
    const parsed = parseEvalReport(MINIMAL);

    expect(parsed).toEqual({
      ok: true,
      report: {
        generatedAt: MINIMAL.generated_at,
        drying: null,
        reignition: null,
        evidence: null,
        agent: null,
      },
    });
  });

  it("reads a present section", () => {
    const parsed = parseEvalReport({ ...MINIMAL, agent: AGENT });

    expect(parsed.ok && parsed.report.agent?.passRate).toBe(0.75);
  });

  it("keeps a zero rate", () => {
    const parsed = parseEvalReport({ ...MINIMAL, agent: { ...AGENT, passed: 0, pass_rate: 0 } });

    expect(parsed.ok && parsed.report.agent?.passed).toBe(0);
  });

  it("keeps a null capture rate and lift for a year without hotspots", () => {
    const drying = {
      run_at: "2026-10-18T05:00:00Z",
      top_share: 0.1,
      years: [{ year: 2026, weeks: 3, hotspots: 0, captured: 0, capture_rate: null, lift: null }],
    };

    const parsed = parseEvalReport({ ...MINIMAL, drying });

    expect(parsed.ok && parsed.report.drying?.years[0]).toMatchObject({
      captureRate: null,
      lift: null,
    });
  });

  it("rejects a capture rate that is text", () => {
    const drying = {
      run_at: "2026-10-18T05:00:00Z",
      top_share: 0.1,
      years: [{ year: 2026, weeks: 3, hotspots: 1, captured: 0, capture_rate: "0", lift: 0 }],
    };

    expect(parseEvalReport({ ...MINIMAL, drying }).ok).toBe(false);
  });

  it.each([
    ["a non-object", "nope"],
    ["null", null],
    ["a missing generated_at", {}],
    ["a bad generated_at", { generated_at: "yesterday" }],
    ["a section of the wrong type", { ...MINIMAL, agent: "ran" }],
    ["a null section", { ...MINIMAL, agent: null }],
    ["a string where a number belongs", { ...MINIMAL, agent: { ...AGENT, cases: "4" } }],
    ["a missing field", { ...MINIMAL, agent: { ...AGENT, model: undefined } }],
    ["a non-finite number", { ...MINIMAL, agent: { ...AGENT, pass_rate: Number.NaN } }],
    [
      "a bad list item",
      { ...MINIMAL, drying: { run_at: AGENT.run_at, top_share: 0.1, years: [{ year: 2019 }] } },
    ],
  ])("rejects %s", (_name, input) => {
    expect(parseEvalReport(input).ok).toBe(false);
  });
});
