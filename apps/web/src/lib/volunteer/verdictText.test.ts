import { describe, expect, it } from "vitest";
import type { Evidence, Verdict } from "../contracts";
import { volunteerCopy } from "../copy/volunteer";
import { describeVerdict, formatConfidence, headlineKey, nextKey } from "./verdictText";

const brokenDam: Verdict = {
  subject: "canal_dam",
  dam_state: "broken",
  smoke: "none",
  hot_ground_signs: "none",
  open_flame: "no",
  transcript: null,
  transcript_en: null,
  reasons: ["breach on the left side"],
  confidence: 0.9,
  needs_human: false,
};

const evidence: Evidence = {
  id: "e1",
  task_id: "t1",
  case_id: "c1",
  kind: "photo",
  gcs_uri: "gs://b/e1",
  sha256: "0".repeat(64),
  point: null,
  captured_at: null,
  verdict: brokenDam,
  location_ok: true,
  uploaded_by: "vol-ari",
  sample: false,
};

describe("headlineKey", () => {
  it("names a broken dam", () => {
    expect(headlineKey(brokenDam, true)).toBe("dam_broken");
  });

  it("puts a location mismatch before the dam state", () => {
    expect(headlineKey(brokenDam, false)).toBe("location_mismatch");
  });

  it("puts smoke before the dam state", () => {
    expect(headlineKey({ ...brokenDam, smoke: "wisps" }, true)).toBe("smoke");
  });

  it("says unclear when a person has to review an unknown dam", () => {
    const unknown: Verdict = { ...brokenDam, dam_state: "unknown", needs_human: true };
    expect(headlineKey(unknown, null)).toBe("unclear");
  });

  it("falls back to received for a voice note", () => {
    const voice: Verdict = { ...brokenDam, dam_state: "not_applicable" };
    expect(headlineKey(voice, null)).toBe("received");
  });
});

describe("nextKey", () => {
  it("asks for no resend when a person reviews", () => {
    expect(nextKey({ ...brokenDam, needs_human: true }, true)).toBe("human");
  });

  it("forwards a broken dam and records an intact one", () => {
    expect(nextKey(brokenDam, true)).toBe("forwarded");
    expect(nextKey({ ...brokenDam, dam_state: "intact" }, true)).toBe("recorded");
  });
});

describe("formatConfidence", () => {
  it("uses a comma in Indonesian and a dot in English", () => {
    expect(formatConfidence(0.9, "id")).toBe("0,90");
    expect(formatConfidence(0.9, "en")).toBe("0.90");
  });
});

describe("describeVerdict", () => {
  it("builds plain Indonesian rows for a broken dam", () => {
    const view = describeVerdict(evidence, brokenDam, volunteerCopy("id"), "id");

    expect(view.headline).toBe("Sekat terlihat jebol");
    expect(view.rows).toEqual([
      { label: "Kondisi sekat", value: "Jebol" },
      { label: "Asap", value: "Tidak ada" },
      { label: "Lokasi", value: "Cocok" },
      { label: "Keyakinan", value: "0,90" },
    ]);
    expect(view.sample).toBe(false);
  });

  it("carries the sample flag and the English transcript", () => {
    const voice: Verdict = {
      ...brokenDam,
      transcript: "sekat jebol",
      transcript_en: "the dam broke",
    };
    const view = describeVerdict({ ...evidence, sample: true }, voice, volunteerCopy("en"), "en");

    expect(view.sample).toBe(true);
    expect(view.rows).toContainEqual({ label: "What was heard", value: "the dam broke" });
  });

  it("omits the location row when the location was not checked", () => {
    const view = describeVerdict(
      { ...evidence, location_ok: null },
      brokenDam,
      volunteerCopy("en"),
      "en",
    );
    expect(view.rows.map((row) => row.label)).not.toContain("Location");
  });

  it("does not judge the location of a sample", () => {
    const sample = { ...evidence, sample: true, location_ok: false };
    const view = describeVerdict(sample, brokenDam, volunteerCopy("en"), "en");

    expect(view.headline).toBe("The dam looks broken");
    expect(view.rows.map((row) => row.label)).not.toContain("Location");
  });
});
