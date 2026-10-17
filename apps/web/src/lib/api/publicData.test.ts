import { describe, expect, it } from "vitest";
import { ResponseShapeError } from "./parse";
import { parseBulletin, parseSummary, publicPath } from "./publicData";

describe("publicPath", () => {
  it("adds the week and extra params", () => {
    expect(publicPath("riau", "cells", "2026-W42", "limit=200")).toBe(
      "/api/public/riau/cells?limit=200&week=2026-W42",
    );
    expect(publicPath("riau", "summary")).toBe("/api/public/riau/summary");
  });
});

describe("parseBulletin", () => {
  const gemini = {
    region: "riau",
    week: "2026-W42",
    text_id: "Minggu ini 12 petak berisiko tinggi.",
    text_en: "This week 12 cells are at high risk.",
    cited: [{ field: "high_risk_cells", value: 12 }],
    source: "gemini",
    model: "gemini-3.5-flash",
    prompt_version: "bulletin-v1",
    created_at: "2026-10-17T04:00:00Z",
  };

  it("reads a Gemini bulletin with its model, prompt version and cited fields", () => {
    const bulletin = parseBulletin(gemini);

    expect(bulletin.source).toBe("gemini");
    expect(bulletin.model).toBe("gemini-3.5-flash");
    expect(bulletin.cited).toEqual([{ field: "high_risk_cells", value: 12 }]);
  });

  it("reads the empty bulletin", () => {
    const bulletin = parseBulletin({
      ...gemini,
      text_id: null,
      text_en: null,
      cited: [],
      source: null,
      model: null,
      prompt_version: null,
      created_at: null,
    });

    expect(bulletin.source).toBeNull();
  });

  it("rejects an unknown source", () => {
    expect(() => parseBulletin({ ...gemini, source: "human" })).toThrow(ResponseShapeError);
  });
});

describe("parseSummary", () => {
  it("keeps a null median and a zero count", () => {
    const summary = parseSummary({
      region: "riau",
      week: "2026-W42",
      high_risk_cells: 0,
      dams_broken: 0,
      cases_open: 0,
      cases_escalated: 0,
      cases_closed: 0,
      median_days_to_repair: null,
      tasks_on_time_pct: null,
      data_as_of: { s1_pass_date: "2026-10-12", ranking_run_at: "2026-10-11T17:00:00Z" },
    });

    expect(summary.high_risk_cells).toBe(0);
    expect(summary.median_days_to_repair).toBeNull();
  });
});
