import { describe, expect, it } from "vitest";
import { fieldsForNumber, segmentExplanation } from "./citedNumbers";

const CITED = { canal_dist_m: 340, rain_deficit_pct: 45, s1_anom_db: -2.3, rank: 7 };

describe("fieldsForNumber", () => {
  it("names the field whose cited value equals the number", () => {
    expect(fieldsForNumber("340", CITED)).toEqual(["canal_dist_m"]);
    expect(fieldsForNumber("-2.3", CITED)).toEqual(["s1_anom_db"]);
  });

  it("names every field when two cited values are equal", () => {
    expect(fieldsForNumber("7", { rank: 7, peat_class: 7 })).toEqual(["rank", "peat_class"]);
  });

  it("matches a fraction shown as a percent and a value shown rounded", () => {
    expect(fieldsForNumber("95", { rain_deficit_pct: 0.95 })).toEqual(["rain_deficit_pct"]);
    expect(fieldsForNumber("2632", { canal_dist_m: 2631.8 })).toEqual(["canal_dist_m"]);
    expect(fieldsForNumber("2.6", { canal_dist_m: 2.63 })).toEqual(["canal_dist_m"]);
  });

  it("reads a fraction as a percent only for a percent field", () => {
    expect(fieldsForNumber("100", { peat_class: 1 })).toEqual([]);
    expect(fieldsForNumber("0", { rain_deficit_pct: 0 })).toEqual(["rain_deficit_pct"]);
  });

  it("does not match a number to a larger value by accident", () => {
    expect(fieldsForNumber("5", { rank: 50 })).toEqual([]);
  });

  it("returns none for a number that is not cited", () => {
    expect(fieldsForNumber("12", CITED)).toEqual([]);
  });
});

describe("segmentExplanation", () => {
  it("splits the text around cited numbers and keeps the rest whole", () => {
    const segments = segmentExplanation(
      "Canal is 340 m away, rain is 45% under, 12 days dry.",
      CITED,
    );

    expect(segments.map((segment) => segment.text).join("")).toBe(
      "Canal is 340 m away, rain is 45% under, 12 days dry.",
    );
    expect(segments.filter((segment) => segment.fields.length > 0)).toEqual([
      { start: 9, text: "340", fields: ["canal_dist_m"] },
      { start: 29, text: "45", fields: ["rain_deficit_pct"] },
    ]);
  });

  it("returns one plain segment when nothing is cited", () => {
    expect(segmentExplanation("No numbers here.", CITED)).toEqual([
      { start: 0, text: "No numbers here.", fields: [] },
    ]);
  });

  it("returns nothing for empty text", () => {
    expect(segmentExplanation("", CITED)).toEqual([]);
  });
});
