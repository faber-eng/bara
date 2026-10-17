import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { type EvalReport, parseEvalReport } from "../../lib/eval/report";
import { EvalPanel, EvalPanelView } from "./EvalPanel";

const FULL = {
  generated_at: "2026-10-18T05:00:00Z",
  drying: {
    run_at: "2026-10-18T04:40:00Z",
    top_share: 0.1,
    years: [
      { year: 2021, weeks: 31, hotspots: 777, captured: 200, capture_rate: 0.4, lift: 3.5 },
      { year: 2022, weeks: 12, hotspots: 55, captured: 5, capture_rate: 0.1, lift: 1 },
    ],
  },
  reignition: {
    run_at: "2026-10-17T17:21:49Z",
    split: "test",
    events: 211,
    positives: 17,
    model: { name: "m1", auc: 0.601, precision_top10: 0.2 },
    baseline: { name: "b1", auc: 0.777, precision_top10: 0.4 },
  },
  evidence: {
    run_at: "2026-10-16T05:00:00Z",
    model: "gemini-x",
    sets: [
      {
        kind: "photo",
        n: 33,
        failed: 1,
        fields: [{ field: "dam_state", correct: 22, n: 33, accuracy: 0.667 }],
      },
      {
        kind: "voice",
        n: 9,
        failed: 0,
        fields: [{ field: "smoke", correct: 9, n: 9, accuracy: 1 }],
      },
    ],
  },
  agent: {
    run_at: "2026-10-15T05:00:00Z",
    model: "gemini-y",
    cases: 13,
    passed: 11,
    pass_rate: 0.846,
  },
};

function reportOf(input: unknown): EvalReport {
  const parsed = parseEvalReport(input);
  if (!parsed.ok) throw new Error(parsed.reason);
  return parsed.report;
}

describe("EvalPanelView", () => {
  afterEach(() => setCopyLanguage("id"));

  it("shows every number from the given report, with run dates and n", () => {
    setCopyLanguage("en");
    const { container } = render(<EvalPanelView report={reportOf(FULL)} />);
    const text = container.textContent ?? "";

    expect(text).toContain("2021");
    expect(text).toContain("3.5x");
    expect(text).toContain("40%");
    expect(text).toContain("777");
    expect(text).toContain("0.601");
    expect(text).toContain("0.777");
    expect(text).toContain("20%");
    expect(text).toContain("211 events, 17 re-ignited");
    expect(text).toContain("Run on 2026-10-18");
    expect(text).toContain("Run on 2026-10-17");
    expect(text).toContain("Run on 2026-10-16");
    expect(text).toContain("Run on 2026-10-15");
    expect(text).toContain("n = 33, 1 failed");
    expect(text).toContain("66.7% (22/33)");
    expect(text).toContain("Voice notes");
    expect(text).toContain("11 of 13 cases passed");
    expect(text).toContain("84.6%");
  });

  it("shows the baseline plainly when it wins", () => {
    setCopyLanguage("en");
    render(<EvalPanelView report={reportOf(FULL)} />);

    const baseline = screen.getByText("Detection-days baseline").closest("tr");
    const model = screen.getByText("Re-ignition model").closest("tr");
    expect(baseline).not.toBeNull();
    expect(model).not.toBeNull();
    if (baseline === null || model === null) return;
    expect(within(baseline).getByText("0.777")).toBeInTheDocument();
    expect(within(model).getByText("0.601")).toBeInTheDocument();
  });

  it("says Not run yet for each absent section", () => {
    setCopyLanguage("en");
    render(<EvalPanelView report={reportOf({ generated_at: FULL.generated_at })} />);

    expect(screen.getAllByText("Not run yet")).toHaveLength(4);
  });

  it("says Not run yet only for the section that is absent", () => {
    setCopyLanguage("en");
    render(<EvalPanelView report={reportOf({ ...FULL, drying: undefined })} />);

    expect(screen.getAllByText("Not run yet")).toHaveLength(1);
    expect(screen.getByText("Re-ignition risk")).toBeInTheDocument();
  });

  it("follows the language toggle", () => {
    render(<EvalPanelView report={reportOf(FULL)} />);

    expect(screen.getByText("Peringkat pengeringan")).toBeInTheDocument();
    expect(screen.getByText("3,5x")).toBeInTheDocument();
  });
});

describe("EvalPanel", () => {
  afterEach(() => setCopyLanguage("id"));

  it("renders the heading and the method pointer from the shipped file", () => {
    setCopyLanguage("en");
    render(<EvalPanel />);

    expect(screen.getByRole("heading", { name: "How well it works" })).toBeInTheDocument();
    expect(screen.getByText("Method and re-run commands: docs/EVAL.md")).toBeInTheDocument();
  });
});
