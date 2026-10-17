import type { Evidence, Verdict } from "../contracts";
import type { CopyLanguage } from "../copy/language";
import type { HeadlineKey, NextKey, VolunteerCopy } from "../copy/volunteer";

export type VerdictRow = { label: string; value: string };

export type VerdictView = {
  headline: string;
  rows: VerdictRow[];
  next: string;
  reasons: string[];
  needsHuman: boolean;
  sample: boolean;
};

const DAM_HEADLINES: Partial<Record<Verdict["dam_state"], HeadlineKey>> = {
  broken: "dam_broken",
  damaged: "dam_damaged",
  intact: "dam_intact",
  overtopped: "dam_overtopped",
};

function hasSmoke(verdict: Verdict): boolean {
  return verdict.smoke === "wisps" || verdict.smoke === "plume";
}

export function headlineKey(verdict: Verdict, locationOk: boolean | null): HeadlineKey {
  if (locationOk === false) return "location_mismatch";
  if (hasSmoke(verdict)) return "smoke";
  const damHeadline = DAM_HEADLINES[verdict.dam_state];
  if (verdict.subject === "canal_dam" && damHeadline !== undefined) return damHeadline;
  if (verdict.needs_human || verdict.subject === "other") return "unclear";
  return "received";
}

export function nextKey(verdict: Verdict, locationOk: boolean | null): NextKey {
  if (locationOk === false) return "location";
  if (verdict.needs_human) return "human";
  if (hasSmoke(verdict)) return "stay_away";
  if (verdict.dam_state === "broken" || verdict.dam_state === "damaged") return "forwarded";
  return "recorded";
}

export function formatConfidence(value: number, language: CopyLanguage): string {
  const text = value.toFixed(2);
  return language === "id" ? text.replace(".", ",") : text;
}

function locationRow(copy: VolunteerCopy, locationOk: boolean | null): VerdictRow[] {
  if (locationOk === null) return [];
  return [{ label: copy.rowLocation, value: locationOk ? copy.locationOk : copy.locationBad }];
}

function damRow(copy: VolunteerCopy, verdict: Verdict): VerdictRow[] {
  if (verdict.subject !== "canal_dam") return [];
  return [{ label: copy.rowDam, value: copy.damStates[verdict.dam_state] }];
}

function smokeRow(copy: VolunteerCopy, verdict: Verdict): VerdictRow[] {
  if (verdict.smoke === "unknown") return [];
  return [{ label: copy.rowSmoke, value: copy.smokes[verdict.smoke] }];
}

function hotRow(copy: VolunteerCopy, verdict: Verdict): VerdictRow[] {
  if (verdict.hot_ground_signs === "unknown" || verdict.hot_ground_signs === "none") return [];
  return [{ label: copy.rowHot, value: copy.hotGrounds[verdict.hot_ground_signs] }];
}

function heardRow(copy: VolunteerCopy, verdict: Verdict, language: CopyLanguage): VerdictRow[] {
  const heard = language === "en" ? verdict.transcript_en : verdict.transcript;
  if (heard === null || heard === "") return [];
  return [{ label: copy.rowHeard, value: heard }];
}

export function describeVerdict(
  evidence: Evidence,
  verdict: Verdict,
  copy: VolunteerCopy,
  language: CopyLanguage,
): VerdictView {
  const locationOk = evidence.sample ? null : evidence.location_ok;
  const rows = [
    ...damRow(copy, verdict),
    ...smokeRow(copy, verdict),
    ...hotRow(copy, verdict),
    ...locationRow(copy, locationOk),
    ...heardRow(copy, verdict, language),
    { label: copy.rowConfidence, value: formatConfidence(verdict.confidence, language) },
  ];
  return {
    headline: copy.headline[headlineKey(verdict, locationOk)],
    rows,
    next: copy.next[nextKey(verdict, locationOk)],
    reasons: verdict.reasons,
    needsHuman: verdict.needs_human,
    sample: evidence.sample,
  };
}
