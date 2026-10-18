import type { RankingComponents } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
import type { CopyLanguage } from "../../lib/copy/language";
import { formatFixed, formatNumber, formatPercent } from "../../lib/public/format";

export type FactRow = { label: string; value: string; meaning: string | null };

const SCORE_STEP = 20;
const MAX_LEVEL = 5;
const PERCENT = 100;

export function scoreLevel(score: number): number {
  const level = Math.floor(score / SCORE_STEP) + 1;
  return Math.min(MAX_LEVEL, Math.max(1, level));
}

export function scoreBand(score: number, copy: DetailCopy): string {
  return copy.bands[scoreLevel(score) - 1] ?? copy.bands[0];
}

export function scoreFact(score: number, copy: DetailCopy, language: CopyLanguage): FactRow {
  return {
    label: copy.facts.score,
    value: `${formatFixed(score, 1, language)} / 100`,
    meaning: scoreBand(score, copy),
  };
}

export function rankChangeMeaning(change: number | null, copy: DetailCopy): string {
  if (change === null) return copy.meanings.isNew;
  if (change === 0) return copy.meanings.same;
  if (change > 0) return copy.meanings.up(change);
  return copy.meanings.down(Math.abs(change));
}

export function rankChangeShort(change: number | null, copy: DetailCopy): string {
  if (change === null) return copy.rankChangeShort.isNew;
  if (change === 0) return copy.rankChangeShort.same;
  if (change > 0) return copy.rankChangeShort.up(change);
  return copy.rankChangeShort.down(Math.abs(change));
}

function radarFact(components: RankingComponents, copy: DetailCopy, language: CopyLanguage) {
  const value = components.s1_anom_db;
  if (value === null) {
    return {
      label: copy.facts.radar,
      value: copy.facts.notAvailable,
      meaning: copy.meanings.noRadar,
    };
  }
  return {
    label: copy.facts.radar,
    value: `${formatFixed(value, 1, language)} dB`,
    meaning: radarMeaning(value, copy),
  };
}

function radarMeaning(value: number, copy: DetailCopy): string | null {
  if (value < 0) return copy.meanings.drier;
  if (value > 0) return copy.meanings.wetter;
  return null;
}

function rainDeficitMeaning(share: number, copy: DetailCopy): string {
  if (share > 0) return copy.meanings.lessRain;
  if (share < 0) return copy.meanings.moreRain;
  return copy.meanings.normalRain;
}

export function componentFacts(
  components: RankingComponents,
  copy: DetailCopy,
  language: CopyLanguage,
): FactRow[] {
  return [
    radarFact(components, copy, language),
    {
      label: copy.facts.rain30,
      value: `${formatFixed(components.rain_30d_mm, 1, language)} mm`,
      meaning: null,
    },
    {
      label: copy.facts.rainDeficit,
      value: `${formatNumber(Math.round(components.rain_deficit_pct * PERCENT), language)}%`,
      meaning: rainDeficitMeaning(components.rain_deficit_pct, copy),
    },
    {
      label: copy.facts.canal,
      value: `${formatNumber(Math.round(components.canal_dist_m), language)} m`,
      meaning: null,
    },
    { label: copy.facts.peatClass, value: String(components.peat_class), meaning: null },
  ];
}

export function chanceText(chance: number, language: CopyLanguage): string {
  return formatPercent(chance, language);
}
