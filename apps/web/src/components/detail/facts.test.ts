import { describe, expect, it } from "vitest";
import { detailCopy } from "../../lib/copy/detail";
import { componentFacts, decisionLine, rankChangeShort, scoreBand, scoreLevel } from "./facts";

const copy = detailCopy("en");

describe("detail facts", () => {
  it("bands the drying score in the legend's steps of 20", () => {
    expect([0, 19.9, 20, 59, 80, 100].map(scoreLevel)).toEqual([1, 1, 2, 3, 5, 5]);
    expect(scoreBand(96.8, copy)).toBe("Very fast drying");
    expect(scoreBand(5, copy)).toBe("Slow drying");
  });

  it("reads a rank change in plain words", () => {
    expect(rankChangeShort(7, copy)).toBe("↑7");
    expect(rankChangeShort(-3, copy)).toBe("↓3");
    expect(rankChangeShort(0, copy)).toBe("same");
    expect(rankChangeShort(null, copy)).toBe("new");
  });

  it("gives each component a unit and a plain meaning where a rule exists", () => {
    const rows = componentFacts(
      {
        s1_anom_db: -5.1,
        rain_30d_mm: 182.6,
        rain_deficit_pct: -0.05,
        canal_dist_m: 2505,
        peat_class: 1,
      },
      copy,
      "en",
    );

    expect(rows).toEqual([
      { label: "Radar change", value: "-5.1 dB", meaning: "The surface got drier" },
      { label: "Rain, 30 days", value: "182.6 mm", meaning: null },
      { label: "Rain deficit", value: "-5%", meaning: "More rain than normal" },
      { label: "Canal distance", value: "2,505 m", meaning: null },
      { label: "Peat class", value: "1", meaning: null },
    ]);
  });

  it("says when there was no radar pass", () => {
    const [radar] = componentFacts(
      { s1_anom_db: null, rain_30d_mm: 1, rain_deficit_pct: 0.4, canal_dist_m: 10, peat_class: 2 },
      copy,
      "en",
    );

    expect(radar).toEqual({
      label: "Radar change",
      value: "n/a",
      meaning: "No radar pass this week",
    });
  });

  it("joins the agent decision and its reason with one stop", () => {
    expect(decisionLine("Wait for the volunteer to check the dam.", "The area ranks 6.")).toBe(
      "Wait for the volunteer to check the dam. The area ranks 6.",
    );
    expect(decisionLine("assign", "riau-0412 ranks first.")).toBe("assign: riau-0412 ranks first.");
  });
});
